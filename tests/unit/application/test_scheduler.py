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


def test_budget_rotates_fairly_and_retains_due_agents() -> None:
    scheduler = StableScheduler(interval=1, max_cognitions_per_tick=1)

    selected: list[AgentId] = []
    for tick in range(1, 7):
        due = scheduler.select(_context(tick))
        selected.extend(due)
        scheduler.record(
            tuple(
                CognitionOutcome(agent_id=agent_id, tick=Tick(tick), kind="noop")
                for agent_id in due
            )
        )

    assert selected == [
        AgentId("alice"),
        AgentId("bob"),
        AgentId("charlie"),
        AgentId("alice"),
        AgentId("bob"),
        AgentId("charlie"),
    ]


def test_staggered_agent_cadence_offsets_are_checkpointed() -> None:
    scheduler = StableScheduler(
        interval=3,
        agent_intervals={AgentId("bob"): 2},
        stagger=True,
        max_cognitions_per_tick=1,
    )

    first = scheduler.select(_context(1))
    scheduler.record((CognitionOutcome(first[0], Tick(1), "noop"),))
    second = scheduler.select(_context(2))
    restored = StableScheduler(
        interval=3,
        agent_intervals={AgentId("bob"): 2},
        stagger=True,
        max_cognitions_per_tick=1,
    )
    restored.restore(scheduler.snapshot())

    assert first == (AgentId("alice"),)
    assert second == (AgentId("bob"),)
    assert restored.snapshot()["offsets"] == scheduler.snapshot()["offsets"]


def test_public_speech_wakes_only_recipients_for_a_future_tick() -> None:
    scheduler = StableScheduler(interval=10)
    initial = scheduler.select(_context(1))
    scheduler.record(
        tuple(CognitionOutcome(agent_id, Tick(1), "noop") for agent_id in initial)
    )
    speech = Event(
        schema_version=1,
        event_id="schedule:speech",
        run_id=RunId("schedule"),
        sequence=EventSequence(1),
        tick=Tick(1),
        kind="action.applied",
        actor_id=AgentId("alice"),
        causation_id=None,
        payload={"kind": "say"},
    )

    scheduler.notify((speech,))

    assert scheduler.select(_context(2)) == (
        AgentId("bob"),
        AgentId("charlie"),
    )


def test_provider_failures_apply_capped_retry_cooldowns() -> None:
    scheduler = StableScheduler(
        interval=1,
        max_cognitions_per_tick=1,
        failure_retry_cooldown_max=2,
    )
    alice = AgentId("alice")

    def alice_context(tick: int) -> ScheduleContext:
        return ScheduleContext(tick=Tick(tick), agent_ids=(alice,))

    assert scheduler.select(alice_context(1)) == (alice,)
    scheduler.record((CognitionOutcome(alice, Tick(1), "failed"),))
    assert scheduler.select(alice_context(2)) == ()
    assert scheduler.select(alice_context(3)) == (alice,)
    scheduler.record((CognitionOutcome(alice, Tick(3), "timed_out"),))

    restored = StableScheduler(
        interval=1,
        max_cognitions_per_tick=1,
        failure_retry_cooldown_max=2,
    )
    restored.restore(scheduler.snapshot())

    assert restored.select(alice_context(4)) == ()
    assert restored.select(alice_context(5)) == ()
    assert restored.select(alice_context(6)) == (alice,)
