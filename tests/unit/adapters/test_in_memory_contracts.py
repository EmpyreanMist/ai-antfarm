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
