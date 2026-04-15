from __future__ import annotations

import logging
from typing import Any
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from ..agents.DebuggerAgent import DebuggerAgent
from ..agents.DocumenterAgent import DocumenterAgent
from ..agents.ResearcherAgent import ResearcherAgent
from ..agents.TriagerAgent import TriagerAgent
from ..repositories import Repository
from .github_repo_searcher import GitHubRepoSearcher
from .llm_client import LLMClient


class AnalyzeGraphState(TypedDict, total=False):
    job_id: str
    issue: dict[str, Any]
    context: dict[str, Any]
    branch_result: dict[str, Any] | None


class RerunGraphState(TypedDict, total=False):
    job_id: str
    issue: dict[str, Any]
    context: dict[str, Any]
    result: dict[str, Any]
    trace_entry: dict[str, Any]


class Orchestrator:
    def __init__(
        self,
        repository: Repository,
        project_root: str,
        llm_client: LLMClient | None = None,
        github_token: str | None = None,
        debugger_require_llm: bool = True,
    ) -> None:
        self.repository = repository
        self.logger = logging.getLogger(__name__)
        self.triager = TriagerAgent(llm_client)
        self.researcher = ResearcherAgent(project_root, llm_client, GitHubRepoSearcher(github_token))
        self.debugger = DebuggerAgent(llm_client, require_llm=debugger_require_llm)
        self.documenter = DocumenterAgent(llm_client)
        self.analysis_graph = self._build_analysis_graph()
        self.debugger_rerun_graph = self._build_debugger_rerun_graph()

    def analyze(self, job_id: str, issue: dict[str, Any], seed_context: dict[str, Any] | None = None) -> dict[str, Any]:
        result = self.analysis_graph.invoke(
            {'job_id': job_id, 'issue': issue, 'context': dict(seed_context or {}), 'branch_result': None}
        )
        trace = self.repository.get_agent_runs(job_id)
        return {
            'trace': trace,
            'context': result.get('context', {}),
            'branch_result': result.get('branch_result'),
        }

    def rerun_debugger(self, job_id: str, issue: dict[str, Any], human_note: str) -> dict[str, Any]:
        triage_run = self.repository.get_latest_agent_run(job_id, self.triager.name)
        research_run = self.repository.get_latest_agent_run(job_id, self.researcher.name)
        if not triage_run or triage_run['artifacts'].get('issue_type') != 'Bug':
            raise ValueError('Debugger rerun is only available for bug reports.')
        context = {}
        context.update(triage_run['artifacts'])
        if research_run:
            context.update(research_run['artifacts'])
        context['human_note'] = human_note
        rerun_state = self.debugger_rerun_graph.invoke({'job_id': job_id, 'issue': issue, 'context': context})
        return {
            'trace_entry': rerun_state['trace_entry'],
            'context': rerun_state['context'],
            'result': rerun_state['result'],
        }

    def _build_analysis_graph(self):
        graph = StateGraph(AnalyzeGraphState)
        graph.add_node('triager', self._triage_node)
        graph.add_node('researcher', self._research_node)
        graph.add_node('debugger', self._debugger_node)
        graph.add_node('documenter', self._documenter_node)

        graph.add_edge(START, 'triager')
        graph.add_edge('triager', 'researcher')
        graph.add_conditional_edges(
            'researcher',
            self._route_after_research,
            {'debugger': 'debugger', 'documenter': 'documenter', 'end': END},
        )
        graph.add_edge('debugger', END)
        graph.add_edge('documenter', END)
        return graph.compile()

    def _build_debugger_rerun_graph(self):
        graph = StateGraph(RerunGraphState)
        graph.add_node('debugger', self._debugger_rerun_node)
        graph.add_edge(START, 'debugger')
        graph.add_edge('debugger', END)
        return graph.compile()

    def _triage_node(self, state: AnalyzeGraphState) -> AnalyzeGraphState:
        self.logger.info('job=%s stage=triager start', state['job_id'])
        self.repository.update_job_status(state['job_id'], 'triager_running')
        result = self.triager.run(state['issue'], state.get('context', {}), {})
        self.repository.add_agent_run(
            state['job_id'],
            self.triager.name,
            result['status'],
            result['summary'],
            result['artifacts'],
            result['evidence'],
        )
        context = dict(state.get('context', {}))
        context.update(result['artifacts'])
        self.logger.info('job=%s stage=triager done status=%s', state['job_id'], result['status'])
        return {'context': context}

    def _research_node(self, state: AnalyzeGraphState) -> AnalyzeGraphState:
        self.logger.info('job=%s stage=researcher start', state['job_id'])
        self.repository.update_job_status(state['job_id'], 'researcher_running')
        result = self.researcher.run(state['issue'], state.get('context', {}), {})
        self.repository.add_agent_run(
            state['job_id'],
            self.researcher.name,
            result['status'],
            result['summary'],
            result['artifacts'],
            result['evidence'],
        )
        context = dict(state.get('context', {}))
        context.update(result['artifacts'])
        self.logger.info('job=%s stage=researcher done status=%s', state['job_id'], result['status'])
        return {'context': context}

    def _debugger_node(self, state: AnalyzeGraphState) -> AnalyzeGraphState:
        self.logger.info('job=%s stage=debugger start', state['job_id'])
        self.repository.update_job_status(state['job_id'], 'debugger_running')
        result = self.debugger.run(state['issue'], state.get('context', {}), {})
        self.repository.add_agent_run(
            state['job_id'],
            self.debugger.name,
            result['status'],
            result['summary'],
            result['artifacts'],
            result['evidence'],
        )
        context = dict(state.get('context', {}))
        context.update(result['artifacts'])
        self.logger.info(
            'job=%s stage=debugger done status=%s llm_used=%s llm_error=%s',
            state['job_id'],
            result['status'],
            result['artifacts'].get('llm_used'),
            result['artifacts'].get('llm_error_kind'),
        )
        return {'context': context, 'branch_result': result}

    def _documenter_node(self, state: AnalyzeGraphState) -> AnalyzeGraphState:
        self.logger.info('job=%s stage=documenter start', state['job_id'])
        self.repository.update_job_status(state['job_id'], 'documenter_running')
        result = self.documenter.run(state['issue'], state.get('context', {}), {})
        self.repository.add_agent_run(
            state['job_id'],
            self.documenter.name,
            result['status'],
            result['summary'],
            result['artifacts'],
            result['evidence'],
        )
        context = dict(state.get('context', {}))
        context.update(result['artifacts'])
        self.logger.info('job=%s stage=documenter done status=%s', state['job_id'], result['status'])
        return {'context': context, 'branch_result': result}

    def _debugger_rerun_node(self, state: RerunGraphState) -> RerunGraphState:
        result = self.debugger.run(state['issue'], state.get('context', {}), {})
        stored = self.repository.add_agent_run(
            state['job_id'],
            self.debugger.name,
            result['status'],
            result['summary'],
            result['artifacts'],
            result['evidence'],
        )
        context = dict(state.get('context', {}))
        context.update(result['artifacts'])
        return {'context': context, 'result': result, 'trace_entry': stored}

    def _route_after_research(self, state: AnalyzeGraphState) -> str:
        issue_type = state.get('context', {}).get('issue_type')
        if issue_type == 'Bug':
            return 'debugger'
        if issue_type == 'Docs':
            return 'documenter'
        return 'end'
