"""Deterministic cognition scheduling."""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from antfarm.domain.models import AgentId, CognitionOutcome, Tick


@dataclass(frozen=True, slots=True)
class ScheduleContext:
    tick: Tick
    agent_ids: Sequence[AgentId]


class CognitionScheduler(Protocol):
    def select(self, context: ScheduleContext) -> Sequence[AgentId]: ...

    def record(self, outcomes: Sequence[CognitionOutcome]) -> None: ...


class StableScheduler:
    def select(self, context: ScheduleContext) -> Sequence[AgentId]:
        return tuple(sorted(context.agent_ids, key=str))

    def record(self, outcomes: Sequence[CognitionOutcome]) -> None:
        del outcomes
