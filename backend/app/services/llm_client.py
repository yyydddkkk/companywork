from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from ..config import Settings


class LLMClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def is_enabled(self) -> bool:
        return bool(self.settings.llm_enabled and self.settings.llm_api_key)

    def complete(self, prompt: str) -> str | None:
        result = self.complete_with_meta(prompt)
        return result.content if result.ok else None

    def complete_with_meta(self, prompt: str) -> 'LLMResult':
        if not self.is_enabled():
            return LLMResult(ok=False, content=None, error_kind='disabled', error_message='LLM is disabled or API key is missing.')

        headers = {
            'Authorization': f'Bearer {self.settings.llm_api_key}',
            'Content-Type': 'application/json',
        }
        payload: dict[str, Any] = {
            'model': self.settings.llm_model,
            'messages': [
                {'role': 'system', 'content': 'You are a precise issue analysis assistant.'},
                {'role': 'user', 'content': prompt},
            ],
            'temperature': 0.2,
        }

        try:
            response = httpx.post(
                f"{self.settings.llm_base_url.rstrip('/')}/chat/completions",
                headers=headers,
                json=payload,
                timeout=15,
            )
            response.raise_for_status()
            data = response.json()
            content = _extract_content(data)
            if not content:
                return LLMResult(
                    ok=False,
                    content=None,
                    error_kind='empty_content',
                    error_message='Provider returned 200 but no assistant content.',
                    raw_excerpt=str(data)[:500],
                )
            return LLMResult(ok=True, content=content)
        except httpx.TimeoutException:
            return LLMResult(ok=False, content=None, error_kind='timeout', error_message='LLM request timed out.')
        except httpx.HTTPStatusError as exc:
            return LLMResult(
                ok=False,
                content=None,
                error_kind=f'http_{exc.response.status_code}',
                error_message=f'LLM HTTP error {exc.response.status_code}.',
            )
        except Exception as exc:
            return LLMResult(
                ok=False,
                content=None,
                error_kind='exception',
                error_message=f'LLM exception: {exc.__class__.__name__}',
            )


@dataclass(slots=True)
class LLMResult:
    ok: bool
    content: str | None
    error_kind: str | None = None
    error_message: str | None = None
    raw_excerpt: str | None = None


def _extract_content(data: dict[str, Any]) -> str | None:
    choices = data.get('choices')
    if not isinstance(choices, list) or not choices:
        return None
    message = choices[0].get('message')
    if not isinstance(message, dict):
        return None
    content = message.get('content')
    if isinstance(content, str):
        stripped = content.strip()
        return stripped or None
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict) and isinstance(item.get('text'), str):
                text = item['text'].strip()
                if text:
                    parts.append(text)
        joined = '\n'.join(parts).strip()
        return joined or None
    return None
