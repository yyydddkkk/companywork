from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class IssuePayload(BaseModel):
    external_id: str | None = None
    title: str
    body: str = ''
    url: str | None = None


class GitHubIssueSource(BaseModel):
    owner: str
    repo: str
    issue_number: int
    title: str | None = None
    body: str | None = None
    url: str | None = None


class AnalyzeRequest(BaseModel):
    source: Literal['inline', 'github']
    issues: list[IssuePayload] = Field(default_factory=list)
    github: GitHubIssueSource | None = None


class HumanFeedbackRequest(BaseModel):
    human_note: str = Field(min_length=3)
