"""Domain contracts implemented by inward-facing application code."""

from random import Random
from typing import Protocol

from antfarm.domain.models import (
    ActionProposal,
    ActionResult,
    AgentContext,
    AgentId,
    JsonObject,
    Observation,
    Tick,
    ValidatedAction,
    ValidationResult,
)


class Agent(Protocol):
    id: AgentId

    async def decide(self, context: AgentContext) -> ActionProposal | None: ...


class Environment(Protocol):
    def observe(self, agent_id: AgentId, tick: Tick) -> Observation: ...

    def validate(self, proposal: ActionProposal) -> ValidationResult: ...

    def apply(self, action: ValidatedAction, rng: Random) -> ActionResult: ...

    def snapshot(self) -> JsonObject: ...
