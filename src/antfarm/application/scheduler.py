"""Deterministic cognition scheduling."""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from antfarm.domain.models import AgentId, Tick


@dataclass(frozen=True, slots=True)
class ScheduleContext:
    tick: Tick
    agent_ids: Sequence[AgentId]


class CognitionScheduler(Protocol):
    def select(self, context: ScheduleContext) -> Sequence[AgentId]: ...


class StableScheduler:
    def select(self, context: ScheduleContext) -> Sequence[AgentId]:
        return tuple(sorted(context.agent_ids, key=str))
