"""Agent-scoped memory boundary."""

from collections.abc import Sequence
from typing import Protocol

from antfarm.domain.json_values import JsonObject
from antfarm.domain.models import AgentId, MemoryItem, MemoryQuery


class MemoryStore(Protocol):
    def recall(self, agent_id: AgentId, query: MemoryQuery) -> Sequence[MemoryItem]: ...

    def append(self, agent_id: AgentId, items: Sequence[MemoryItem]) -> None: ...

    def snapshot(self) -> JsonObject: ...

    def restore(self, state: JsonObject) -> None: ...
