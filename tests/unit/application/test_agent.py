import asyncio

import pytest

from antfarm.adapters.models import MockModelProvider
from antfarm.application.agent import MalformedDecisionError, ModelBackedAgent
from antfarm.domain import AgentContext, AgentId, AgentPersonality, Observation, Tick
from antfarm.ports.models import (
    MalformedModelResponseError,
    ModelRequest,
    ModelResponse,
    ProviderCapabilities,
)


def test_malformed_model_response_fails_before_proposal_creation() -> None:
    agent_id = AgentId("alice")
    agent = ModelBackedAgent(
        id=agent_id,
        model_ref="test-model",
        provider=MockModelProvider(
            {agent_id: (ModelResponse(action_kind=""),)}
        ),
    )
    context = AgentContext(
        observation=Observation(agent_id=agent_id, tick=Tick(1), state={}),
        memories=(),
    )

    with pytest.raises(MalformedDecisionError):
        asyncio.run(agent.decide(context))


class _MalformedProvider:
    capabilities = ProviderCapabilities(
        structured_output=True,
        network_required=True,
    )

    async def generate(self, request: ModelRequest) -> ModelResponse:
        del request
        raise MalformedModelResponseError("invalid wire response")


def test_malformed_provider_output_becomes_a_malformed_decision() -> None:
    agent_id = AgentId("alice")
    agent = ModelBackedAgent(
        id=agent_id,
        model_ref="test-model",
        provider=_MalformedProvider(),
    )
    context = AgentContext(
        observation=Observation(agent_id=agent_id, tick=Tick(1), state={}),
        memories=(),
    )

    with pytest.raises(MalformedDecisionError):
        asyncio.run(agent.decide(context))


class _RecordingProvider:
    capabilities = ProviderCapabilities(
        structured_output=True,
        network_required=False,
    )

    def __init__(self) -> None:
        self.requests: list[ModelRequest] = []

    async def generate(self, request: ModelRequest) -> ModelResponse:
        self.requests.append(request)
        return ModelResponse(action_kind=None)


def test_agent_supplies_immutable_identity_and_private_personality() -> None:
    agent_id = AgentId("alice")
    provider = _RecordingProvider()
    personality = AgentPersonality(
        description="A patient steward.", traits={"patience": "high"}
    )
    agent = ModelBackedAgent(
        id=agent_id,
        model_ref="shared-model",
        provider=provider,
        personality=personality,
    )
    context = AgentContext(
        observation=Observation(agent_id=agent_id, tick=Tick(1), state={"value": 2}),
        memories=(),
    )

    asyncio.run(agent.decide(context))

    assert len(provider.requests) == 1
    request = provider.requests[0]
    assert request.identity.id == agent_id
    assert request.personality == personality
    assert request.observation.agent_id == agent_id
    assert request.personality is not None
    with pytest.raises(TypeError):
        request.personality.traits["patience"] = "low"  # type: ignore[index]
