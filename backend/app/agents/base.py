from __future__ import annotations

from typing import Any, Protocol


AgentResult = dict[str, Any]


class Agent(Protocol):
    name: str

    def run(self, issue: dict[str, Any], context: dict[str, Any], config: dict[str, Any]) -> AgentResult:
        ...
