"""Agent-scoped memory boundary."""

from collections.abc import Sequence
from typing import Protocol

from antfarm.domain.models import AgentId, MemoryItem


class MemoryStore(Protocol):
    def recall(self, agent_id: AgentId, limit: int) -> Sequence[MemoryItem]: ...

    def append(self, agent_id: AgentId, items: Sequence[MemoryItem]) -> None: ...
