"""Stable transport-neutral contracts for application services."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType

from antfarm.domain.json_values import JsonObject, freeze_object

MAX_PAGE_SIZE = 1_000
DEFAULT_PAGE_SIZE = 100


class ErrorCode(StrEnum):
    INVALID_ARGUMENT = "invalid_argument"
    INVALID_SCENARIO = "invalid_scenario"
    NOT_FOUND = "not_found"
    CONFLICT = "conflict"
    INVALID_STATE = "invalid_state"
    EXECUTION_FAILED = "execution_failed"


class ApplicationError(ValueError):
    """Expected service failure with a stable machine-readable code."""

    def __init__(
        self,
        code: ErrorCode,
        message: str,
        *,
        details: Mapping[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = freeze_object(details or {})


class RunMode(StrEnum):
    BOUNDED = "bounded"
    CONTINUOUS = "continuous"


class RunStatus(StrEnum):
    RUNNING = "running"
    STOPPING = "stopping"
    COMPLETED = "completed"
    STOPPED = "stopped"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class ScenarioTemplateView:
    id: str
    name: str
    description: str
    runtime: str
    featured: bool = False


@dataclass(frozen=True, slots=True)
class ModeView:
    id: str
    name: str
    description: str
    capabilities: tuple[str, ...]
    configuration_hints: JsonObject
    visualization_hints: JsonObject
    templates: tuple[ScenarioTemplateView, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "capabilities", tuple(self.capabilities))
        object.__setattr__(
            self, "configuration_hints", freeze_object(self.configuration_hints)
        )
        object.__setattr__(
            self, "visualization_hints", freeze_object(self.visualization_hints)
        )
        object.__setattr__(self, "templates", tuple(self.templates))


@dataclass(frozen=True, slots=True)
class RunState:
    run_id: str
    mode: RunMode
    status: RunStatus
    tick: int
    failure: ErrorCode | None = None


@dataclass(frozen=True, slots=True)
class RunView:
    run_id: str
    seed: int
    runtime_overrides: JsonObject = field(
        default_factory=lambda: MappingProxyType({})
    )
    scenario: JsonObject = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "runtime_overrides", freeze_object(self.runtime_overrides)
        )
        object.__setattr__(self, "scenario", freeze_object(self.scenario))


@dataclass(frozen=True, slots=True)
class SnapshotView:
    run_id: str
    tick: int
    world: JsonObject
    metrics: JsonObject

    def __post_init__(self) -> None:
        object.__setattr__(self, "world", freeze_object(self.world))
        object.__setattr__(self, "metrics", freeze_object(self.metrics))


@dataclass(frozen=True, slots=True)
class EventView:
    schema_version: int
    event_id: str
    run_id: str
    sequence: int
    tick: int
    kind: str
    actor_id: str | None
    causation_id: str | None
    payload: JsonObject

    def __post_init__(self) -> None:
        object.__setattr__(self, "payload", freeze_object(self.payload))


@dataclass(frozen=True, slots=True)
class EventQuery:
    run_id: str
    after: int = 0
    limit: int = DEFAULT_PAGE_SIZE
    kinds: frozenset[str] = frozenset()
    actor_id: str | None = None
    from_tick: int | None = None
    to_tick: int | None = None

    def __post_init__(self) -> None:
        if not self.run_id:
            raise ApplicationError(ErrorCode.INVALID_ARGUMENT, "run_id is required")
        if self.after < 0:
            raise ApplicationError(
                ErrorCode.INVALID_ARGUMENT, "after must not be negative"
            )
        _validate_page_size(self.limit)
        if self.from_tick is not None and self.from_tick < 0:
            raise ApplicationError(
                ErrorCode.INVALID_ARGUMENT, "from_tick must not be negative"
            )
        if self.to_tick is not None and self.to_tick < 0:
            raise ApplicationError(
                ErrorCode.INVALID_ARGUMENT, "to_tick must not be negative"
            )
        if (
            self.from_tick is not None
            and self.to_tick is not None
            and self.from_tick > self.to_tick
        ):
            raise ApplicationError(
                ErrorCode.INVALID_ARGUMENT, "from_tick must not exceed to_tick"
            )
        if any(not kind for kind in self.kinds):
            raise ApplicationError(
                ErrorCode.INVALID_ARGUMENT, "event kinds must not be empty"
            )
        object.__setattr__(self, "kinds", frozenset(self.kinds))


@dataclass(frozen=True, slots=True)
class EventPage:
    items: Sequence[EventView]
    next_after: int | None

    def __post_init__(self) -> None:
        object.__setattr__(self, "items", tuple(self.items))


@dataclass(frozen=True, slots=True)
class AgentQuery:
    run_id: str
    offset: int = 0
    limit: int = DEFAULT_PAGE_SIZE

    def __post_init__(self) -> None:
        if not self.run_id:
            raise ApplicationError(ErrorCode.INVALID_ARGUMENT, "run_id is required")
        if self.offset < 0:
            raise ApplicationError(
                ErrorCode.INVALID_ARGUMENT, "offset must not be negative"
            )
        _validate_page_size(self.limit)


@dataclass(frozen=True, slots=True)
class AgentPage[T]:
    items: Sequence[T]
    next_offset: int | None

    def __post_init__(self) -> None:
        object.__setattr__(self, "items", tuple(self.items))


@dataclass(frozen=True, slots=True)
class EntityQuery:
    run_id: str
    offset: int = 0
    limit: int = DEFAULT_PAGE_SIZE

    def __post_init__(self) -> None:
        if not self.run_id:
            raise ApplicationError(ErrorCode.INVALID_ARGUMENT, "run_id is required")
        if self.offset < 0:
            raise ApplicationError(
                ErrorCode.INVALID_ARGUMENT, "offset must not be negative"
            )
        _validate_page_size(self.limit)


@dataclass(frozen=True, slots=True)
class EntityPage[T]:
    items: Sequence[T]
    next_offset: int | None

    def __post_init__(self) -> None:
        object.__setattr__(self, "items", tuple(self.items))


@dataclass(frozen=True, slots=True)
class RunSummary:
    run_id: str
    ticks: int
    final_state: JsonObject
    events: Sequence[EventView]
    metrics: JsonObject = field(default_factory=lambda: MappingProxyType({}))
    active_agent_count: int = 0
    checkpoint: str = "memory (not durable)"

    def __post_init__(self) -> None:
        object.__setattr__(self, "final_state", freeze_object(self.final_state))
        object.__setattr__(self, "events", tuple(self.events))
        object.__setattr__(self, "metrics", freeze_object(self.metrics))


def _validate_page_size(limit: int) -> None:
    if not 1 <= limit <= MAX_PAGE_SIZE:
        raise ApplicationError(
            ErrorCode.INVALID_ARGUMENT,
            f"limit must be between 1 and {MAX_PAGE_SIZE}",
        )
