import asyncio

import pytest

from antfarm.adapters.models import MockModelProvider
from antfarm.application.agent import MalformedDecisionError, ModelBackedAgent
from antfarm.domain import AgentContext, AgentId, Observation, Tick
from antfarm.ports.models import ModelResponse


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
