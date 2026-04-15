from __future__ import annotations

import json
import re
from typing import Any

from ..services.llm_client import LLMClient


class DebuggerAgent:
    name = 'Debugger'

    def __init__(self, llm_client: LLMClient | None = None, require_llm: bool = True) -> None:
        self.llm_client = llm_client
        self.require_llm = require_llm

    def run(self, issue: dict[str, Any], context: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
        body = issue.get('body', '') or ''
        text = f"{issue.get('title', '')} {body}".lower()
        human_note = (context.get('human_note') or '').strip()
        related_files = context.get('related_files', [])
        extracted = _extract_issue_debug_payload(body)
        ambiguous_keywords = ('intermittent', 'sometimes', 'cannot reproduce', 'race condition', 'flaky', 'randomly')
        has_issue_repro = bool(extracted['reproduce_code'] or extracted['reproduce_steps'])
        requires_human = any(keyword in text for keyword in ambiguous_keywords) and not human_note and not has_issue_repro
        hypothesis = 'A state transition or stale client-side cache likely triggers the failure path.'
        if human_note:
            hypothesis = f'Human note narrows the trigger: {human_note}'
        elif related_files:
            hypothesis = f'Likely centered around {related_files[0]} with an unhandled edge case.'

        reproduce_steps = extracted['reproduce_steps'] or [
            'Install dependencies and start the application.',
            'Open the affected workflow described in the issue.',
            'Observe the failure state and capture logs.',
        ]
        if human_note:
            reproduce_steps.insert(2, f'Follow the human-provided trigger: {human_note}')

        reproduce_code = extracted['reproduce_code'] or (
            "def reproduce_issue():\n"
            "    session = boot_application()\n"
            "    session.open_target_view()\n"
            "    return session.capture_failure()"
        )
        if human_note:
            reproduce_code = (
                'def reproduce_issue():\n'
                '    session = boot_application()\n'
                f"    session.apply_context({human_note!r})\n"
                '    session.open_target_view()\n'
                '    return session.capture_failure()'
            )

        fix_suggestions = extracted['fix_suggestions'] or [
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

        llm_enabled = bool(self.llm_client and self.llm_client.is_enabled())
        llm_used = False
        llm_error_kind = None
        llm_error_message = None
        if self.llm_client and not requires_human:
            llm_result = self.llm_client.complete_with_meta(
                'Return strict JSON with keys root_cause_hypothesis (string), reproduce_steps (string[]), '
                'reproduce_code (string), fix_suggestions (string[]). Keep it concise and actionable.\n\n'
                f"Issue: {issue.get('title', '')}\n{body}\n\nContext: {context}\n\n"
                f"Current draft: root_cause_hypothesis={hypothesis}, reproduce_steps={reproduce_steps}, "
                f"reproduce_code={reproduce_code}, fix_suggestions={fix_suggestions}"
            )
            if llm_result.ok and llm_result.content:
                parsed = _parse_llm_json(llm_result.content)
                if parsed:
                    llm_used = True
                    hypothesis = parsed.get('root_cause_hypothesis') or hypothesis
                    reproduce_steps = _coerce_list(parsed.get('reproduce_steps')) or reproduce_steps
                    reproduce_code = _coerce_string(parsed.get('reproduce_code')) or reproduce_code
                    llm_fixes = _coerce_list(parsed.get('fix_suggestions'))
                    if llm_fixes:
                        fix_suggestions = llm_fixes
                else:
                    llm_error_kind = 'invalid_json'
                    llm_error_message = 'LLM returned non-JSON content for Debugger.'
            else:
                llm_error_kind = llm_result.error_kind or 'llm_error'
                llm_error_message = llm_result.error_message or 'LLM request failed for Debugger.'

        if not requires_human and self.require_llm:
            if not llm_enabled:
                requires_human = True
                human_reason = 'Debugger requires LLM, but LLM is disabled or API key is missing.'
                llm_error_kind = llm_error_kind or 'disabled'
                llm_error_message = llm_error_message or human_reason
            elif not llm_used:
                requires_human = True
                human_reason = (
                    f"Debugger LLM is required but failed ({llm_error_kind or 'unknown'}). "
                    'Please retry or provide human feedback to rerun.'
                )
                reproduce_code = ''
                fix_suggestions = ['LLM synthesis failed. Provide additional context and rerun Debugger.']

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
                'llm_enabled': llm_enabled,
                'llm_used': llm_used,
                'llm_error_kind': llm_error_kind,
                'llm_error_message': llm_error_message,
            },
            'evidence': [
                {'source': 'issue', 'excerpt': issue.get('body', '')[:220]},
                {'source': 'human_feedback', 'excerpt': human_note[:220]} if human_note else {'source': 'research', 'excerpt': context.get('research_summary', '')[:220]},
            ],
        }


def _extract_issue_debug_payload(body: str) -> dict[str, Any]:
    reproduction = _extract_section(body, 'reproduction')
    suggested_fix = _extract_section(body, 'suggested fix')
    reproduce_code = _first_code_block(reproduction) if reproduction else ''
    reproduce_steps = _extract_steps_from_shell_block(reproduce_code) if reproduce_code else []
    fix_suggestions = _extract_fix_suggestions(suggested_fix)
    return {
        'reproduce_code': reproduce_code,
        'reproduce_steps': reproduce_steps,
        'fix_suggestions': fix_suggestions,
    }


def _extract_section(text: str, heading: str) -> str:
    pattern = re.compile(rf'(?ims)^##\s*{re.escape(heading)}\s*(.*?)(?=^##\s|\Z)')
    match = pattern.search(text or '')
    return match.group(1).strip() if match else ''


def _first_code_block(text: str) -> str:
    match = re.search(r'```(?:\w+)?\n(.*?)```', text or '', re.S)
    return match.group(1).strip() if match else ''


def _extract_steps_from_shell_block(code: str) -> list[str]:
    steps: list[str] = []
    for raw_line in (code or '').splitlines():
        line = raw_line.strip()
        if not line or line.startswith('#'):
            continue
        steps.append(line)
    return steps[:8]


def _extract_fix_suggestions(text: str) -> list[str]:
    if not text:
        return []
    suggestions: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith(('-', '*')):
            suggestions.append(line[1:].strip())
        elif line.startswith('```'):
            break
        else:
            suggestions.append(line)
    return [item for item in suggestions if item][:4]


def _parse_llm_json(raw: str) -> dict[str, Any] | None:
    try:
        return json.loads(raw)
    except Exception:
        pass
    match = re.search(r'\{.*\}', raw, re.S)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except Exception:
        return None


def _coerce_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _coerce_string(value: Any) -> str:
    return str(value).strip() if value is not None else ''
