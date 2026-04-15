from __future__ import annotations

from typing import Any

from ..services.llm_client import LLMClient


class DebuggerAgent:
    name = 'Debugger'

    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self.llm_client = llm_client

    def run(self, issue: dict[str, Any], context: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
        text = f"{issue.get('title', '')} {issue.get('body', '')}".lower()
        human_note = (context.get('human_note') or '').strip()
        related_files = context.get('related_files', [])
        ambiguous_keywords = ('intermittent', 'sometimes', 'cannot reproduce', 'race condition', 'flaky', 'randomly')
        requires_human = any(keyword in text for keyword in ambiguous_keywords) and not human_note
        hypothesis = 'A state transition or stale client-side cache likely triggers the failure path.'
        if human_note:
            hypothesis = f'Human note narrows the trigger: {human_note}'
        elif related_files:
            hypothesis = f'Likely centered around {related_files[0]} with an unhandled edge case.'

        reproduce_steps = [
            'Install dependencies and start the application.',
            'Open the affected workflow described in the issue.',
            'Observe the failure state and capture logs.',
        ]
        if human_note:
            reproduce_steps.insert(2, f'Follow the human-provided trigger: {human_note}')

        reproduce_code = "def reproduce_issue():\n    session = boot_application()\n    session.open_target_view()\n    return session.capture_failure()"
        if human_note:
            reproduce_code = (
                'def reproduce_issue():\n'
                '    session = boot_application()\n'
                f"    session.apply_context({human_note!r})\n"
                '    session.open_target_view()\n'
                '    return session.capture_failure()'
            )

        fix_suggestions = [
            'Add a focused regression test for the reported trigger.',
            'Guard against missing state before rendering the failing path.',
            'Log the triggering context so future triage has exact reproduction evidence.',
        ]
        human_reason = None
        if requires_human:
            human_reason = 'The issue description is ambiguous and does not contain deterministic reproduction detail.'
            reproduce_steps = ['A precise trigger is missing. Capture a deterministic sequence from a human operator.']
            reproduce_code = ''
            fix_suggestions = ['Ask for exact trigger conditions, timing, and environment details before changing code.']

        llm_note = None
        if self.llm_client and not requires_human:
            llm_note = self.llm_client.complete(
                'Produce a concise debugging hypothesis and one fix suggestion for this issue.\n\n'
                f"Issue: {issue.get('title', '')}\n{issue.get('body', '')}\nContext: {context}"
            )
        if llm_note:
            fix_suggestions.insert(0, llm_note[:240])

        status = 'requires_human' if requires_human else 'ok'
        return {
            'status': status,
            'summary': 'Debugger produced a reproduction plan.' if not requires_human else 'Debugger needs human clarification before continuing.',
            'artifacts': {
                'root_cause_hypothesis': hypothesis,
                'reproduce_steps': reproduce_steps,
                'reproduce_code': reproduce_code,
                'fix_suggestions': fix_suggestions,
                'requires_human': requires_human,
                'human_reason': human_reason,
            },
            'evidence': [
                {'source': 'issue', 'excerpt': issue.get('body', '')[:220]},
                {'source': 'human_feedback', 'excerpt': human_note[:220]} if human_note else {'source': 'research', 'excerpt': context.get('research_summary', '')[:220]},
            ],
        }
