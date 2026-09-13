"""A tiny world used only to prove the engine lifecycle."""

from collections.abc import Iterable

from antfarm.domain.json_values import JsonObject
from antfarm.domain.models import (
    ActionProposal,
    ActionResult,
    AgentId,
    Observation,
    Tick,
    ValidatedAction,
    ValidationResult,
)
from antfarm.domain.protocols import RandomSource


class CounterEnvironment:
    def __init__(self, initial_value: int, agent_ids: Iterable[AgentId]) -> None:
        self._value = initial_value
        self._agent_ids = frozenset(agent_ids)

    def observe(self, agent_id: AgentId, tick: Tick) -> Observation:
        if agent_id not in self._agent_ids:
            raise ValueError(f"unknown agent: {agent_id}")
        return Observation(agent_id=agent_id, tick=tick, state={"value": self._value})

    def validate(self, proposal: ActionProposal) -> ValidationResult:
        if proposal.actor_id not in self._agent_ids:
            return ValidationResult(action=None, reason="unknown actor")
        if proposal.kind != "increment":
            return ValidationResult(action=None, reason="unsupported action kind")
        if set(proposal.parameters) != {"amount"}:
            return ValidationResult(action=None, reason="amount is required")
        amount = proposal.parameters["amount"]
        if isinstance(amount, bool) or not isinstance(amount, int) or amount < 1:
            return ValidationResult(
                action=None, reason="amount must be a positive integer"
            )
        return ValidationResult(
            action=ValidatedAction(
                actor_id=proposal.actor_id,
                kind=proposal.kind,
                parameters=proposal.parameters,
            )
        )

    def apply(self, action: ValidatedAction, rng: RandomSource) -> ActionResult:
        del rng  # This world is deterministic but preserves the seeded boundary.
        if action.kind != "increment":
            raise ValueError("environment can only apply increment actions")
        amount = action.parameters["amount"]
        if isinstance(amount, bool) or not isinstance(amount, int):
            raise ValueError("validated increment amount must be an integer")
        self._value += amount
        return ActionResult(success=True, payload={"value": self._value})

    def snapshot(self) -> JsonObject:
        return {"value": self._value}

    def restore(self, state: JsonObject) -> None:
        if set(state) != {"value"}:
            raise ValueError("counter state must contain only value")
        value = state["value"]
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError("counter value must be an integer")
        self._value = value
