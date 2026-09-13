from antfarm.application.scheduler import ScheduleContext, StableScheduler
from antfarm.domain import (
    AgentId,
    CognitionOutcome,
    Event,
    EventSequence,
    RunId,
    Tick,
)


def _context(tick: int) -> ScheduleContext:
    return ScheduleContext(
        tick=Tick(tick),
        agent_ids=(AgentId("charlie"), AgentId("alice"), AgentId("bob")),
    )


def _event(kind: str, actor_id: AgentId | None) -> Event:
    return Event(
        schema_version=1,
        event_id="schedule:1",
        run_id=RunId("schedule"),
        sequence=EventSequence(1),
        tick=Tick(1),
        kind=kind,
        actor_id=actor_id,
        causation_id=None,
    )


def test_interval_selects_agents_in_stable_order() -> None:
    scheduler = StableScheduler(interval=2)

    assert scheduler.select(_context(1)) == (
        AgentId("alice"),
        AgentId("bob"),
        AgentId("charlie"),
    )
    assert scheduler.select(_context(2)) == ()
    assert scheduler.select(_context(3)) == (
        AgentId("alice"),
        AgentId("bob"),
        AgentId("charlie"),
    )


def test_cooldown_and_pending_event_survive_snapshot_restore() -> None:
    alice = AgentId("alice")
    original = StableScheduler(
        interval=None,
        cooldown=2,
        event_kinds=("world.changed",),
    )
    original.notify((_event("world.changed", alice),))
    assert original.select(_context(1)) == (alice,)
    original.record((CognitionOutcome(agent_id=alice, tick=Tick(1), kind="noop"),))
    original.notify((_event("world.changed", alice),))

    restored = StableScheduler(
        interval=None,
        cooldown=2,
        event_kinds=("world.changed",),
    )
    restored.restore(original.snapshot())

    assert restored.select(_context(2)) == ()
    assert restored.select(_context(3)) == ()
    assert restored.select(_context(4)) == (alice,)


def test_event_trigger_can_schedule_all_agents() -> None:
    scheduler = StableScheduler(interval=None, event_kinds=("tick.completed",))

    assert scheduler.select(_context(1)) == ()
    scheduler.notify((_event("ignored", AgentId("alice")),))
    assert scheduler.select(_context(2)) == ()
    scheduler.notify((_event("tick.completed", None),))

    assert scheduler.select(_context(3)) == (
        AgentId("alice"),
        AgentId("bob"),
        AgentId("charlie"),
    )
