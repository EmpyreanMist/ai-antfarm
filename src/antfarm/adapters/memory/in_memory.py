"""Bounded process-local memory."""

from collections.abc import Mapping, Sequence

from antfarm.domain.json_values import JsonObject, freeze_object, thaw_json
from antfarm.domain.models import AgentId, MemoryItem, MemoryQuery


class InMemoryMemoryStore:
    def __init__(self) -> None:
        self._items: dict[AgentId, list[MemoryItem]] = {}

    def recall(self, agent_id: AgentId, query: MemoryQuery) -> Sequence[MemoryItem]:
        if query.limit == 0:
            return ()
        return tuple(self._items.get(agent_id, ())[-query.limit :])

    def append(self, agent_id: AgentId, items: Sequence[MemoryItem]) -> None:
        self._items.setdefault(agent_id, []).extend(items)

    def snapshot(self) -> JsonObject:
        return freeze_object(
            {
                str(agent_id): [
                    {"kind": item.kind, "content": thaw_json(item.content)}
                    for item in items
                ]
                for agent_id, items in self._items.items()
            }
        )

    def restore(self, state: JsonObject) -> None:
        restored: dict[AgentId, list[MemoryItem]] = {}
        for raw_agent_id, raw_items in state.items():
            if not isinstance(raw_items, tuple):
                raise TypeError("memory items must be an array")
            items: list[MemoryItem] = []
            for raw_item in raw_items:
                if not isinstance(raw_item, Mapping):
                    raise TypeError("memory item must be an object")
                kind = raw_item.get("kind")
                content = raw_item.get("content")
                if not isinstance(kind, str) or not isinstance(content, Mapping):
                    raise TypeError("memory item requires kind and content")
                items.append(MemoryItem(kind=kind, content=content))
            restored[AgentId(raw_agent_id)] = items
        self._items = restored
