"""Provider-neutral model request and response boundary."""

from collections.abc import Sequence
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Protocol

from antfarm.domain.json_values import JsonObject, freeze_object
from antfarm.domain.models import AgentId, MemoryItem, Observation


@dataclass(frozen=True, slots=True)
class ProviderCapabilities:
    structured_output: bool
    network_required: bool


@dataclass(frozen=True, slots=True)
class ModelRequest:
    actor_id: AgentId
    observation: Observation
    memories: Sequence[MemoryItem]


@dataclass(frozen=True, slots=True)
class ModelResponse:
    action_kind: str | None
    parameters: JsonObject = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        object.__setattr__(self, "parameters", freeze_object(self.parameters))


class ModelProvider(Protocol):
    capabilities: ProviderCapabilities

    async def generate(self, request: ModelRequest) -> ModelResponse: ...
