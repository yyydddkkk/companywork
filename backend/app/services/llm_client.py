from __future__ import annotations

from typing import Any

import httpx

from ..config import Settings


class LLMClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def is_enabled(self) -> bool:
        return bool(self.settings.llm_enabled and self.settings.llm_api_key)

    def complete(self, prompt: str) -> str | None:
        if not self.is_enabled():
            return None

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
            return data['choices'][0]['message']['content'].strip()
        except Exception:
            return None
