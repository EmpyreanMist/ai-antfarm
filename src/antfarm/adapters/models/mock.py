"""Offline deterministic model provider."""

from collections.abc import Mapping, Sequence

from antfarm.domain.models import AgentId
from antfarm.ports.models import ModelRequest, ModelResponse, ProviderCapabilities


class MockModelProvider:
    capabilities = ProviderCapabilities(
        structured_output=True,
        network_required=False,
    )

    def __init__(
        self,
        decisions: Mapping[AgentId, Sequence[ModelResponse | Exception]],
    ) -> None:
        self._decisions = {
            agent_id: tuple(agent_decisions)
            for agent_id, agent_decisions in decisions.items()
        }
        self._positions: dict[AgentId, int] = {}

    async def generate(self, request: ModelRequest) -> ModelResponse:
        position = self._positions.get(request.actor_id, 0)
        self._positions[request.actor_id] = position + 1
        decisions = self._decisions.get(request.actor_id, ())
        if position >= len(decisions):
            return ModelResponse(action_kind=None)
        decision = decisions[position]
        if isinstance(decision, Exception):
            raise decision
        return decision

    async def close(self) -> None:
        """The deterministic provider owns no external resources."""
