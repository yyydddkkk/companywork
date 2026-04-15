from __future__ import annotations

from typing import Any

from ..services.llm_client import LLMClient


class TriagerAgent:
    name = 'Triager'

    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self.llm_client = llm_client

    def run(self, issue: dict[str, Any], context: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
        text = f"{issue.get('title', '')} {issue.get('body', '')}".lower()
        issue_type = 'Feature'
        confidence = 0.68
        rationale = 'Matched general product enhancement language.'

        bug_keywords = ('bug', 'crash', 'error', 'exception', 'traceback', 'freeze', 'fail', 'broken')
        docs_keywords = ('doc', 'docs', 'readme', 'guide', 'tutorial', 'documentation')
        question_keywords = ('how do', 'how to', 'question', 'why does', 'can i')

        if any(keyword in text for keyword in bug_keywords):
            issue_type = 'Bug'
            confidence = 0.91
            rationale = 'Detected failure-oriented keywords in the issue title/body.'
        elif any(keyword in text for keyword in docs_keywords):
            issue_type = 'Docs'
            confidence = 0.89
            rationale = 'Detected documentation-oriented keywords in the issue content.'
        elif any(keyword in text for keyword in question_keywords):
            issue_type = 'Question'
            confidence = 0.77
            rationale = 'Detected inquiry-oriented phrasing.'

        llm_note = None
        if self.llm_client:
            llm_note = self.llm_client.complete(
                f"Classify this GitHub issue into Bug, Feature, Docs, or Question and explain briefly:\n\n{issue.get('title', '')}\n\n{issue.get('body', '')}"
            )
        if llm_note:
            rationale = f'{rationale} LLM refinement: {llm_note[:200]}'

        return {
            'status': 'ok',
            'summary': f'Classified issue as {issue_type}.',
            'artifacts': {
                'issue_type': issue_type,
                'confidence': confidence,
                'rationale': rationale,
            },
            'evidence': [
                {
                    'source': 'issue',
                    'excerpt': issue.get('title', '')[:160] or issue.get('body', '')[:160],
                }
            ],
        }
