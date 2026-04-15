from __future__ import annotations

import base64
import re
from typing import Any

import httpx


class GitHubRepoSearcher:
    def __init__(self, github_token: str | None = None) -> None:
        self.github_token = github_token

    def search(
        self,
        owner: str,
        repo: str,
        tokens: list[str],
        max_files: int = 5,
    ) -> tuple[list[dict[str, Any]], str | None]:
        picked_tokens = [token for token in tokens if token][:5]
        if not picked_tokens:
            return [], 'No searchable tokens were extracted from the issue.'

        try:
            ranked_paths = self._search_paths(owner, repo, picked_tokens)
            if not ranked_paths:
                return [], 'GitHub code search returned no matching files for this issue.'
            matches = self._fetch_file_snippets(owner, repo, ranked_paths, picked_tokens, max_files=max_files)
            if not matches:
                return [], 'GitHub file content fetch returned no readable text files.'
            return matches, None
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            if status in (401, 403):
                return [], 'GitHub API authorization/rate limit blocked repository search.'
            if status == 404:
                return [], 'GitHub repository or search endpoint was not found.'
            return [], f'GitHub API returned HTTP {status} while searching repository context.'
        except httpx.HTTPError:
            return [], 'Network error occurred while querying GitHub repository context.'

    def _search_paths(self, owner: str, repo: str, tokens: list[str]) -> dict[str, int]:
        scores: dict[str, int] = {}
        headers = self._headers()
        with httpx.Client(timeout=12) as client:
            for token in tokens:
                query = f"{token} repo:{owner}/{repo} in:file"
                response = client.get(
                    'https://api.github.com/search/code',
                    params={'q': query, 'per_page': 10},
                    headers=headers,
                )
                response.raise_for_status()
                payload = response.json()
                for item in payload.get('items', []):
                    path = item.get('path')
                    if not path:
                        continue
                    scores[path] = scores.get(path, 0) + 1
        return scores

    def _fetch_file_snippets(
        self,
        owner: str,
        repo: str,
        ranked_paths: dict[str, int],
        tokens: list[str],
        max_files: int,
    ) -> list[dict[str, Any]]:
        sorted_paths = sorted(ranked_paths.items(), key=lambda item: (-item[1], item[0]))
        chosen = [path for path, _ in sorted_paths[: max_files * 2]]
        headers = self._headers()
        matches: list[dict[str, Any]] = []
        with httpx.Client(timeout=12) as client:
            for path in chosen:
                response = client.get(
                    f'https://api.github.com/repos/{owner}/{repo}/contents/{path}',
                    headers=headers,
                )
                if response.status_code >= 400:
                    continue
                payload = response.json()
                raw = payload.get('content')
                encoding = payload.get('encoding')
                if not raw or encoding != 'base64':
                    continue
                try:
                    text = base64.b64decode(raw).decode('utf-8')
                except Exception:
                    continue
                excerpt = _extract_excerpt(text, tokens)
                score = ranked_paths.get(path, 0) + _token_hit_score(path, text, tokens)
                matches.append({'path': path, 'score': score, 'excerpt': excerpt})
                if len(matches) >= max_files:
                    break
        matches.sort(key=lambda item: (-item['score'], item['path']))
        return matches[:max_files]

    def _headers(self) -> dict[str, str]:
        headers = {'Accept': 'application/vnd.github+json'}
        if self.github_token:
            headers['Authorization'] = f'Bearer {self.github_token}'
        return headers


def _extract_excerpt(text: str, tokens: list[str]) -> str:
    lowered = text.lower()
    for token in tokens:
        idx = lowered.find(token.lower())
        if idx >= 0:
            start = max(0, idx - 80)
            end = min(len(text), idx + 180)
            return text[start:end].replace('\n', ' ').strip()
    return text[:200].replace('\n', ' ').strip()


def _token_hit_score(path: str, text: str, tokens: list[str]) -> int:
    lowered_path = path.lower()
    lowered_text = text.lower()
    score = 0
    for token in tokens:
        token_lower = token.lower()
        score += lowered_path.count(token_lower)
        score += lowered_text.count(token_lower)
    return score


def extract_issue_hints(issue: dict[str, Any], max_items: int = 5) -> list[str]:
    body = f"{issue.get('title', '')}\n{issue.get('body', '')}"
    hints: list[str] = []
    backtick_values = re.findall(r'`([^`]+)`', body)
    for item in backtick_values:
        value = item.strip()
        if len(value) < 3:
            continue
        if re.search(r'\s', value):
            continue
        hints.append(value)
    paths = re.findall(r'([A-Za-z0-9_./-]+\.(?:py|md|ts|tsx|js|jsx|json|yml|yaml))', body)
    hints.extend(paths)
    normalized: list[str] = []
    for hint in hints:
        if hint not in normalized:
            normalized.append(hint)
        if len(normalized) >= max_items:
            break
    return normalized
