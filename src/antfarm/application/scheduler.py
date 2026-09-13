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
    """Select due agents in stable order using deterministic scheduling rules.

    An interval starts at tick one. Cooldown is the number of complete ticks an
    agent must skip after an outcome. Matching events schedule their actor for a
    future tick; actor-less matching events schedule every known agent.
    """

    def __init__(
        self,
        *,
        interval: int | None = 1,
        cooldown: int = 0,
        event_kinds: Sequence[str] = (),
    ) -> None:
        if interval is not None and interval < 1:
            raise ValueError("scheduler interval must be positive")
        if cooldown < 0:
            raise ValueError("scheduler cooldown must not be negative")
        if interval is None and not event_kinds:
            raise ValueError("scheduler requires an interval or event kind")
        if any(not kind for kind in event_kinds):
            raise ValueError("scheduler event kinds must not be empty")
        self._interval = interval
        self._cooldown = cooldown
        self._event_kinds = frozenset(event_kinds)
        self._last_outcome_ticks: dict[AgentId, Tick] = {}
        self._pending_agents: set[AgentId] = set()
        self._pending_all = False

    def select(self, context: ScheduleContext) -> Sequence[AgentId]:
        if self._pending_all:
            self._pending_agents.update(context.agent_ids)
            self._pending_all = False

        interval_due = self._interval is not None and (
            (int(context.tick) - 1) % self._interval == 0
        )
        candidates = (
            agent_id
            for agent_id in context.agent_ids
            if interval_due or agent_id in self._pending_agents
        )
        return tuple(
            sorted(
                (
                    agent_id
                    for agent_id in candidates
                    if self._cooldown_elapsed(agent_id, context.tick)
                ),
                key=str,
            )
        )

    def record(self, outcomes: Sequence[CognitionOutcome]) -> None:
        for outcome in outcomes:
            self._last_outcome_ticks[outcome.agent_id] = outcome.tick
            self._pending_agents.discard(outcome.agent_id)

    def notify(self, events: Sequence[Event]) -> None:
        for event in events:
            if event.kind not in self._event_kinds:
                continue
            if event.actor_id is None:
                self._pending_all = True
            else:
                self._pending_agents.add(event.actor_id)

    def snapshot(self) -> JsonObject:
        return freeze_object(
            {
                "last_outcome_ticks": {
                    str(agent_id): int(tick)
                    for agent_id, tick in sorted(
                        self._last_outcome_ticks.items(), key=lambda item: str(item[0])
                    )
                },
                "pending_agents": tuple(
                    str(agent_id) for agent_id in sorted(self._pending_agents, key=str)
                ),
                "pending_all": self._pending_all,
            }
        )

    def restore(self, state: JsonObject) -> None:
        raw_ticks = state.get("last_outcome_ticks")
        raw_pending = state.get("pending_agents")
        raw_pending_all = state.get("pending_all")
        if not isinstance(raw_ticks, Mapping):
            raise TypeError("scheduler outcome ticks must be an object")
        if not isinstance(raw_pending, tuple):
            raise TypeError("scheduler pending agents must be an array")
        if not isinstance(raw_pending_all, bool):
            raise TypeError("scheduler pending-all flag must be a boolean")

        restored_ticks: dict[AgentId, Tick] = {}
        for raw_agent_id, raw_tick in raw_ticks.items():
            if not isinstance(raw_agent_id, str):
                raise TypeError("scheduler agent identifiers must be strings")
            if isinstance(raw_tick, bool) or not isinstance(raw_tick, int):
                raise TypeError("scheduler outcome ticks must be integers")
            restored_ticks[AgentId(raw_agent_id)] = Tick(raw_tick)

        restored_pending: set[AgentId] = set()
        for raw_pending_agent in raw_pending:
            if not isinstance(raw_pending_agent, str):
                raise TypeError("scheduler pending agent identifiers must be strings")
            restored_pending.add(AgentId(raw_pending_agent))

        self._last_outcome_ticks = restored_ticks
        self._pending_agents = restored_pending
        self._pending_all = raw_pending_all

    def _cooldown_elapsed(self, agent_id: AgentId, tick: Tick) -> bool:
        previous = self._last_outcome_ticks.get(agent_id)
        return previous is None or int(tick) > int(previous) + self._cooldown
