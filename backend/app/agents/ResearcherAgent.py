from __future__ import annotations

from pathlib import Path
from typing import Any
import re

from ..services.github_repo_searcher import GitHubRepoSearcher, extract_issue_hints
from ..services.llm_client import LLMClient


STOP_WORDS = {
    'the', 'and', 'for', 'with', 'that', 'when', 'from', 'after', 'need', 'issue', 'page', 'user',
    'users', 'still', 'only', 'this', 'does', 'into', 'have', 'long', 'period', 'trace', 'export'
}
TEXT_SUFFIXES = {'.py', '.md', '.tsx', '.ts', '.js', '.jsx', '.json', '.yml', '.yaml', '.csv'}


class ResearcherAgent:
    name = 'Researcher'

    def __init__(
        self,
        project_root: str,
        llm_client: LLMClient | None = None,
        github_searcher: GitHubRepoSearcher | None = None,
    ) -> None:
        self.project_root = Path(project_root)
        self.llm_client = llm_client
        self.github_searcher = github_searcher or GitHubRepoSearcher()

    def run(self, issue: dict[str, Any], context: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
        tokens = self._keywords(issue)
        mode = (context.get('mode') or '').lower()
        owner = str(context.get('owner') or '')
        repo = str(context.get('repo') or '')
        source_scope = 'local_project'
        source_repo = None
        degraded_reason = None

        matches: list[dict[str, Any]] = []
        if mode == 'github' and owner and repo:
            source_scope = 'github_repo'
            source_repo = f'{owner}/{repo}'
            matches, degraded_reason = self.github_searcher.search(owner, repo, tokens, max_files=5)
            if not matches:
                source_scope = 'issue_only_fallback'
                hints = extract_issue_hints(issue)
                matches = [{'path': hint, 'score': 1, 'excerpt': 'Extracted from issue content.'} for hint in hints]
                if not degraded_reason:
                    degraded_reason = 'No repository evidence matched this issue; fell back to issue text only.'
        else:
            for path in self._iter_files():
                try:
                    text = path.read_text(encoding='utf-8')
                except UnicodeDecodeError:
                    continue
                lowered = text.lower()
                score = sum(lowered.count(token) + str(path).lower().count(token) for token in tokens)
                if score <= 0:
                    continue
                excerpt = self._extract_excerpt(text, tokens)
                matches.append(
                    {
                        'path': str(path.relative_to(self.project_root)),
                        'score': score,
                        'excerpt': excerpt,
                    }
                )

        matches.sort(key=lambda item: (-item['score'], item['path']))
        top_matches = matches[:5]
        related_files = [item['path'] for item in top_matches]
        code_snippets = [item for item in top_matches if Path(item['path']).suffix != '.md'][:3]
        doc_snippets = [item for item in top_matches if Path(item['path']).suffix == '.md'][:3]
        research_summary = 'No strong repository matches found; fall back to issue text and defaults.'
        if top_matches:
            research_summary = 'Top evidence came from ' + ', '.join(item['path'] for item in top_matches[:3]) + '.'
        if degraded_reason:
            research_summary = f'{research_summary} Degraded mode: {degraded_reason}'

        llm_enabled = bool(self.llm_client and self.llm_client.is_enabled())
        llm_note = None
        if self.llm_client and top_matches:
            llm_note = self.llm_client.complete(
                'Summarize the likely relevant code/docs for this issue in 2 short sentences.\n\n'
                f"Issue: {issue.get('title', '')}\n{issue.get('body', '')}\n\n"
                f"Matches: {top_matches}"
            )
        if llm_note:
            research_summary = llm_note[:400]

        evidence = [
            {'source': item['path'], 'excerpt': item['excerpt']}
            for item in top_matches[:3]
        ]
        return {
            'status': 'ok',
            'summary': research_summary,
            'artifacts': {
                'related_files': related_files,
                'code_snippets': code_snippets,
                'doc_snippets': doc_snippets,
                'research_summary': research_summary,
                'llm_enabled': llm_enabled,
                'llm_used': bool(llm_note),
                'source_scope': source_scope,
                'source_repo': source_repo,
                'degraded_reason': degraded_reason,
            },
            'evidence': evidence,
        }

    def _keywords(self, issue: dict[str, Any]) -> list[str]:
        raw_tokens = re.findall(r'[a-zA-Z]{4,}', f"{issue.get('title', '')} {issue.get('body', '')}".lower())
        tokens = [token for token in raw_tokens if token not in STOP_WORDS]
        return list(dict.fromkeys(tokens[:8] or ['issue', 'report']))

    def _iter_files(self):
        ignored = {'.git', '.venv', 'node_modules', 'dist', 'build', '__pycache__'}
        for path in self.project_root.rglob('*'):
            if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
                continue
            if any(part in ignored for part in path.parts):
                continue
            yield path

    def _extract_excerpt(self, text: str, tokens: list[str]) -> str:
        lowered = text.lower()
        for token in tokens:
            idx = lowered.find(token)
            if idx >= 0:
                start = max(0, idx - 60)
                end = min(len(text), idx + 140)
                return text[start:end].replace('\n', ' ').strip()
        return text[:180].replace('\n', ' ').strip()
