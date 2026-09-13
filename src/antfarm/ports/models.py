"""Provider-neutral model request and response boundary."""

from collections.abc import Sequence
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Protocol

from antfarm.domain.json_values import JsonObject, freeze_object
from antfarm.domain.models import (
    AgentId,
    AgentIdentity,
    AgentPersonality,
    MemoryItem,
    Observation,
)


@dataclass(frozen=True, slots=True)
class ProviderCapabilities:
    structured_output: bool
    network_required: bool


@dataclass(frozen=True, slots=True)
class ModelRequest:
    identity: AgentIdentity
    personality: AgentPersonality | None
    observation: Observation
    memories: Sequence[MemoryItem]
    available_actions: Sequence[JsonObject] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "memories", tuple(self.memories))
        object.__setattr__(
            self,
            "available_actions",
            tuple(freeze_object(action) for action in self.available_actions),
        )

    @property
    def actor_id(self) -> AgentId:
        """Compatibility accessor for providers that route by agent ID."""

        return self.identity.id


@dataclass(frozen=True, slots=True)
class ModelResponse:
    action_kind: str | None
    parameters: JsonObject = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        object.__setattr__(self, "parameters", freeze_object(self.parameters))


class MalformedModelResponseError(ValueError):
    """A provider returned data that does not satisfy the model boundary."""


class ModelProvider(Protocol):
    capabilities: ProviderCapabilities

    async def generate(self, request: ModelRequest) -> ModelResponse: ...

    async def close(self) -> None: ...
