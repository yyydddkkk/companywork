from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import os
from dotenv import load_dotenv


@dataclass(slots=True)
class Settings:
    database_path: str
    llm_enabled: bool = False
    llm_base_url: str = 'https://api.openai.com/v1'
    llm_model: str = 'gpt-4.1-mini'
    llm_api_key: str | None = None
    debugger_require_llm: bool = True
    enable_github_fetch: bool = False
    github_token: str | None = None
    project_root: str = ''


TRUE_VALUES = {'1', 'true', 'yes', 'on'}


def _as_bool(value: str | bool | None, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    return value.strip().lower() in TRUE_VALUES


def load_settings(overrides: dict[str, Any] | None = None) -> Settings:
    repo_root = Path(__file__).resolve().parents[2]
    load_dotenv(repo_root / '.env')
    env = {
        'database_path': os.getenv('DATABASE_PATH', str(repo_root / 'data' / 'issue_multi_agent.db')),
        'llm_enabled': _as_bool(os.getenv('LLM_ENABLED'), False),
        'llm_base_url': os.getenv('LLM_BASE_URL', 'https://api.openai.com/v1'),
        'llm_model': os.getenv('LLM_MODEL', 'gpt-4.1-mini'),
        'llm_api_key': os.getenv('LLM_API_KEY'),
        'debugger_require_llm': _as_bool(os.getenv('DEBUGGER_REQUIRE_LLM'), True),
        'enable_github_fetch': _as_bool(os.getenv('ENABLE_GITHUB_FETCH'), False),
        'github_token': os.getenv('GITHUB_TOKEN'),
        'project_root': os.getenv('PROJECT_ROOT', str(repo_root.parent)),
    }
    if overrides:
        env.update(overrides)
    return Settings(**env)
