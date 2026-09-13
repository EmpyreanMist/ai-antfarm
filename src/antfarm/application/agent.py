"""A minimal agent that delegates cognition to a model provider."""

from dataclasses import dataclass

from antfarm.domain.models import ActionProposal, AgentContext, AgentId
from antfarm.ports.models import ModelProvider, ModelRequest


@dataclass(slots=True)
class ModelBackedAgent:
    id: AgentId
    provider: ModelProvider

    async def decide(self, context: AgentContext) -> ActionProposal | None:
        response = await self.provider.generate(
            ModelRequest(
                actor_id=self.id,
                observation=context.observation,
                memories=context.memories,
            )
        )
        if response.action_kind is None:
            return None
        return ActionProposal(
            actor_id=self.id,
            kind=response.action_kind,
            parameters=response.parameters,
        )
