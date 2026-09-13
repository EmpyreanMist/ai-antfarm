"""The deliberately small, versioned M0.1 scenario schema."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, PositiveInt, field_validator


class StrictModel(BaseModel):
    """Base for configuration objects that reject accidental fields."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class RunConfig(StrictModel):
    id: Annotated[str, Field(min_length=1)]
    seed: int = 0
    ticks: PositiveInt = 1


class DecisionConfig(StrictModel):
    kind: Annotated[str, Field(min_length=1)]
    parameters: dict[str, int | str | bool | None] = Field(default_factory=dict)


class MockProviderConfig(StrictModel):
    kind: Literal["mock"]
    decisions: dict[str, tuple[DecisionConfig, ...]]


class AgentConfig(StrictModel):
    id: Annotated[str, Field(min_length=1)]


class CounterEnvironmentConfig(StrictModel):
    kind: Literal["counter"]
    initial_value: int = 0


class ScenarioConfig(StrictModel):
    schema_version: Literal[1]
    run: RunConfig
    provider: MockProviderConfig
    agents: tuple[AgentConfig, ...]
    environment: CounterEnvironmentConfig

    @field_validator("agents")
    @classmethod
    def agents_are_nonempty_and_unique(
        cls, agents: tuple[AgentConfig, ...]
    ) -> tuple[AgentConfig, ...]:
        if not agents:
            raise ValueError("at least one agent is required")
        ids = [agent.id for agent in agents]
        if len(ids) != len(set(ids)):
            raise ValueError("agent identifiers must be unique")
        return agents
