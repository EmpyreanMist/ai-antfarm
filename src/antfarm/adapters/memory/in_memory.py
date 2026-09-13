"""Bounded process-local memory."""

from collections.abc import Sequence

from antfarm.domain.models import AgentId, MemoryItem


class InMemoryMemoryStore:
    def __init__(self) -> None:
        self._items: dict[AgentId, list[MemoryItem]] = {}

    def recall(self, agent_id: AgentId, limit: int) -> Sequence[MemoryItem]:
        if limit < 0:
            raise ValueError("memory recall limit must not be negative")
        if limit == 0:
            return ()
        return tuple(self._items.get(agent_id, ())[-limit:])

    def append(self, agent_id: AgentId, items: Sequence[MemoryItem]) -> None:
        self._items.setdefault(agent_id, []).extend(items)
