from __future__ import annotations

import logging
from typing import Any

from fastapi import HTTPException

from ..config import Settings
from ..db import Database
from ..repositories import Repository
from .issue_loader import IssueLoader
from .llm_client import LLMClient
from .orchestrator import Orchestrator
from .report_builder import ReportBuilder
from ..schemas import AnalyzeRequest


class JobService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.database = Database(settings.database_path)
        self.database.init_schema()
        self.repository = Repository(self.database)
        self.issue_loader = IssueLoader(settings)
        self.llm_client = LLMClient(settings)
        self.orchestrator = Orchestrator(
            self.repository,
            settings.project_root,
            self.llm_client,
            settings.github_token,
            settings.debugger_require_llm,
        )
        self.report_builder = ReportBuilder()
        self.logger = logging.getLogger(__name__)

    def enqueue_analyze(self, payload: AnalyzeRequest) -> dict[str, Any]:
        try:
            source, issues, metadata = self.issue_loader.load_from_request(payload)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return self._start_job(source, issues, metadata)

    def enqueue_analyze_upload(self, filename: str, raw_bytes: bytes) -> dict[str, Any]:
        try:
            source, issues, metadata = self.issue_loader.load_from_upload(filename, raw_bytes)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if not issues:
            raise HTTPException(status_code=400, detail='Uploaded file did not contain any issues.')
        return self._start_job(source, issues, metadata)

    def get_job_status(self, job_id: str) -> dict[str, Any]:
        job = self.repository.get_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail='Job not found.')
        trace = self.repository.get_agent_runs(job_id)
        report = self.repository.get_report_record(job_id)
        return {
            'job_id': job['id'],
            'status': job['status'],
            'created_at': job['created_at'],
            'updated_at': job['updated_at'],
            'report_ready': bool(report),
            'report_id': report['id'] if report else None,
            'agent_trace': [_serialize_trace_item(item) for item in trace],
        }

    def get_report(self, report_id: str) -> dict[str, Any]:
        report = self.repository.get_report_record(report_id)
        if not report:
            raise HTTPException(status_code=404, detail='Report not found.')
        issue = self.repository.get_primary_issue_for_job(report['job_id'])
        trace = self.repository.get_agent_runs(report['job_id'])
        feedback = self.repository.get_feedback(report_id)
        diagnosis = _loads(report['diagnosis_json'])
        return {
            'report_id': report['id'],
            'job_id': report['job_id'],
            'issue': {
                'id': issue['id'],
                'external_id': issue['external_id'],
                'title': issue['title'],
                'body': issue['body'],
                'url': issue['issue_url'],
            },
            'diagnosis': diagnosis,
            'requires_human': bool(report['requires_human']),
            'rerun_count': report['rerun_count'],
            'agent_trace': [_serialize_trace_item(item) for item in trace],
            'html_report': report['html_report'],
            'human_feedback': feedback,
        }

    def add_human_feedback(self, report_id: str, human_note: str) -> dict[str, Any]:
        report = self.repository.get_report_record(report_id)
        if not report:
            raise HTTPException(status_code=404, detail='Report not found.')
        return self.repository.add_human_feedback(report_id, report['job_id'], human_note)

    def rerun_debugger(self, report_id: str) -> dict[str, Any]:
        report = self.repository.get_report_record(report_id)
        if not report:
            raise HTTPException(status_code=404, detail='Report not found.')
        latest_feedback = self.repository.get_latest_feedback(report_id)
        if not latest_feedback:
            raise HTTPException(status_code=400, detail='Human feedback is required before rerunning the debugger.')
        issue = self.repository.get_primary_issue_for_job(report['job_id'])
        if not issue:
            raise HTTPException(status_code=404, detail='Primary issue not found.')

        try:
            rerun = self.orchestrator.rerun_debugger(report['job_id'], issue['raw'], latest_feedback['human_note'])
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        trace = self.repository.get_agent_runs(report['job_id'])
        triage = self.repository.get_latest_agent_run(report['job_id'], 'Triager')
        research = self.repository.get_latest_agent_run(report['job_id'], 'Researcher')
        diagnosis = self._build_diagnosis(issue['raw'], triage['artifacts'], research['artifacts'], rerun['result']['artifacts'])
        requires_human = bool(rerun['result']['artifacts'].get('requires_human'))
        html_report = self.report_builder.build(issue['raw'], trace, diagnosis, requires_human, self.repository.get_feedback(report_id))
        rerun_count = int(report['rerun_count']) + 1
        self.repository.save_report(report_id, report['job_id'], report['issue_id'], diagnosis['type'], diagnosis, html_report, requires_human, rerun_count)
        return {
            'report_id': report_id,
            'rerun_count': rerun_count,
            'requires_human': requires_human,
            'debugger': rerun['result']['artifacts'],
        }

    def _start_job(self, source: str, issues: list[dict[str, Any]], metadata: dict[str, Any]) -> dict[str, Any]:
        job_id, stored_issues = self.repository.create_job(source, issues, metadata)
        self.repository.update_job_status(job_id, 'queued')
        self._run_job(job_id, stored_issues[0]['id'], issues[0], metadata)
        return {'report_id': job_id, 'job_id': job_id, 'status': 'completed'}

    def _run_job(self, job_id: str, issue_id: str, primary_issue: dict[str, Any], metadata: dict[str, Any]) -> None:
        self.logger.info('analysis job started: %s', job_id)
        self.repository.update_job_status(job_id, 'running')
        try:
            result = self.orchestrator.analyze(job_id, primary_issue, metadata)
            diagnosis = self._build_diagnosis(
                primary_issue,
                result['context'],
                result['context'],
                result['branch_result']['artifacts'] if result['branch_result'] else {},
            )
            requires_human = bool(diagnosis.get('requires_human', False))
            html_report = self.report_builder.build(primary_issue, result['trace'], diagnosis, requires_human, [])
            self.repository.save_report(job_id, job_id, issue_id, diagnosis['type'], diagnosis, html_report, requires_human, 0)
            self.logger.info('analysis job completed: %s type=%s', job_id, diagnosis['type'])
        except Exception:
            self.repository.update_job_status(job_id, 'failed')
            self.logger.exception('analysis job failed: %s', job_id)
            raise

    def _build_diagnosis(
        self,
        issue: dict[str, Any],
        triage_context: dict[str, Any],
        research_context: dict[str, Any],
        branch_artifacts: dict[str, Any],
    ) -> dict[str, Any]:
        issue_type = triage_context.get('issue_type', 'Feature')
        diagnosis = {
            'type': issue_type,
            'issue_title': issue.get('title', ''),
            'triage_confidence': triage_context.get('confidence', 0.0),
            'triage_rationale': triage_context.get('rationale', ''),
            'related_files': research_context.get('related_files', []),
            'research_summary': research_context.get('research_summary', ''),
            'source_scope': research_context.get('source_scope', 'local_project'),
            'source_repo': research_context.get('source_repo'),
            'degraded_reason': research_context.get('degraded_reason'),
            'root_cause_hypothesis': branch_artifacts.get('root_cause_hypothesis', research_context.get('research_summary', 'Further analysis required.')),
            'fix_suggestions': branch_artifacts.get('fix_suggestions', ['Review the highlighted files and confirm the intended workflow.']),
            'reproduce_steps': branch_artifacts.get('reproduce_steps', []),
            'reproduce_code': branch_artifacts.get('reproduce_code', ''),
            'doc_targets': branch_artifacts.get('doc_targets', []),
            'gap_analysis': branch_artifacts.get('gap_analysis', ''),
            'suggested_updates': branch_artifacts.get('suggested_updates', []),
            'requires_human': branch_artifacts.get('requires_human', False),
            'human_reason': branch_artifacts.get('human_reason'),
            'llm_error_kind': branch_artifacts.get('llm_error_kind'),
            'llm_error_message': branch_artifacts.get('llm_error_message'),
        }
        return diagnosis


import json


def _loads(raw: str) -> dict[str, Any]:
    return json.loads(raw)


def _serialize_trace_item(item: dict[str, Any]) -> dict[str, Any]:
    return {
        'id': item['id'],
        'agent_name': item['agent_name'],
        'step_index': item['step_index'],
        'status': item['status'],
        'summary': item['summary'],
        'artifacts': item['artifacts'],
        'evidence': item['evidence'],
        'created_at': item['created_at'],
    }
