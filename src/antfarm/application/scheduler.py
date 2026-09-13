"""Deterministic, snapshot-capable cognition scheduling."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol

from antfarm.domain.json_values import JsonObject, freeze_object
from antfarm.domain.models import AgentId, CognitionOutcome, Event, Tick


@dataclass(frozen=True, slots=True)
class ScheduleContext:
    tick: Tick
    agent_ids: Sequence[AgentId]


class CognitionScheduler(Protocol):
    def select(self, context: ScheduleContext) -> Sequence[AgentId]: ...

    def record(self, outcomes: Sequence[CognitionOutcome]) -> None: ...

    def notify(self, events: Sequence[Event]) -> None: ...

    def snapshot(self) -> JsonObject: ...

    def restore(self, state: JsonObject) -> None: ...


class StableScheduler:
    """Select a fair, bounded set of due agents in deterministic order."""

    _FAILURE_KINDS = frozenset({"failed", "malformed", "timed_out"})

    def __init__(
        self,
        *,
        interval: int | None = 1,
        cooldown: int = 0,
        event_kinds: Sequence[str] = (),
        agent_intervals: Mapping[AgentId, int] | None = None,
        stagger: bool = False,
        max_cognitions_per_tick: int | None = None,
        failure_retry_cooldown_max: int = 8,
    ) -> None:
        if interval is not None and interval < 1:
            raise ValueError("scheduler interval must be positive")
        if cooldown < 0:
            raise ValueError("scheduler cooldown must not be negative")
        if interval is None and not event_kinds and not agent_intervals:
            raise ValueError("scheduler requires an interval or event kind")
        if any(not kind for kind in event_kinds):
            raise ValueError("scheduler event kinds must not be empty")
        if max_cognitions_per_tick is not None and max_cognitions_per_tick < 1:
            raise ValueError("scheduler cognition budget must be positive")
        if failure_retry_cooldown_max < 1:
            raise ValueError("scheduler retry cooldown cap must be positive")
        configured_intervals = dict(agent_intervals or {})
        if any(value < 1 for value in configured_intervals.values()):
            raise ValueError("agent cognition intervals must be positive")

        self._interval = interval
        self._cooldown = cooldown
        self._event_kinds = frozenset(event_kinds)
        self._agent_intervals = configured_intervals
        self._stagger = stagger
        self._budget = max_cognitions_per_tick
        self._retry_cap = failure_retry_cooldown_max
        self._last_outcome_ticks: dict[AgentId, Tick] = {}
        self._retry_blocked_until: dict[AgentId, Tick] = {}
        self._failure_counts: dict[AgentId, int] = {}
        self._pending_agents: set[AgentId] = set()
        self._pending_all = False
        self._known_agents: tuple[AgentId, ...] = ()
        self._offsets: dict[AgentId, int] = {}
        self._fairness_cursor = 0

    def select(self, context: ScheduleContext) -> Sequence[AgentId]:
        agent_ids = tuple(sorted(context.agent_ids, key=str))
        self._known_agents = agent_ids
        known = set(agent_ids)
        self._pending_agents.intersection_update(known)
        self._ensure_offsets(agent_ids)

        if self._pending_all:
            self._pending_agents.update(agent_ids)
            self._pending_all = False
        for agent_id in agent_ids:
            if self._periodically_due(agent_id, context.tick):
                self._pending_agents.add(agent_id)

        if not agent_ids:
            return ()
        start = self._fairness_cursor % len(agent_ids)
        rotated = (*agent_ids[start:], *agent_ids[:start])
        eligible = [
            agent_id
            for agent_id in rotated
            if agent_id in self._pending_agents
            and self._cooldown_elapsed(agent_id, context.tick)
            and self._retry_elapsed(agent_id, context.tick)
        ]
        selected = eligible[: self._budget]
        if selected:
            last_index = agent_ids.index(selected[-1])
            self._fairness_cursor = (last_index + 1) % len(agent_ids)
            self._pending_agents.difference_update(selected)
        return tuple(selected)

    def record(self, outcomes: Sequence[CognitionOutcome]) -> None:
        for outcome in outcomes:
            agent_id = outcome.agent_id
            self._last_outcome_ticks[agent_id] = outcome.tick
            self._pending_agents.discard(agent_id)
            if outcome.kind in self._FAILURE_KINDS:
                failures = self._failure_counts.get(agent_id, 0) + 1
                self._failure_counts[agent_id] = failures
                retry_cooldown = min(2 ** (failures - 1), self._retry_cap)
                self._retry_blocked_until[agent_id] = Tick(
                    int(outcome.tick) + retry_cooldown
                )
            else:
                self._failure_counts.pop(agent_id, None)
                self._retry_blocked_until.pop(agent_id, None)

    def notify(self, events: Sequence[Event]) -> None:
        for event in events:
            if event.kind == "action.applied" and event.payload.get("kind") == "say":
                self._pending_agents.update(
                    agent_id
                    for agent_id in self._known_agents
                    if agent_id != event.actor_id
                )
            if event.kind not in self._event_kinds:
                continue
            if event.actor_id is None:
                self._pending_all = True
            else:
                self._pending_agents.add(event.actor_id)

    def snapshot(self) -> JsonObject:
        return freeze_object(
            {
                "last_outcome_ticks": self._tick_map(self._last_outcome_ticks),
                "retry_blocked_until": self._tick_map(self._retry_blocked_until),
                "failure_counts": self._int_map(self._failure_counts),
                "pending_agents": tuple(
                    str(agent_id) for agent_id in sorted(self._pending_agents, key=str)
                ),
                "pending_all": self._pending_all,
                "fairness_cursor": self._fairness_cursor,
                "offsets": self._int_map(self._offsets),
            }
        )

    def restore(self, state: JsonObject) -> None:
        self._last_outcome_ticks = {
            agent_id: Tick(value)
            for agent_id, value in self._restore_int_map(
                state, "last_outcome_ticks"
            ).items()
        }
        self._retry_blocked_until = {
            agent_id: Tick(value)
            for agent_id, value in self._restore_int_map(
                state, "retry_blocked_until"
            ).items()
        }
        self._failure_counts = self._restore_int_map(state, "failure_counts")
        self._offsets = self._restore_int_map(state, "offsets")

        raw_pending = state.get("pending_agents")
        raw_pending_all = state.get("pending_all")
        raw_cursor = state.get("fairness_cursor")
        if not isinstance(raw_pending, tuple):
            raise TypeError("scheduler pending agents must be an array")
        if not isinstance(raw_pending_all, bool):
            raise TypeError("scheduler pending-all flag must be a boolean")
        if isinstance(raw_cursor, bool) or not isinstance(raw_cursor, int):
            raise TypeError("scheduler fairness cursor must be an integer")
        restored_pending: set[AgentId] = set()
        for raw_agent_id in raw_pending:
            if not isinstance(raw_agent_id, str):
                raise TypeError("scheduler pending agent identifiers must be strings")
            restored_pending.add(AgentId(raw_agent_id))
        self._pending_agents = restored_pending
        self._pending_all = raw_pending_all
        self._fairness_cursor = raw_cursor

    def _ensure_offsets(self, agent_ids: Sequence[AgentId]) -> None:
        for index, agent_id in enumerate(agent_ids):
            interval = self._agent_intervals.get(agent_id, self._interval)
            self._offsets.setdefault(
                agent_id,
                index % interval if self._stagger and interval is not None else 0,
            )

    def _periodically_due(self, agent_id: AgentId, tick: Tick) -> bool:
        interval = self._agent_intervals.get(agent_id, self._interval)
        if interval is None:
            return False
        first_tick = self._offsets[agent_id] + 1
        return int(tick) >= first_tick and (int(tick) - first_tick) % interval == 0

    def _cooldown_elapsed(self, agent_id: AgentId, tick: Tick) -> bool:
        previous = self._last_outcome_ticks.get(agent_id)
        return previous is None or int(tick) > int(previous) + self._cooldown

    def _retry_elapsed(self, agent_id: AgentId, tick: Tick) -> bool:
        blocked_until = self._retry_blocked_until.get(agent_id)
        return blocked_until is None or int(tick) > int(blocked_until)

    @staticmethod
    def _tick_map(values: Mapping[AgentId, Tick]) -> dict[str, int]:
        return {
            str(agent_id): int(value)
            for agent_id, value in sorted(values.items(), key=lambda item: str(item[0]))
        }

    @staticmethod
    def _int_map(values: Mapping[AgentId, int]) -> dict[str, int]:
        return {
            str(agent_id): value
            for agent_id, value in sorted(values.items(), key=lambda item: str(item[0]))
        }

    @staticmethod
    def _restore_int_map(state: JsonObject, key: str) -> dict[AgentId, int]:
        raw = state.get(key)
        if not isinstance(raw, Mapping):
            raise TypeError(f"scheduler {key} must be an object")
        restored: dict[AgentId, int] = {}
        for raw_agent_id, raw_value in raw.items():
            if not isinstance(raw_agent_id, str):
                raise TypeError("scheduler agent identifiers must be strings")
            if isinstance(raw_value, bool) or not isinstance(raw_value, int):
                raise TypeError(f"scheduler {key} values must be integers")
            restored[AgentId(raw_agent_id)] = raw_value
        return restored
