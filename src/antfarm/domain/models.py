"""Small immutable values used by the M0.1 execution lifecycle."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType

type JsonScalar = str | int | float | bool | None
type JsonObject = Mapping[str, JsonScalar]


class AgentId(str):
    def __new__(cls, value: str) -> "AgentId":
        if not value:
            raise ValueError("agent id must not be empty")
        return super().__new__(cls, value)


class RunId(str):
    def __new__(cls, value: str) -> "RunId":
        if not value:
            raise ValueError("run id must not be empty")
        return super().__new__(cls, value)


class Tick(int):
    def __new__(cls, value: int) -> "Tick":
        if value < 0:
            raise ValueError("tick must not be negative")
        return super().__new__(cls, value)


class EventSequence(int):
    def __new__(cls, value: int) -> "EventSequence":
        if value < 1:
            raise ValueError("event sequence must be positive")
        return super().__new__(cls, value)


def _immutable(values: Mapping[str, JsonScalar]) -> JsonObject:
    return MappingProxyType(dict(values))


@dataclass(frozen=True, slots=True)
class ActionProposal:
    actor_id: AgentId
    kind: str
    parameters: JsonObject = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        object.__setattr__(self, "parameters", _immutable(self.parameters))


@dataclass(frozen=True, slots=True)
class ValidatedAction:
    actor_id: AgentId
    kind: str
    parameters: JsonObject = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        object.__setattr__(self, "parameters", _immutable(self.parameters))


@dataclass(frozen=True, slots=True)
class ActionResult:
    success: bool
    payload: JsonObject = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        object.__setattr__(self, "payload", _immutable(self.payload))


@dataclass(frozen=True, slots=True)
class Observation:
    agent_id: AgentId
    tick: Tick
    state: JsonObject

    def __post_init__(self) -> None:
        object.__setattr__(self, "state", _immutable(self.state))


@dataclass(frozen=True, slots=True)
class MemoryItem:
    kind: str
    content: JsonObject

    def __post_init__(self) -> None:
        object.__setattr__(self, "content", _immutable(self.content))


@dataclass(frozen=True, slots=True)
class AgentContext:
    observation: Observation
    memories: Sequence[MemoryItem]


@dataclass(frozen=True, slots=True)
class ValidationResult:
    action: ValidatedAction | None
    reason: str | None = None

    @property
    def accepted(self) -> bool:
        return self.action is not None


@dataclass(frozen=True, slots=True)
class Event:
    schema_version: int
    event_id: str
    run_id: RunId
    sequence: EventSequence
    tick: Tick
    kind: str
    actor_id: AgentId | None
    causation_id: str | None
    payload: JsonObject = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        object.__setattr__(self, "payload", _immutable(self.payload))


@dataclass(frozen=True, slots=True)
class SimulationSnapshot:
    tick: Tick
    world: JsonObject

    def __post_init__(self) -> None:
        object.__setattr__(self, "world", _immutable(self.world))
