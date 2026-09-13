"""Domain contracts implemented by inward-facing application code."""

from typing import Protocol

from antfarm.domain.json_values import JsonObject
from antfarm.domain.models import (
    ActionProposal,
    ActionResult,
    AgentContext,
    AgentId,
    Observation,
    Tick,
    ValidatedAction,
    ValidationResult,
)


class Agent(Protocol):
    id: AgentId
    model_ref: str

    async def decide(self, context: AgentContext) -> ActionProposal | None: ...


class RandomSource(Protocol):
    def random(self) -> float: ...

    def randint(self, start: int, stop: int) -> int: ...


class Environment(Protocol):
    def observe(self, agent_id: AgentId, tick: Tick) -> Observation: ...

    def validate(self, proposal: ActionProposal) -> ValidationResult: ...

    def apply(self, action: ValidatedAction, rng: RandomSource) -> ActionResult: ...

    def snapshot(self) -> JsonObject: ...

    def restore(self, state: JsonObject) -> None: ...
