from __future__ import annotations

from pathlib import Path
from typing import Any

from ..services.llm_client import LLMClient


class DocumenterAgent:
    name = 'Documenter'

    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self.llm_client = llm_client

    def run(self, issue: dict[str, Any], context: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
        doc_candidates = context.get('doc_snippets', [])
        related_files = context.get('related_files', [])
        doc_targets = [item['path'] for item in doc_candidates] or [path for path in related_files if Path(path).suffix == '.md']
        if not doc_targets:
            doc_targets = ['README.md']

        suggested_updates = [
            'Update setup steps to reflect the current runtime and command examples.',
            'Add a short troubleshooting subsection for the reported confusion point.',
        ]
        gap_analysis = 'The available documentation does not fully match the issue description or current workflow.'
        llm_note = None
        if self.llm_client:
            llm_note = self.llm_client.complete(
                'Summarize the documentation gap and one suggested update in 2 sentences.\n\n'
                f"Issue: {issue.get('title', '')}\n{issue.get('body', '')}\nContext: {context}"
            )
        if llm_note:
            gap_analysis = llm_note[:320]

        return {
            'status': 'ok',
            'summary': 'Documenter identified likely documentation updates.',
            'artifacts': {
                'doc_targets': doc_targets,
                'gap_analysis': gap_analysis,
                'suggested_updates': suggested_updates,
            },
            'evidence': [
                {'source': target, 'excerpt': context.get('research_summary', '')[:220]}
                for target in doc_targets[:3]
            ],
        }
