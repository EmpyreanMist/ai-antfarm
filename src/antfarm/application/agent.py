"""A minimal agent that delegates cognition to a model provider."""

from dataclasses import dataclass

from antfarm.domain.json_values import JsonObject
from antfarm.domain.models import ActionProposal, AgentContext, AgentId
from antfarm.ports.models import (
    MalformedModelResponseError,
    ModelProvider,
    ModelRequest,
)


class MalformedDecisionError(ValueError):
    """A provider response could not be converted to a domain proposal."""


@dataclass(slots=True)
class ModelBackedAgent:
    id: AgentId
    model_ref: str
    provider: ModelProvider
    available_actions: tuple[JsonObject, ...] = ()

    async def decide(self, context: AgentContext) -> ActionProposal | None:
        try:
            response = await self.provider.generate(
                ModelRequest(
                    actor_id=self.id,
                    observation=context.observation,
                    memories=context.memories,
                    available_actions=self.available_actions,
                )
            )
        except MalformedModelResponseError as error:
            raise MalformedDecisionError(str(error)) from error
        if response.action_kind is None:
            return None
        try:
            return ActionProposal(
                actor_id=self.id,
                kind=response.action_kind,
                parameters=response.parameters,
            )
        except (TypeError, ValueError) as error:
            raise MalformedDecisionError from error
