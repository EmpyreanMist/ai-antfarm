from antfarm.adapters.events import InMemoryEventBus
from antfarm.adapters.memory import InMemoryMemoryStore
from antfarm.domain import (
    AgentId,
    Event,
    EventSequence,
    MemoryItem,
    MemoryQuery,
    RunId,
    Tick,
)


def test_recall_is_bounded_and_scoped_to_one_agent() -> None:
    memory = InMemoryMemoryStore()
    memory.append(
        AgentId("alice"),
        (
            MemoryItem(kind="result", content={"value": 1}),
            MemoryItem(kind="result", content={"value": 2}),
            MemoryItem(kind="result", content={"value": 3}),
        ),
    )
    memory.append(
        AgentId("bob"),
        (MemoryItem(kind="result", content={"value": 99}),),
    )

    assert memory.recall(AgentId("alice"), MemoryQuery(limit=2)) == (
        MemoryItem(kind="result", content={"value": 2}),
        MemoryItem(kind="result", content={"value": 3}),
    )
    assert memory.recall(AgentId("alice"), MemoryQuery(limit=0)) == ()
    assert memory.recall(AgentId("missing"), MemoryQuery(limit=10)) == ()


def test_memory_snapshot_restore_round_trip() -> None:
    original = InMemoryMemoryStore()
    original.append(
        AgentId("alice"),
        (MemoryItem(kind="result", content={"value": 3}),),
    )
    restored = InMemoryMemoryStore()

    restored.restore(original.snapshot())

    assert restored.recall(AgentId("alice"), MemoryQuery(limit=10)) == (
        MemoryItem(kind="result", content={"value": 3}),
    )


def test_memory_retention_is_bounded_per_agent() -> None:
    memory = InMemoryMemoryStore(max_items_per_agent=2)

    memory.append(
        AgentId("alice"),
        tuple(
            MemoryItem(kind="result", content={"value": value})
            for value in range(4)
        ),
    )

    assert memory.recall(AgentId("alice"), MemoryQuery(limit=10)) == (
        MemoryItem(kind="result", content={"value": 2}),
        MemoryItem(kind="result", content={"value": 3}),
    )


def test_public_message_delivery_is_deduplicated_by_stable_id() -> None:
    memory = InMemoryMemoryStore()
    message = MemoryItem(
        kind="public_message",
        content={"id": "message-1", "sender_id": "alice", "tick": 1, "text": "hi"},
    )

    memory.append(AgentId("bob"), (message, message))
    memory.append(AgentId("bob"), (message,))

    assert memory.recall(AgentId("bob"), MemoryQuery(limit=10)) == (message,)


def test_event_subscription_is_observational_and_cancellable() -> None:
    bus = InMemoryEventBus()
    received: list[Event] = []
    subscription = bus.subscribe({"action.applied"}, received.append)
    event = Event(
        schema_version=1,
        event_id="run:1",
        run_id=RunId("run"),
        sequence=EventSequence(1),
        tick=Tick(1),
        kind="action.applied",
        actor_id=AgentId("alice"),
        causation_id=None,
    )

    bus.publish((event,))
    subscription.cancel()
    bus.publish((event,))

    assert received == [event]
    assert bus.published == [event, event]
