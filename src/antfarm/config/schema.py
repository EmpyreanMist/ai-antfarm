"""Strict, versioned scenario schema and deterministic normalization."""

import json
from collections.abc import Sequence
from typing import Annotated, Literal, Self, cast

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    NonNegativeInt,
    PositiveInt,
    model_validator,
)

Identifier = Annotated[str, Field(min_length=1, pattern=r"^[a-z][a-z0-9_-]*$")]
EventKind = Annotated[str, Field(min_length=1, pattern=r"^[a-z][a-z0-9_.-]*$")]
EnvironmentVariable = Annotated[str, Field(min_length=1, pattern=r"^[A-Z_][A-Z0-9_]*$")]
Scalar = str | int | float | bool | None
M2_MAX_ACTIVE_AGENTS = 10


class StrictModel(BaseModel):
    """Configuration base that prevents typo-driven silent behavior."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class RunConfig(StrictModel):
    id: Identifier
    seed: int = 0
    ticks: PositiveInt = 1
    active_agents: Annotated[int, Field(ge=1, le=M2_MAX_ACTIVE_AGENTS)] | None = None


class EngineConfig(StrictModel):
    kind: Literal["deterministic_sequential"] = "deterministic_sequential"


class DecisionConfig(StrictModel):
    kind: Identifier
    parameters: dict[str, Scalar] = Field(default_factory=dict)


class MockProviderConfig(StrictModel):
    kind: Literal["mock"]
    decisions: dict[Identifier, tuple[DecisionConfig, ...]] = Field(
        default_factory=dict
    )


class OpenAICompatibleProviderConfig(StrictModel):
    kind: Literal["openai_compatible"]
    base_url: Annotated[str, Field(min_length=1)]
    api_key_env: EnvironmentVariable | None = None
    runtime: Literal["ollama"] | None = None


ProviderConfig = Annotated[
    MockProviderConfig | OpenAICompatibleProviderConfig,
    Field(discriminator="kind"),
]


class ModelConfig(StrictModel):
    provider_ref: Identifier
    model: Annotated[str, Field(min_length=1)]
    timeout_seconds: Annotated[float, Field(gt=0)] = 30.0
    parameters: dict[str, Scalar] = Field(default_factory=dict)


class PersonalityConfig(StrictModel):
    description: Annotated[str, Field(min_length=1)]
    traits: dict[Identifier, Scalar] = Field(default_factory=dict)


class AgentConfig(StrictModel):
    id: Identifier
    model_ref: Identifier
    personality_ref: Identifier | None = None
    cognition_interval: PositiveInt | None = None


class AgentPoolConfig(StrictModel):
    id_prefix: Identifier
    count: PositiveInt
    model_ref: Identifier
    personality_ref: Identifier | None = None
    cognition_interval: PositiveInt | None = None


class ResolvedAgentConfig(StrictModel):
    id: Identifier
    model_ref: Identifier
    personality_ref: Identifier | None = None
    pool_ref: Identifier | None = None
    cognition_interval: PositiveInt | None = None


class IncrementActionConfig(StrictModel):
    kind: Literal["increment"]


class HarvestActionConfig(StrictModel):
    kind: Literal["harvest"]


class ContributeActionConfig(StrictModel):
    kind: Literal["contribute"]


class SayActionConfig(StrictModel):
    kind: Literal["say"]


ActionConfig = Annotated[
    IncrementActionConfig
    | HarvestActionConfig
    | ContributeActionConfig
    | SayActionConfig,
    Field(discriminator="kind"),
]


class CounterEnvironmentConfig(StrictModel):
    kind: Literal["counter"]
    initial_value: int = 0


class CommonsSocialConfig(StrictModel):
    message_max_length: PositiveInt = 500
    history_limit: PositiveInt = 20
    roster_limit: PositiveInt = 100


class CommonsEnvironmentConfig(StrictModel):
    kind: Literal["commons"]
    initial_resource: NonNegativeInt
    initial_endowment: NonNegativeInt = 0
    social: CommonsSocialConfig | None = None


EnvironmentConfig = Annotated[
    CounterEnvironmentConfig | CommonsEnvironmentConfig,
    Field(discriminator="kind"),
]


class MemoryConfig(StrictModel):
    kind: Literal["in_memory"]
    recall_limit: Annotated[int, Field(ge=0)] = 10
    retention_limit: PositiveInt = 100


class SchedulingConfig(StrictModel):
    kind: Literal["stable"]
    interval: PositiveInt | None = 1
    cooldown: Annotated[int, Field(ge=0)] = 0
    event_kinds: tuple[EventKind, ...] = ()
    stagger: bool = False
    max_cognitions_per_tick: PositiveInt | None = None
    failure_retry_cooldown_max: PositiveInt = 8

    @model_validator(mode="after")
    def has_a_due_strategy(self) -> Self:
        if self.interval is None and not self.event_kinds:
            raise ValueError("scheduling requires an interval or event kind")
        if len(set(self.event_kinds)) != len(self.event_kinds):
            raise ValueError("duplicate scheduling event kinds")
        return self


class ActionAllowlistRuleConfig(StrictModel):
    id: Identifier
    kind: Literal["action_allowlist"]
    action_refs: tuple[Identifier, ...]


RuleConfig = ActionAllowlistRuleConfig
MetricIdentifier = Literal[
    "action_count", "rejection_count", "failure_count", "agent_outcomes"
]


class InMemoryStorageConfig(StrictModel):
    kind: Literal["memory"]


class SqliteStorageConfig(StrictModel):
    kind: Literal["sqlite"]
    path: Annotated[str, Field(min_length=1)]


StorageConfig = Annotated[
    InMemoryStorageConfig | SqliteStorageConfig,
    Field(discriminator="kind"),
]


class ObservabilityConfig(StrictModel):
    event_detail: Literal["failures", "all"] = "all"
    include_model_io: Literal[False] = False
    event_buffer_limit: PositiveInt = 1000


class ScenarioConfig(StrictModel):
    schema_version: Literal[1]
    run: RunConfig
    engine: EngineConfig = Field(default_factory=EngineConfig)
    providers: dict[Identifier, ProviderConfig]
    models: dict[Identifier, ModelConfig]
    personalities: dict[Identifier, PersonalityConfig] = Field(default_factory=dict)
    agents: tuple[AgentConfig, ...] = ()
    agent_pools: tuple[AgentPoolConfig, ...] = ()
    actions: tuple[ActionConfig, ...]
    environment: EnvironmentConfig
    memory: MemoryConfig
    scheduling: SchedulingConfig
    rules: tuple[RuleConfig, ...] = ()
    metrics: tuple[MetricIdentifier, ...] = ()
    observability: ObservabilityConfig = Field(default_factory=ObservabilityConfig)
    storage: StorageConfig

    @model_validator(mode="after")
    def references_are_valid(self) -> Self:
        if not self.providers:
            raise ValueError("at least one provider is required")
        if not self.models:
            raise ValueError("at least one model is required")

        for model_id, model in self.models.items():
            if model.provider_ref not in self.providers:
                raise ValueError(
                    f"model {model_id!r} references unknown provider "
                    f"{model.provider_ref!r}"
                )

        expanded_agents = self.expand_agents()
        if not expanded_agents:
            raise ValueError("at least one explicit or pooled agent is required")
        self._require_unique(
            "expanded agent identifiers", [agent.id for agent in expanded_agents]
        )
        if (
            self.run.active_agents is not None
            and self.run.active_agents > len(expanded_agents)
        ):
            raise ValueError(
                "active agent count exceeds the configured population of "
                f"{len(expanded_agents)}"
            )
        for agent in expanded_agents:
            if agent.model_ref not in self.models:
                raise ValueError(
                    f"agent {agent.id!r} references unknown model {agent.model_ref!r}"
                )
            if (
                agent.personality_ref is not None
                and agent.personality_ref not in self.personalities
            ):
                raise ValueError(
                    f"agent {agent.id!r} references unknown personality "
                    f"{agent.personality_ref!r}"
                )

        action_kinds = [action.kind for action in self.actions]
        if not action_kinds:
            raise ValueError("at least one action is required")
        self._require_unique("action kinds", action_kinds)
        action_kind_set = set(action_kinds)
        supported_actions = {"increment"}
        if isinstance(self.environment, CommonsEnvironmentConfig):
            supported_actions = {"harvest", "contribute"}
            if self.environment.social is not None:
                supported_actions.add("say")
        incompatible_actions = action_kind_set.difference(supported_actions)
        if incompatible_actions:
            names = ", ".join(sorted(incompatible_actions))
            raise ValueError(
                f"environment {self.environment.kind!r} does not support actions: "
                f"{names}"
            )
        self._require_unique("rule identifiers", [rule.id for rule in self.rules])
        for rule in self.rules:
            unknown_actions = set(rule.action_refs).difference(action_kind_set)
            if unknown_actions:
                names = ", ".join(sorted(unknown_actions))
                raise ValueError(
                    f"rule {rule.id!r} references unknown actions: {names}"
                )
        self._require_unique("metric identifiers", list(self.metrics))

        agent_models = {agent.id: agent.model_ref for agent in expanded_agents}
        for provider_id, provider in self.providers.items():
            if not isinstance(provider, MockProviderConfig):
                continue
            for agent_id, decisions in provider.decisions.items():
                model_ref = agent_models.get(agent_id)
                if model_ref is None:
                    raise ValueError(
                        f"provider {provider_id!r} has decisions for unknown agent "
                        f"{agent_id!r}"
                    )
                if self.models[model_ref].provider_ref != provider_id:
                    raise ValueError(
                        f"provider {provider_id!r} has decisions for agent "
                        f"{agent_id!r} assigned to another provider"
                    )
                for decision in decisions:
                    if decision.kind not in action_kind_set:
                        raise ValueError(
                            f"decision for agent {agent_id!r} references disabled "
                            f"action {decision.kind!r}"
                        )
        return self

    def expand_agents(self) -> tuple[ResolvedAgentConfig, ...]:
        """Expand pools deterministically without depending on mapping order."""

        expanded = [
            ResolvedAgentConfig(
                id=agent.id,
                model_ref=agent.model_ref,
                personality_ref=agent.personality_ref,
                cognition_interval=agent.cognition_interval,
            )
            for agent in self.agents
        ]
        for pool in self.agent_pools:
            width = max(3, len(str(pool.count)))
            expanded.extend(
                ResolvedAgentConfig(
                    id=f"{pool.id_prefix}-{index:0{width}d}",
                    model_ref=pool.model_ref,
                    personality_ref=pool.personality_ref,
                    pool_ref=pool.id_prefix,
                    cognition_interval=pool.cognition_interval,
                )
                for index in range(1, pool.count + 1)
            )
        return tuple(sorted(expanded, key=lambda agent: agent.id))

    def active_agents(self) -> tuple[ResolvedAgentConfig, ...]:
        """Return the validated active prefix of the configured population."""

        expanded = self.expand_agents()
        count = self.run.active_agents
        return expanded if count is None else expanded[:count]

    def normalized_data(self) -> dict[str, object]:
        """Return a JSON-compatible, deterministically ordered representation."""

        raw = self.model_dump(mode="json", exclude_none=True)
        raw["agents"] = [
            agent.model_dump(mode="json", exclude_none=True)
            for agent in sorted(self.agents, key=lambda agent: agent.id)
        ]
        raw["agent_pools"] = [
            pool.model_dump(mode="json", exclude_none=True)
            for pool in sorted(self.agent_pools, key=lambda pool: pool.id_prefix)
        ]
        raw["actions"] = [
            action.model_dump(mode="json", exclude_none=True)
            for action in sorted(self.actions, key=lambda action: action.kind)
        ]
        raw["rules"] = [
            rule.model_dump(mode="json", exclude_none=True)
            for rule in sorted(self.rules, key=lambda rule: rule.id)
        ]
        raw["metrics"] = sorted(self.metrics)
        raw["expanded_agents"] = [
            agent.model_dump(mode="json", exclude_none=True)
            for agent in self.expand_agents()
        ]
        raw["active_agent_ids"] = [agent.id for agent in self.active_agents()]
        return cast(
            dict[str, object],
            json.loads(json.dumps(raw, sort_keys=True, separators=(",", ":"))),
        )

    def normalized_json(self) -> str:
        return json.dumps(self.normalized_data(), sort_keys=True, separators=(",", ":"))

    @staticmethod
    def _require_unique(label: str, values: Sequence[str]) -> None:
        duplicates = sorted({value for value in values if values.count(value) > 1})
        if duplicates:
            raise ValueError(f"duplicate {label}: {', '.join(duplicates)}")
