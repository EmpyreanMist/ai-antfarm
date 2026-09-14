"""Small immutable values used by the M0.1 execution lifecycle."""

from collections.abc import Mapping, Sequence
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
class AgentIdentity:
    """Public, immutable identity supplied to an agent's model request."""

    id: AgentId


@dataclass(frozen=True, slots=True)
class AgentPersonality:
    """Private, immutable personality context for one agent."""

    description: str
    traits: JsonObject = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        if not self.description:
            raise ValueError("agent personality description must not be empty")
        object.__setattr__(self, "traits", freeze_object(self.traits))


def _validated_statements(label: str, values: Sequence[str]) -> tuple[str, ...]:
    statements = tuple(values)
    if any(not value.strip() for value in statements):
        raise ValueError(f"agent profile {label} must not contain empty text")
    return statements


@dataclass(frozen=True, slots=True)
class ProfileIdentity:
    display_name: str
    description: str | None = None

    def __post_init__(self) -> None:
        if not self.display_name.strip():
            raise ValueError("agent profile display name must not be empty")
        if self.description is not None and not self.description.strip():
            raise ValueError("agent profile identity description must not be empty")


@dataclass(frozen=True, slots=True)
class ProfilePersonality:
    description: str
    qualities: Sequence[str] = ()

    def __post_init__(self) -> None:
        if not self.description.strip():
            raise ValueError("agent profile personality description must not be empty")
        object.__setattr__(
            self, "qualities", _validated_statements("qualities", self.qualities)
        )


@dataclass(frozen=True, slots=True)
class ProfileGoals:
    statements: Sequence[str]

    def __post_init__(self) -> None:
        statements = _validated_statements("goals", self.statements)
        if not statements:
            raise ValueError("agent profile goals must not be empty")
        object.__setattr__(self, "statements", statements)


@dataclass(frozen=True, slots=True)
class ProfileBeliefs:
    statements: Sequence[str]

    def __post_init__(self) -> None:
        statements = _validated_statements("beliefs", self.statements)
        if not statements:
            raise ValueError("agent profile beliefs must not be empty")
        object.__setattr__(self, "statements", statements)


@dataclass(frozen=True, slots=True)
class ProfileValues:
    statements: Sequence[str]

    def __post_init__(self) -> None:
        statements = _validated_statements("values", self.statements)
        if not statements:
            raise ValueError("agent profile values must not be empty")
        object.__setattr__(self, "statements", statements)


@dataclass(frozen=True, slots=True)
class CommunicationPreferences:
    style: str | None = None
    preferences: Sequence[str] = ()

    def __post_init__(self) -> None:
        if self.style is not None and not self.style.strip():
            raise ValueError("agent profile communication style must not be empty")
        preferences = _validated_statements(
            "communication preferences", self.preferences
        )
        if self.style is None and not preferences:
            raise ValueError(
                "agent profile communication preferences must not be empty"
            )
        object.__setattr__(self, "preferences", preferences)


@dataclass(frozen=True, slots=True)
class BehavioralTraits:
    generosity: float | None = None
    greed: float | None = None
    selfishness: float | None = None
    empathy: float | None = None
    assertiveness: float | None = None
    agreeableness: float | None = None
    honesty: float | None = None
    conformity: float | None = None
    patience: float | None = None
    impulsiveness: float | None = None
    risk_tolerance: float | None = None
    competitiveness: float | None = None
    envy: float | None = None
    aggression: float | None = None
    trust: float | None = None
    ambition: float | None = None
    materialism: float | None = None
    fairness: float | None = None
    forgiveness: float | None = None
    sociability: float | None = None

    def __post_init__(self) -> None:
        values = tuple(
            getattr(self, field_name) for field_name in self.__dataclass_fields__
        )
        if not any(value is not None for value in values):
            raise ValueError("agent profile behavioral traits must not be empty")
        if any(
            value is not None and (isinstance(value, bool) or not 0 <= value <= 1)
            for value in values
        ):
            raise ValueError("agent profile behavioral traits must be between 0 and 1")


@dataclass(frozen=True, slots=True)
class SocialStatus:
    label: str | None = None
    roles: Sequence[str] = ()
    standing: float | None = None

    def __post_init__(self) -> None:
        if self.label is not None and not self.label.strip():
            raise ValueError("agent profile social status label must not be empty")
        roles = _validated_statements("social status roles", self.roles)
        if self.standing is not None and (
            isinstance(self.standing, bool) or not 0 <= self.standing <= 1
        ):
            raise ValueError("agent profile social standing must be between 0 and 1")
        if self.label is None and not roles and self.standing is None:
            raise ValueError("agent profile social status must not be empty")
        object.__setattr__(self, "roles", roles)


@dataclass(frozen=True, slots=True)
class Reputation:
    """Static reputation facts; evolution belongs to a later milestone."""

    score: float | None = None
    labels: Sequence[str] = ()

    def __post_init__(self) -> None:
        labels = _validated_statements("reputation labels", self.labels)
        if self.score is not None and (
            isinstance(self.score, bool) or not 0 <= self.score <= 1
        ):
            raise ValueError("agent profile reputation score must be between 0 and 1")
        if self.score is None and not labels:
            raise ValueError("agent profile reputation must not be empty")
        object.__setattr__(self, "labels", labels)


@dataclass(frozen=True, slots=True)
class Relationship:
    """One static, directed relationship from the profiled agent."""

    kind: str
    strength: float | None = None

    def __post_init__(self) -> None:
        if not self.kind.strip():
            raise ValueError("agent profile relationship kind must not be empty")
        if self.strength is not None and (
            isinstance(self.strength, bool) or not 0 <= self.strength <= 1
        ):
            raise ValueError(
                "agent profile relationship strength must be between 0 and 1"
            )


@dataclass(frozen=True, slots=True)
class EconomicSituation:
    """An agent's configured economic facts, distinct from mutable world state."""

    money: int | None = None
    resources: Mapping[str, int] = field(default_factory=lambda: MappingProxyType({}))
    recurring_income: int | None = None
    occupation: str | None = None

    def __post_init__(self) -> None:
        resources = dict(self.resources)
        values = (self.money, self.recurring_income, *resources.values())
        if any(
            isinstance(value, bool) or not isinstance(value, int) or value < 0
            for value in values
            if value is not None
        ):
            raise ValueError("economic amounts must be non-negative integers")
        if any(not name.strip() for name in resources):
            raise ValueError("economic resource names must not be empty")
        if self.occupation is not None and not self.occupation.strip():
            raise ValueError("economic occupation must not be empty")
        if (
            self.money is None
            and not resources
            and self.recurring_income is None
            and self.occupation is None
        ):
            raise ValueError("economic situation must not be empty")
        object.__setattr__(self, "resources", MappingProxyType(resources))


@dataclass(frozen=True, slots=True)
class InformationVisibility:
    """Public/private metadata for independently observable profile dimensions."""

    wealth: str = "private"
    possessions: str = "private"
    occupation: str = "private"
    status: str = "private"
    reputation: str = "private"
    relationships: str = "private"
    health: str = "private"
    group_membership: str = "private"

    def __post_init__(self) -> None:
        if any(
            getattr(self, name) not in {"private", "public"}
            for name in self.__dataclass_fields__
        ):
            raise ValueError("information visibility must be private or public")


@dataclass(frozen=True, slots=True)
class PublicAgentProfile:
    """The typed subset of profile facts allowed into other agents' observations."""

    economics: EconomicSituation | None = None
    social_status: SocialStatus | None = None
    reputation: Reputation | None = None
    relationships: Mapping[AgentId, Relationship] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def __post_init__(self) -> None:
        relationships = MappingProxyType(dict(self.relationships))
        if (
            self.economics is None
            and self.social_status is None
            and self.reputation is None
            and not relationships
        ):
            raise ValueError("public agent profile must not be empty")
        object.__setattr__(self, "relationships", relationships)


@dataclass(frozen=True, slots=True)
class PrivateInformation:
    statements: Sequence[str]

    def __post_init__(self) -> None:
        statements = _validated_statements("private information", self.statements)
        if not statements:
            raise ValueError("agent profile private information must not be empty")
        object.__setattr__(self, "statements", statements)


@dataclass(frozen=True, slots=True)
class AgentProfile:
    """Private, immutable, composable behavioral context for one agent."""

    identity: ProfileIdentity | None = None
    personality: ProfilePersonality | None = None
    goals: ProfileGoals | None = None
    beliefs: ProfileBeliefs | None = None
    values: ProfileValues | None = None
    communication: CommunicationPreferences | None = None
    traits: BehavioralTraits | None = None
    social_status: SocialStatus | None = None
    reputation: Reputation | None = None
    relationships: Mapping[AgentId, Relationship] = field(
        default_factory=lambda: MappingProxyType({})
    )
    economics: EconomicSituation | None = None
    private_information: PrivateInformation | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "relationships", MappingProxyType(dict(self.relationships))
        )
        if not any(
            bool(getattr(self, field_name))
            for field_name in self.__dataclass_fields__
        ):
            raise ValueError("agent profile must contain at least one section")


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
    metrics: JsonObject = field(default_factory=lambda: MappingProxyType({}))
    engine: JsonObject = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        object.__setattr__(self, "world", freeze_object(self.world))
        object.__setattr__(self, "memory", freeze_object(self.memory))
        object.__setattr__(self, "scheduler", freeze_object(self.scheduler))
        object.__setattr__(self, "metrics", freeze_object(self.metrics))
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
    runtime_overrides: JsonObject = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "runtime_overrides", freeze_object(self.runtime_overrides)
        )


@dataclass(frozen=True, slots=True)
class StoredRun:
    metadata: RunMetadata
    scenario: JsonObject

    def __post_init__(self) -> None:
        object.__setattr__(self, "scenario", freeze_object(self.scenario))


@dataclass(frozen=True, slots=True)
class StoredCheckpoint:
    run_id: RunId
    snapshot: SimulationSnapshot
