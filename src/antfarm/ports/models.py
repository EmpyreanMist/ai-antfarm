"""Provider-neutral model request and response boundary."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Protocol

from antfarm.domain.models import (
    AgentId,
    JsonObject,
    JsonScalar,
    MemoryItem,
    Observation,
)


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
        values: Mapping[str, JsonScalar] = self.parameters
        object.__setattr__(self, "parameters", MappingProxyType(dict(values)))


class ModelProvider(Protocol):
    async def generate(self, request: ModelRequest) -> ModelResponse: ...
