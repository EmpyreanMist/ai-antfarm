from antfarm.application.metrics import BuiltInMetricCollector
from antfarm.domain import AgentId, Event, EventSequence, RunId, Tick
from antfarm.domain.json_values import JsonObject, thaw_json


def _event(
    sequence: int,
    kind: str,
    *,
    actor_id: str | None = "alice",
    payload: JsonObject | None = None,
) -> Event:
    return Event(
        schema_version=1,
        event_id=f"metrics:{sequence}",
        run_id=RunId("metrics"),
        sequence=EventSequence(sequence),
        tick=Tick(1),
        kind=kind,
        actor_id=None if actor_id is None else AgentId(actor_id),
        causation_id=None,
        payload=payload or {},
    )


def test_metrics_project_deterministic_event_derived_summaries() -> None:
    collector = BuiltInMetricCollector(
        ("action_count", "rejection_count", "failure_count", "agent_outcomes"),
        action_kinds=("harvest", "contribute"),
        agent_ids=("bob", "alice"),
    )
    events = (
        _event(1, "action.validated", payload={"kind": "harvest"}),
        _event(2, "action.applied", payload={"kind": "harvest"}),
        _event(3, "action.rejected", actor_id="bob"),
        _event(4, "cognition.malformed", actor_id="bob"),
        _event(5, "action.noop"),
    )

    projected = collector.project(events)

    assert thaw_json(collector.snapshot()) == {
        "action_count": {"total": 0, "by_kind": {"contribute": 0, "harvest": 0}},
        "rejection_count": {"total": 0},
        "failure_count": {
            "total": 0,
            "by_kind": {"failed": 0, "malformed": 0, "timed_out": 0},
        },
        "agent_outcomes": {
            "alice": {
                "applied": 0,
                "rejected": 0,
                "noop": 0,
                "failed": 0,
                "malformed": 0,
                "timed_out": 0,
            },
            "bob": {
                "applied": 0,
                "rejected": 0,
                "noop": 0,
                "failed": 0,
                "malformed": 0,
                "timed_out": 0,
            },
        },
    }
    assert thaw_json(projected) == {
        "action_count": {
            "total": 1,
            "by_kind": {"contribute": 0, "harvest": 1},
        },
        "rejection_count": {"total": 1},
        "failure_count": {
            "total": 1,
            "by_kind": {"failed": 0, "malformed": 1, "timed_out": 0},
        },
        "agent_outcomes": {
            "alice": {
                "applied": 1,
                "rejected": 0,
                "noop": 1,
                "failed": 0,
                "malformed": 0,
                "timed_out": 0,
            },
            "bob": {
                "applied": 0,
                "rejected": 1,
                "noop": 0,
                "failed": 0,
                "malformed": 1,
                "timed_out": 0,
            },
        },
    }


def test_metrics_consume_committed_events_and_restore() -> None:
    collector = BuiltInMetricCollector(
        ("failure_count",), action_kinds=("increment",), agent_ids=("alice",)
    )
    event = _event(1, "cognition.timed_out")
    collector.observe(event)
    restored = BuiltInMetricCollector(
        ("failure_count",), action_kinds=("increment",), agent_ids=("alice",)
    )

    restored.restore(collector.snapshot())

    assert restored.snapshot() == collector.snapshot()
