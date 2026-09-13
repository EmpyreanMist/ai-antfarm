"""Small immutable values used by the M0.1 execution lifecycle."""

from collections.abc import Sequence
from dataclasses import dataclass, field
from types import MappingProxyType

from antfarm.domain.json_values import JsonObject, freeze_object


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


@dataclass(frozen=True, slots=True)
class ActionProposal:
    actor_id: AgentId
    kind: str
    parameters: JsonObject = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        if not self.kind:
            raise ValueError("action proposal kind must not be empty")
        object.__setattr__(self, "parameters", freeze_object(self.parameters))


@dataclass(frozen=True, slots=True)
class ValidatedAction:
    actor_id: AgentId
    kind: str
    parameters: JsonObject = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        if not self.kind:
            raise ValueError("validated action kind must not be empty")
        object.__setattr__(self, "parameters", freeze_object(self.parameters))


@dataclass(frozen=True, slots=True)
class ActionResult:
    success: bool
    payload: JsonObject = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        object.__setattr__(self, "payload", freeze_object(self.payload))


@dataclass(frozen=True, slots=True)
class Observation:
    agent_id: AgentId
    tick: Tick
    state: JsonObject

    def __post_init__(self) -> None:
        object.__setattr__(self, "state", freeze_object(self.state))


@dataclass(frozen=True, slots=True)
class MemoryItem:
    kind: str
    content: JsonObject

    def __post_init__(self) -> None:
        object.__setattr__(self, "content", freeze_object(self.content))


@dataclass(frozen=True, slots=True)
class AgentContext:
    observation: Observation
    memories: Sequence[MemoryItem]

    def __post_init__(self) -> None:
        object.__setattr__(self, "memories", tuple(self.memories))


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
        if self.schema_version != 1:
            raise ValueError("unsupported event schema version")
        if not self.event_id or not self.kind:
            raise ValueError("event id and kind must not be empty")
        object.__setattr__(self, "payload", freeze_object(self.payload))


@dataclass(frozen=True, slots=True)
class SimulationSnapshot:
    tick: Tick
    world: JsonObject
    memory: JsonObject = field(default_factory=lambda: MappingProxyType({}))
    scheduler: JsonObject = field(default_factory=lambda: MappingProxyType({}))
    engine: JsonObject = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        object.__setattr__(self, "world", freeze_object(self.world))
        object.__setattr__(self, "memory", freeze_object(self.memory))
        object.__setattr__(self, "scheduler", freeze_object(self.scheduler))
        object.__setattr__(self, "engine", freeze_object(self.engine))


@dataclass(frozen=True, slots=True)
class RunLimit:
    ticks: int

    def __post_init__(self) -> None:
        if self.ticks < 1:
            raise ValueError("run limit ticks must be positive")


@dataclass(frozen=True, slots=True)
class RunResult:
    snapshot: SimulationSnapshot
    events: Sequence[Event]

    def __post_init__(self) -> None:
        object.__setattr__(self, "events", tuple(self.events))


@dataclass(frozen=True, slots=True)
class MemoryQuery:
    limit: int

    def __post_init__(self) -> None:
        if self.limit < 0:
            raise ValueError("memory query limit must not be negative")


@dataclass(frozen=True, slots=True)
class CognitionOutcome:
    agent_id: AgentId
    tick: Tick
    kind: str


@dataclass(frozen=True, slots=True)
class RunMetadata:
    run_id: RunId
    seed: int


@dataclass(frozen=True, slots=True)
class StoredCheckpoint:
    run_id: RunId
    snapshot: SimulationSnapshot
