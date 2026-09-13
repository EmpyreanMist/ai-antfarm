"""Bounded process-local memory."""

from collections.abc import Mapping, Sequence

from antfarm.domain.json_values import JsonObject, freeze_object, thaw_json
from antfarm.domain.models import AgentId, MemoryItem, MemoryQuery


class InMemoryMemoryStore:
    def __init__(self, max_items_per_agent: int = 100) -> None:
        if max_items_per_agent < 1:
            raise ValueError("memory retention limit must be positive")
        self._max_items_per_agent = max_items_per_agent
        self._items: dict[AgentId, list[MemoryItem]] = {}

    def recall(self, agent_id: AgentId, query: MemoryQuery) -> Sequence[MemoryItem]:
        if query.limit == 0:
            return ()
        return tuple(self._items.get(agent_id, ())[-query.limit :])

    def append(self, agent_id: AgentId, items: Sequence[MemoryItem]) -> None:
        retained = self._items.setdefault(agent_id, [])
        message_ids = {
            message_id
            for item in retained
            if (message_id := _public_message_id(item)) is not None
        }
        for item in items:
            message_id = _public_message_id(item)
            if message_id is not None and message_id in message_ids:
                continue
            retained.append(item)
            if message_id is not None:
                message_ids.add(message_id)
        del retained[: -self._max_items_per_agent]

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
            message_ids: set[str] = set()
            for raw_item in raw_items:
                if not isinstance(raw_item, Mapping):
                    raise TypeError("memory item must be an object")
                kind = raw_item.get("kind")
                content = raw_item.get("content")
                if not isinstance(kind, str) or not isinstance(content, Mapping):
                    raise TypeError("memory item requires kind and content")
                item = MemoryItem(kind=kind, content=content)
                message_id = _public_message_id(item)
                if message_id is not None and message_id in message_ids:
                    raise ValueError("memory state contains a duplicate public message")
                if message_id is not None:
                    message_ids.add(message_id)
                items.append(item)
            if len(items) > self._max_items_per_agent:
                raise ValueError("memory state exceeds configured retention limit")
            restored[AgentId(raw_agent_id)] = items
        self._items = restored


def _public_message_id(item: MemoryItem) -> str | None:
    if item.kind != "public_message":
        return None
    message_id = item.content.get("id")
    if not isinstance(message_id, str) or not message_id:
        raise TypeError("public message memory requires a non-empty id")
    return message_id
