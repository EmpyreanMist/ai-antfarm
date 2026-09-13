"""Deterministic built-in summaries derived only from ordered events."""

from collections.abc import Mapping, Sequence

from antfarm.domain.json_values import JsonObject, freeze_object
from antfarm.domain.models import Event

ACTION_COUNT = "action_count"
REJECTION_COUNT = "rejection_count"
FAILURE_COUNT = "failure_count"
AGENT_OUTCOMES = "agent_outcomes"

BUILT_IN_METRICS = frozenset(
    {ACTION_COUNT, REJECTION_COUNT, FAILURE_COUNT, AGENT_OUTCOMES}
)
FAILURE_KINDS = ("failed", "malformed", "timed_out")
OUTCOME_KINDS = ("applied", "rejected", "noop", *FAILURE_KINDS)
EVENT_OUTCOMES = {
    "action.applied": "applied",
    "action.rejected": "rejected",
    "action.noop": "noop",
    "cognition.failed": "failed",
    "cognition.malformed": "malformed",
    "cognition.timed_out": "timed_out",
}


class BuiltInMetricCollector:
    """Collect the closed M1 metric catalog without access to world state."""

    def __init__(
        self,
        metric_ids: Sequence[str],
        *,
        action_kinds: Sequence[str],
        agent_ids: Sequence[str],
    ) -> None:
        unknown = set(metric_ids).difference(BUILT_IN_METRICS)
        if unknown:
            raise ValueError(f"unknown built-in metrics: {', '.join(sorted(unknown))}")
        self._metric_ids = frozenset(metric_ids)
        self._action_counts = {kind: 0 for kind in sorted(action_kinds)}
        self._rejection_count = 0
        self._failure_counts = {kind: 0 for kind in FAILURE_KINDS}
        self._agent_outcomes = {
            agent_id: {kind: 0 for kind in OUTCOME_KINDS}
            for agent_id in sorted(agent_ids)
        }

    @property
    def event_kinds(self) -> set[str]:
        kinds: set[str] = set()
        if ACTION_COUNT in self._metric_ids:
            kinds.add("action.applied")
        if REJECTION_COUNT in self._metric_ids:
            kinds.add("action.rejected")
        if FAILURE_COUNT in self._metric_ids:
            kinds.update(f"cognition.{kind}" for kind in FAILURE_KINDS)
        if AGENT_OUTCOMES in self._metric_ids:
            kinds.update(EVENT_OUTCOMES)
        return kinds

    def observe(self, event: Event) -> None:
        """Consume one event after its containing step has committed."""

        self._apply(event)

    def project(self, events: Sequence[Event]) -> JsonObject:
        """Purely project a batch for inclusion in the atomic checkpoint."""

        projected = BuiltInMetricCollector(
            tuple(self._metric_ids),
            action_kinds=tuple(self._action_counts),
            agent_ids=tuple(self._agent_outcomes),
        )
        projected.restore(self.snapshot())
        for event in events:
            projected._apply(event)
        return projected.snapshot()

    def snapshot(self) -> JsonObject:
        summaries: dict[str, object] = {}
        if ACTION_COUNT in self._metric_ids:
            summaries[ACTION_COUNT] = {
                "total": sum(self._action_counts.values()),
                "by_kind": dict(sorted(self._action_counts.items())),
            }
        if REJECTION_COUNT in self._metric_ids:
            summaries[REJECTION_COUNT] = {"total": self._rejection_count}
        if FAILURE_COUNT in self._metric_ids:
            summaries[FAILURE_COUNT] = {
                "total": sum(self._failure_counts.values()),
                "by_kind": dict(self._failure_counts),
            }
        if AGENT_OUTCOMES in self._metric_ids:
            summaries[AGENT_OUTCOMES] = {
                agent_id: dict(outcomes)
                for agent_id, outcomes in sorted(self._agent_outcomes.items())
            }
        return freeze_object(summaries)

    def restore(self, state: JsonObject) -> None:
        if set(state) != self._metric_ids:
            raise ValueError("metric state does not match configured metrics")
        if ACTION_COUNT in self._metric_ids:
            action_summary = _mapping(state, ACTION_COUNT)
            by_kind = _mapping(action_summary, "by_kind")
            if set(by_kind) != set(self._action_counts):
                raise ValueError("action metric kinds do not match configuration")
            self._action_counts = {
                kind: _count(by_kind, kind) for kind in sorted(by_kind)
            }
            if _count(action_summary, "total") != sum(self._action_counts.values()):
                raise ValueError("action metric total does not match its counts")
        if REJECTION_COUNT in self._metric_ids:
            self._rejection_count = _count(_mapping(state, REJECTION_COUNT), "total")
        if FAILURE_COUNT in self._metric_ids:
            failure_summary = _mapping(state, FAILURE_COUNT)
            by_kind = _mapping(failure_summary, "by_kind")
            if set(by_kind) != set(FAILURE_KINDS):
                raise ValueError("failure metric kinds are invalid")
            self._failure_counts = {
                kind: _count(by_kind, kind) for kind in FAILURE_KINDS
            }
            if _count(failure_summary, "total") != sum(
                self._failure_counts.values()
            ):
                raise ValueError("failure metric total does not match its counts")
        if AGENT_OUTCOMES in self._metric_ids:
            agent_summaries = _mapping(state, AGENT_OUTCOMES)
            if set(agent_summaries) != set(self._agent_outcomes):
                raise ValueError("metric agent ids do not match configuration")
            restored: dict[str, dict[str, int]] = {}
            for agent_id in sorted(agent_summaries):
                outcomes = _mapping(agent_summaries, agent_id)
                if set(outcomes) != set(OUTCOME_KINDS):
                    raise ValueError("agent outcome kinds are invalid")
                restored[agent_id] = {
                    kind: _count(outcomes, kind) for kind in OUTCOME_KINDS
                }
            self._agent_outcomes = restored

    def _apply(self, event: Event) -> None:
        if ACTION_COUNT in self._metric_ids and event.kind == "action.applied":
            action_kind = event.payload.get("kind")
            if isinstance(action_kind, str) and action_kind in self._action_counts:
                self._action_counts[action_kind] += 1
        if REJECTION_COUNT in self._metric_ids and event.kind == "action.rejected":
            self._rejection_count += 1
        failure_kind = event.kind.removeprefix("cognition.")
        if (
            FAILURE_COUNT in self._metric_ids
            and event.kind.startswith("cognition.")
            and failure_kind in self._failure_counts
        ):
            self._failure_counts[failure_kind] += 1
        outcome = EVENT_OUTCOMES.get(event.kind)
        actor_id = None if event.actor_id is None else str(event.actor_id)
        if (
            AGENT_OUTCOMES in self._metric_ids
            and outcome is not None
            and actor_id in self._agent_outcomes
        ):
            self._agent_outcomes[actor_id][outcome] += 1


def _mapping(data: Mapping[str, object], key: str) -> Mapping[str, object]:
    value = data.get(key)
    if not isinstance(value, Mapping):
        raise TypeError(f"metric {key!r} must be an object")
    return value


def _count(data: Mapping[str, object], key: str) -> int:
    value = data.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise TypeError(f"metric count {key!r} must be a non-negative integer")
    return value
