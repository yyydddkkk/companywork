from __future__ import annotations

import csv
import io
import json
from typing import Any

import httpx

from ..config import Settings
from ..schemas import AnalyzeRequest


class IssueLoader:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def load_from_request(self, payload: AnalyzeRequest) -> tuple[str, list[dict[str, Any]], dict[str, Any]]:
        if payload.source == 'inline':
            issues = [issue.model_dump() for issue in payload.issues]
            if not issues:
                raise ValueError('Inline analysis requires at least one issue.')
            return 'inline', issues, {'mode': 'inline'}

        if not payload.github:
            raise ValueError('GitHub analysis requires a github object.')
        github = payload.github
        issue = github.model_dump()
        if not issue.get('title') and self.settings.enable_github_fetch:
            issue = self._fetch_github_issue(issue)
        if not issue.get('title'):
            raise ValueError('GitHub analysis requires title/body in payload unless ENABLE_GITHUB_FETCH=true.')
        normalized = {
            'external_id': str(issue['issue_number']),
            'title': issue.get('title', ''),
            'body': issue.get('body', ''),
            'url': issue.get('url') or f"https://github.com/{issue['owner']}/{issue['repo']}/issues/{issue['issue_number']}",
        }
        return 'github', [normalized], {
            'mode': 'github',
            'owner': issue['owner'],
            'repo': issue['repo'],
            'issue_number': issue['issue_number'],
        }

    def load_from_upload(self, filename: str, raw_bytes: bytes) -> tuple[str, list[dict[str, Any]], dict[str, Any]]:
        suffix = filename.lower().rsplit('.', 1)[-1] if '.' in filename else ''
        if suffix == 'json':
            data = json.loads(raw_bytes.decode('utf-8'))
            issues = data if isinstance(data, list) else data.get('issues', [])
            return 'upload', [self._normalize_uploaded_issue(issue) for issue in issues], {'mode': 'upload-json', 'filename': filename}
        if suffix == 'csv':
            reader = csv.DictReader(io.StringIO(raw_bytes.decode('utf-8')))
            return 'upload', [self._normalize_uploaded_issue(row) for row in reader], {'mode': 'upload-csv', 'filename': filename}
        raise ValueError('Upload only supports .json or .csv files.')

    def _normalize_uploaded_issue(self, issue: dict[str, Any]) -> dict[str, Any]:
        return {
            'external_id': issue.get('external_id') or issue.get('id'),
            'title': (issue.get('title') or '').strip(),
            'body': (issue.get('body') or '').strip(),
            'url': issue.get('url'),
        }

    def _fetch_github_issue(self, issue: dict[str, Any]) -> dict[str, Any]:
        headers = {'Accept': 'application/vnd.github+json'}
        if self.settings.github_token:
            headers['Authorization'] = f"Bearer {self.settings.github_token}"
        response = httpx.get(
            f"https://api.github.com/repos/{issue['owner']}/{issue['repo']}/issues/{issue['issue_number']}",
            headers=headers,
            timeout=15,
        )
        response.raise_for_status()
        payload = response.json()
        issue['title'] = payload.get('title', '')
        issue['body'] = payload.get('body', '')
        issue['url'] = payload.get('html_url')
        return issue
