"""Finite shared-resource environment with agent-owned holdings."""

from collections.abc import Iterable, Mapping

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


class CommonsEnvironment:
    """Let agents harvest from and contribute to a shared resource."""

    def __init__(
        self,
        *,
        initial_resource: int,
        initial_endowment: int,
        agent_ids: Iterable[AgentId],
    ) -> None:
        if initial_resource < 0 or initial_endowment < 0:
            raise ValueError("commons initial values must not be negative")
        self._resource = initial_resource
        self._holdings = {
            agent_id: initial_endowment for agent_id in sorted(agent_ids, key=str)
        }

    def observe(self, agent_id: AgentId, tick: Tick) -> Observation:
        if agent_id not in self._holdings:
            raise ValueError(f"unknown agent: {agent_id}")
        return Observation(
            agent_id=agent_id,
            tick=tick,
            state={
                "resource": self._resource,
                "own_holding": self._holdings[agent_id],
            },
        )

    def validate(self, proposal: ActionProposal) -> ValidationResult:
        if proposal.actor_id not in self._holdings:
            return ValidationResult(action=None, reason="unknown actor")
        if proposal.kind not in {"harvest", "contribute"}:
            return ValidationResult(action=None, reason="unsupported action kind")
        if set(proposal.parameters) != {"amount"}:
            return ValidationResult(action=None, reason="amount is required")
        amount = proposal.parameters["amount"]
        if isinstance(amount, bool) or not isinstance(amount, int) or amount < 1:
            return ValidationResult(
                action=None, reason="amount must be a positive integer"
            )
        available = (
            self._resource
            if proposal.kind == "harvest"
            else self._holdings[proposal.actor_id]
        )
        if amount > available:
            source = "resource" if proposal.kind == "harvest" else "holding"
            return ValidationResult(
                action=None,
                reason=f"amount exceeds available {source}",
            )
        return ValidationResult(
            action=ValidatedAction(
                actor_id=proposal.actor_id,
                kind=proposal.kind,
                parameters=proposal.parameters,
            )
        )

    def apply(self, action: ValidatedAction, rng: RandomSource) -> ActionResult:
        del rng
        amount = action.parameters.get("amount")
        if isinstance(amount, bool) or not isinstance(amount, int) or amount < 1:
            raise ValueError("validated commons amount must be a positive integer")
        if action.actor_id not in self._holdings:
            raise ValueError("validated commons actor is unknown")
        if action.kind == "harvest":
            if amount > self._resource:
                raise ValueError("validated harvest exceeds available resource")
            self._resource -= amount
            self._holdings[action.actor_id] += amount
        elif action.kind == "contribute":
            if amount > self._holdings[action.actor_id]:
                raise ValueError("validated contribution exceeds actor holding")
            self._holdings[action.actor_id] -= amount
            self._resource += amount
        else:
            raise ValueError("environment cannot apply this action kind")
        return ActionResult(
            success=True,
            payload={
                "resource": self._resource,
                "actor_holding": self._holdings[action.actor_id],
            },
        )

    def snapshot(self) -> JsonObject:
        return {
            "resource": self._resource,
            "holdings": {
                str(agent_id): amount for agent_id, amount in self._holdings.items()
            },
        }

    def restore(self, state: JsonObject) -> None:
        if set(state) != {"resource", "holdings"}:
            raise ValueError("commons state must contain resource and holdings")
        resource = state["resource"]
        holdings = state["holdings"]
        if isinstance(resource, bool) or not isinstance(resource, int) or resource < 0:
            raise TypeError("commons resource must be a non-negative integer")
        if not isinstance(holdings, Mapping):
            raise TypeError("commons holdings must be an object")
        expected_agents = {str(agent_id) for agent_id in self._holdings}
        if set(holdings) != expected_agents:
            raise ValueError("commons holdings must contain every configured agent")
        restored: dict[AgentId, int] = {}
        for raw_agent_id, amount in holdings.items():
            if isinstance(amount, bool) or not isinstance(amount, int) or amount < 0:
                raise TypeError("commons holdings must be non-negative integers")
            restored[AgentId(raw_agent_id)] = amount
        self._resource = resource
        self._holdings = restored
