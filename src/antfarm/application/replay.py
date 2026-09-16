"""Model-free reconstruction and comparison of committed run histories."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from random import Random

from antfarm.application.contracts import ApplicationError, ErrorCode, ReplayFrame
from antfarm.domain.json_values import JsonObject, freeze_object, thaw_json
from antfarm.domain.models import ActionProposal, Event, SimulationSnapshot, Tick
from antfarm.domain.protocols import Environment

MAX_REPLAY_EVENTS = 100_000
OUTCOME_KINDS = {
    "action.applied": "applied",
    "action.rejected": "rejected",
    "action.noop": "noop",
    "cognition.failed": "failed",
    "cognition.malformed": "malformed",
    "cognition.timed_out": "timed_out",
}


@dataclass(frozen=True, slots=True)
class ReplayResult:
    frames: tuple[ReplayFrame, ...]
    final_world: JsonObject
    final_metrics: JsonObject


def replay_events(
    *,
    environment: Environment,
    seed: int,
    events: Sequence[Event],
    checkpoint: SimulationSnapshot,
) -> ReplayResult:
    """Reapply validated committed actions without cognition or provider access."""

    if not events or len(events) > MAX_REPLAY_EVENTS:
        raise _invalid("run history is empty or exceeds the replay limit")
    rng = Random(seed)
    frames: list[ReplayFrame] = []
    metrics = _empty_metrics()
    expected_sequence = 1
    expected_tick = 1
    tick_events: list[Event] = []
    validated: dict[str, Event] = {}

    for event in events:
        if event.schema_version != 1:
            raise _invalid("event schema version is incompatible")
        if int(event.sequence) != expected_sequence:
            raise _invalid("event sequence is incomplete or unordered")
        expected_sequence += 1
        if int(event.tick) != expected_tick:
            raise _invalid("event ticks are incomplete or unordered")
        tick_events.append(event)
        if event.kind == "action.validated":
            validated[event.event_id] = event
        if event.kind == "action.applied":
            _apply_recorded(environment, rng, event, validated)
        _record_metric(metrics, event)
        if event.kind == "tick.completed":
            if tick_events[0].kind != "tick.started":
                raise _invalid("tick does not start with tick.started")
            frames.append(
                ReplayFrame(
                    tick=expected_tick,
                    event_sequence=int(event.sequence),
                    world=environment.snapshot(),
                    metrics=freeze_object(metrics),
                )
            )
            tick_events = []
            validated = {}
            expected_tick += 1

    if tick_events or not frames:
        raise _invalid("run history ends before a committed tick boundary")
    final = frames[-1]
    checkpoint_sequence = checkpoint.engine.get("event_sequence")
    if checkpoint_sequence != final.event_sequence:
        raise _invalid("checkpoint sequence does not match committed history")
    if int(checkpoint.tick) != final.tick or checkpoint.world != final.world:
        raise _invalid("replayed final state does not match the checkpoint")
    return ReplayResult(
        frames=tuple(frames),
        final_world=final.world,
        final_metrics=final.metrics,
    )


def json_deltas(
    left: JsonObject, right: JsonObject, *, limit: int = 1_000
) -> JsonObject:
    """Return bounded leaf deltas without coercing incompatible values."""

    changes: dict[str, object] = {}
    _walk_deltas("", thaw_json(left), thaw_json(right), changes, limit)
    return freeze_object(changes)


def _apply_recorded(
    environment: Environment,
    rng: Random,
    event: Event,
    validated: Mapping[str, Event],
) -> None:
    cause = validated.get(event.causation_id or "")
    kind = event.payload.get("kind")
    parameters = event.payload.get("parameters")
    if (
        cause is None
        or cause.actor_id != event.actor_id
        or cause.tick != event.tick
        or cause.payload.get("kind") != kind
        or cause.payload.get("parameters") != parameters
        or event.actor_id is None
        or not isinstance(kind, str)
        or not isinstance(parameters, Mapping)
    ):
        raise _invalid("applied action does not match a validated action")
    validation = environment.validate(
        ActionProposal(actor_id=event.actor_id, kind=kind, parameters=parameters)
    )
    if not validation.accepted or validation.action is None:
        raise _invalid("recorded action is invalid for the reconstructed state")
    result = environment.apply(validation.action, rng, Tick(int(event.tick)))
    recorded_result = {
        key: value
        for key, value in event.payload.items()
        if key not in {"kind", "parameters"}
    }
    if result.payload != freeze_object(recorded_result):
        raise _invalid("recorded action result does not match reconstruction")


def _empty_metrics() -> dict[str, object]:
    return {
        "actions": {"total": 0, "by_kind": {}},
        "rejections": 0,
        "failures": 0,
        "outcomes": {},
    }


def _record_metric(metrics: dict[str, object], event: Event) -> None:
    outcome = OUTCOME_KINDS.get(event.kind)
    if event.kind == "action.applied":
        actions = metrics["actions"]
        if not isinstance(actions, dict):
            raise RuntimeError("replay metrics are invalid")
        actions["total"] = _count(actions.get("total")) + 1
        by_kind = actions["by_kind"]
        kind = event.payload.get("kind")
        if isinstance(by_kind, dict) and isinstance(kind, str):
            by_kind[kind] = _count(by_kind.get(kind, 0)) + 1
    elif event.kind == "action.rejected":
        metrics["rejections"] = _count(metrics.get("rejections")) + 1
    elif event.kind.startswith("cognition."):
        metrics["failures"] = _count(metrics.get("failures")) + 1
    if outcome is not None and event.actor_id is not None:
        outcomes = metrics["outcomes"]
        if not isinstance(outcomes, dict):
            raise RuntimeError("replay metrics are invalid")
        actor = outcomes.setdefault(str(event.actor_id), {})
        if isinstance(actor, dict):
            actor[outcome] = _count(actor.get(outcome, 0)) + 1


def _count(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise RuntimeError("replay metric count is invalid")
    return value


def _walk_deltas(
    path: str,
    left: object,
    right: object,
    changes: dict[str, object],
    limit: int,
) -> None:
    if len(changes) >= limit:
        return
    if isinstance(left, dict) and isinstance(right, dict):
        for key in sorted(set(left) | set(right)):
            _walk_deltas(
                f"{path}.{key}" if path else key,
                left.get(key),
                right.get(key),
                changes,
                limit,
            )
        return
    if left != right:
        changes[path or "$root"] = {"baseline": left, "candidate": right}


def _invalid(message: str) -> ApplicationError:
    return ApplicationError(ErrorCode.INVALID_STATE, message)
