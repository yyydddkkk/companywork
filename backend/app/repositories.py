from __future__ import annotations

from datetime import datetime, timezone
import json
from typing import Any
from uuid import uuid4

from .db import Database


class Repository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def create_job(self, source: str, issues: list[dict[str, Any]], metadata: dict[str, Any]) -> tuple[str, list[dict[str, Any]]]:
        job_id = str(uuid4())
        now = _utc_now()
        normalized_issues: list[dict[str, Any]] = []
        with self.database.connect() as conn:
            conn.execute(
                'INSERT INTO analysis_jobs (id, source, status, issue_count, metadata_json, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)',
                (job_id, source, 'running', len(issues), _json(metadata), now, now),
            )
            for issue in issues:
                issue_id = str(uuid4())
                record = {
                    'id': issue_id,
                    'job_id': job_id,
                    'external_id': issue.get('external_id') or issue.get('id'),
                    'source': source,
                    'title': issue.get('title', '').strip(),
                    'body': issue.get('body', '').strip(),
                    'issue_url': issue.get('url'),
                    'raw_json': _json(issue),
                    'created_at': now,
                }
                conn.execute(
                    '''
                    INSERT INTO issues (id, job_id, external_id, source, title, body, issue_url, raw_json, created_at)
                    VALUES (:id, :job_id, :external_id, :source, :title, :body, :issue_url, :raw_json, :created_at)
                    ''',
                    record,
                )
                normalized_issues.append(record)
        return job_id, normalized_issues

    def add_agent_run(self, job_id: str, agent_name: str, status: str, summary: str, artifacts: dict[str, Any], evidence: list[dict[str, Any]]) -> dict[str, Any]:
        now = _utc_now()
        with self.database.connect() as conn:
            row = conn.execute('SELECT COALESCE(MAX(step_index), 0) AS max_step FROM agent_runs WHERE job_id = ?', (job_id,)).fetchone()
            step_index = int(row['max_step']) + 1
            run_id = str(uuid4())
            conn.execute(
                '''
                INSERT INTO agent_runs (id, job_id, agent_name, step_index, status, summary, artifacts_json, evidence_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''',
                (run_id, job_id, agent_name, step_index, status, summary, _json(artifacts), _json(evidence), now),
            )
        return {
            'id': run_id,
            'agent_name': agent_name,
            'step_index': step_index,
            'status': status,
            'summary': summary,
            'artifacts': artifacts,
            'evidence': evidence,
            'created_at': now,
        }

    def save_report(
        self,
        report_id: str,
        job_id: str,
        issue_id: str,
        issue_type: str,
        diagnosis: dict[str, Any],
        html_report: str,
        requires_human: bool,
        rerun_count: int,
    ) -> None:
        now = _utc_now()
        with self.database.connect() as conn:
            exists = conn.execute('SELECT id, created_at FROM reports WHERE id = ?', (report_id,)).fetchone()
            if exists:
                conn.execute(
                    '''
                    UPDATE reports
                    SET issue_type = ?, requires_human = ?, diagnosis_json = ?, html_report = ?, rerun_count = ?, updated_at = ?
                    WHERE id = ?
                    ''',
                    (issue_type, int(requires_human), _json(diagnosis), html_report, rerun_count, now, report_id),
                )
            else:
                conn.execute(
                    '''
                    INSERT INTO reports (id, job_id, issue_id, issue_type, requires_human, diagnosis_json, html_report, rerun_count, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''',
                    (report_id, job_id, issue_id, issue_type, int(requires_human), _json(diagnosis), html_report, rerun_count, now, now),
                )
            conn.execute('UPDATE analysis_jobs SET status = ?, updated_at = ? WHERE id = ?', ('completed', now, job_id))

    def add_human_feedback(self, report_id: str, job_id: str, human_note: str) -> dict[str, Any]:
        feedback_id = str(uuid4())
        now = _utc_now()
        with self.database.connect() as conn:
            conn.execute(
                'INSERT INTO human_feedback (id, report_id, job_id, human_note, created_at) VALUES (?, ?, ?, ?, ?)',
                (feedback_id, report_id, job_id, human_note, now),
            )
        return {'id': feedback_id, 'report_id': report_id, 'job_id': job_id, 'human_note': human_note, 'created_at': now}

    def get_latest_feedback(self, report_id: str) -> dict[str, Any] | None:
        with self.database.connect() as conn:
            row = conn.execute(
                'SELECT * FROM human_feedback WHERE report_id = ? ORDER BY created_at DESC LIMIT 1',
                (report_id,),
            ).fetchone()
        return _row_to_feedback(row) if row else None

    def get_feedback(self, report_id: str) -> list[dict[str, Any]]:
        with self.database.connect() as conn:
            rows = conn.execute(
                'SELECT * FROM human_feedback WHERE report_id = ? ORDER BY created_at ASC',
                (report_id,),
            ).fetchall()
        return [_row_to_feedback(row) for row in rows]

    def get_report_record(self, report_id: str) -> dict[str, Any] | None:
        with self.database.connect() as conn:
            row = conn.execute('SELECT * FROM reports WHERE id = ?', (report_id,)).fetchone()
        return dict(row) if row else None

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        with self.database.connect() as conn:
            row = conn.execute('SELECT * FROM analysis_jobs WHERE id = ?', (job_id,)).fetchone()
        if not row:
            return None
        data = dict(row)
        data['metadata'] = json.loads(data.pop('metadata_json'))
        return data

    def get_primary_issue_for_job(self, job_id: str) -> dict[str, Any] | None:
        with self.database.connect() as conn:
            row = conn.execute(
                'SELECT * FROM issues WHERE job_id = ? ORDER BY created_at ASC LIMIT 1',
                (job_id,),
            ).fetchone()
        if not row:
            return None
        data = dict(row)
        data['raw'] = json.loads(data.pop('raw_json'))
        return data

    def update_job_status(self, job_id: str, status: str) -> None:
        with self.database.connect() as conn:
            conn.execute(
                'UPDATE analysis_jobs SET status = ?, updated_at = ? WHERE id = ?',
                (status, _utc_now(), job_id),
            )

    def get_agent_runs(self, job_id: str) -> list[dict[str, Any]]:
        with self.database.connect() as conn:
            rows = conn.execute(
                'SELECT * FROM agent_runs WHERE job_id = ? ORDER BY step_index ASC, created_at ASC',
                (job_id,),
            ).fetchall()
        return [_row_to_agent_run(row) for row in rows]

    def get_latest_agent_run(self, job_id: str, agent_name: str) -> dict[str, Any] | None:
        with self.database.connect() as conn:
            row = conn.execute(
                'SELECT * FROM agent_runs WHERE job_id = ? AND agent_name = ? ORDER BY step_index DESC LIMIT 1',
                (job_id, agent_name),
            ).fetchone()
        return _row_to_agent_run(row) if row else None


def _row_to_agent_run(row) -> dict[str, Any]:
    data = dict(row)
    data['artifacts'] = json.loads(data.pop('artifacts_json'))
    data['evidence'] = json.loads(data.pop('evidence_json'))
    return data


def _row_to_feedback(row) -> dict[str, Any]:
    return {
        'id': row['id'],
        'report_id': row['report_id'],
        'job_id': row['job_id'],
        'human_note': row['human_note'],
        'created_at': row['created_at'],
    }


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
