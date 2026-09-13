"""Closed composition root for the runtime components implemented so far."""

import os
from dataclasses import dataclass

from antfarm.adapters.events import InMemoryEventBus
from antfarm.adapters.memory import InMemoryMemoryStore
from antfarm.adapters.models import (
    MockModelProvider,
    OpenAICompatibleModelProvider,
)
from antfarm.adapters.storage import InMemoryStorage, SQLiteStorage
from antfarm.application.agent import ModelBackedAgent
from antfarm.application.engine import SimulationEngine
from antfarm.application.metrics import BuiltInMetricCollector
from antfarm.application.scheduler import StableScheduler
from antfarm.config.schema import (
    CommonsEnvironmentConfig,
    MockProviderConfig,
    OpenAICompatibleProviderConfig,
    ScenarioConfig,
    SqliteStorageConfig,
)
from antfarm.domain.json_values import JsonObject
from antfarm.domain.models import AgentId, AgentPersonality, RunId, RunMetadata
from antfarm.domain.protocols import Environment
from antfarm.environments import CommonsEnvironment, CounterEnvironment
from antfarm.ports.models import ModelProvider, ModelResponse
from antfarm.ports.storage import Storage


@dataclass(frozen=True, slots=True)
class ComposedSimulation:
    engine: SimulationEngine
    storage: Storage
    event_bus: InMemoryEventBus
    metrics: BuiltInMetricCollector
    providers: tuple[ModelProvider, ...]

    async def close(self) -> None:
        for provider in self.providers:
            await provider.close()
        self.storage.close()


def compose(config: ScenarioConfig) -> ComposedSimulation:
    """Compose only the M0.1 runtime kinds; later kinds fail explicitly."""

    if config.rules:
        raise ValueError("simulation rules are configured but not implemented yet")
    providers: dict[str, ModelProvider] = {}
    for provider_id, provider_config in config.providers.items():
        if not isinstance(provider_config, MockProviderConfig):
            continue
        decisions = {
            AgentId(agent_id): tuple(
                ModelResponse(
                    action_kind=decision.kind,
                    parameters=decision.parameters,
                )
                for decision in agent_decisions
            )
            for agent_id, agent_decisions in provider_config.decisions.items()
        }
        providers[provider_id] = MockModelProvider(decisions)

    resolved_agents = config.expand_agents()
    action_catalog: dict[str, JsonObject] = {
        "increment": {
            "kind": "increment",
            "description": "Increase the shared counter.",
            "parameters": {"amount": "A positive integer."},
        },
        "harvest": {
            "kind": "harvest",
            "description": "Move resource from the commons to your holding.",
            "parameters": {"amount": "A positive integer no greater than resource."},
        },
        "contribute": {
            "kind": "contribute",
            "description": "Move resource from your holding into the commons.",
            "parameters": {
                "amount": "A positive integer no greater than own_holding."
            },
        },
        "say": {
            "kind": "say",
            "description": "Publish one message to the shared public room.",
            "parameters": {"text": "Bounded, non-empty message text."},
        },
    }
    available_actions = tuple(action_catalog[action.kind] for action in config.actions)
    used_model_ids = sorted({agent.model_ref for agent in resolved_agents})
    models: dict[str, ModelProvider] = {}
    for model_id in used_model_ids:
        model_config = config.models[model_id]
        provider_config = config.providers[model_config.provider_ref]
        if isinstance(provider_config, MockProviderConfig):
            models[model_id] = providers[model_config.provider_ref]
            continue
        if isinstance(provider_config, OpenAICompatibleProviderConfig):
            api_key = None
            if provider_config.api_key_env is not None:
                api_key = os.environ.get(provider_config.api_key_env)
                if not api_key:
                    raise ValueError(
                        "required provider API key environment variable "
                        f"{provider_config.api_key_env!r} is not set"
                    )
            models[model_id] = OpenAICompatibleModelProvider(
                base_url=provider_config.base_url,
                model=model_config.model,
                timeout_seconds=model_config.timeout_seconds,
                parameters=model_config.parameters,
                api_key=api_key,
            )

    agents: dict[AgentId, ModelBackedAgent] = {}
    for agent_config in resolved_agents:
        provider = models.get(agent_config.model_ref)
        if provider is None:
            raise ValueError(
                f"provider kind for model {agent_config.model_ref!r} is not implemented"
            )
        agent_id = AgentId(agent_config.id)
        personality = None
        if agent_config.personality_ref is not None:
            personality_config = config.personalities[agent_config.personality_ref]
            personality = AgentPersonality(
                description=personality_config.description,
                traits=personality_config.traits,
            )
        agents[agent_id] = ModelBackedAgent(
            id=agent_id,
            model_ref=agent_config.model_ref,
            provider=provider,
            personality=personality,
            available_actions=available_actions,
        )

    storage: Storage
    if isinstance(config.storage, SqliteStorageConfig):
        storage = SQLiteStorage(config.storage.path)
    else:
        storage = InMemoryStorage()
    run_id = RunId(config.run.id)
    storage.create_run(
        RunMetadata(run_id=run_id, seed=config.run.seed),
        config.normalized_data(),
    )
    event_bus = InMemoryEventBus(
        max_retained_events=config.observability.event_buffer_limit
    )
    environment: Environment
    if isinstance(config.environment, CommonsEnvironmentConfig):
        environment = CommonsEnvironment(
            initial_resource=config.environment.initial_resource,
            initial_endowment=config.environment.initial_endowment,
            agent_ids=agents,
            social=config.environment.social is not None,
            message_max_length=(
                config.environment.social.message_max_length
                if config.environment.social is not None
                else 500
            ),
            history_limit=(
                config.environment.social.history_limit
                if config.environment.social is not None
                else 20
            ),
            roster_limit=(
                config.environment.social.roster_limit
                if config.environment.social is not None
                else 100
            ),
        )
    else:
        environment = CounterEnvironment(
            initial_value=config.environment.initial_value,
            agent_ids=agents,
        )
    engine = SimulationEngine(
        run_id=run_id,
        seed=config.run.seed,
        agents=agents,
        environment=environment,
        memory=InMemoryMemoryStore(
            max_items_per_agent=config.memory.retention_limit
        ),
        scheduler=StableScheduler(
            interval=config.scheduling.interval,
            cooldown=config.scheduling.cooldown,
            event_kinds=config.scheduling.event_kinds,
            agent_intervals={
                AgentId(agent.id): agent.cognition_interval
                for agent in resolved_agents
                if agent.cognition_interval is not None
            },
            stagger=config.scheduling.stagger,
            max_cognitions_per_tick=(
                config.scheduling.max_cognitions_per_tick
            ),
            failure_retry_cooldown_max=(
                config.scheduling.failure_retry_cooldown_max
            ),
        ),
        event_bus=event_bus,
        storage=storage,
        metrics=BuiltInMetricCollector(
            config.metrics,
            action_kinds=tuple(action.kind for action in config.actions),
            agent_ids=tuple(str(agent_id) for agent_id in agents),
        ),
        memory_recall_limit=config.memory.recall_limit,
    )
    return ComposedSimulation(
        engine=engine,
        storage=storage,
        event_bus=event_bus,
        metrics=engine.metrics,
        providers=tuple(dict.fromkeys(models.values())),
    )
