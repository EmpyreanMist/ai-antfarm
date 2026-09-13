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
from antfarm.application.scheduler import StableScheduler
from antfarm.config.schema import (
    MockProviderConfig,
    OpenAICompatibleProviderConfig,
    ScenarioConfig,
    SqliteStorageConfig,
)
from antfarm.domain.json_values import JsonObject
from antfarm.domain.models import AgentId, RunId, RunMetadata
from antfarm.environments import CounterEnvironment
from antfarm.ports.models import ModelProvider, ModelResponse
from antfarm.ports.storage import Storage


@dataclass(frozen=True, slots=True)
class ComposedSimulation:
    engine: SimulationEngine
    storage: Storage
    event_bus: InMemoryEventBus


def compose(config: ScenarioConfig) -> ComposedSimulation:
    """Compose only the M0.1 runtime kinds; later kinds fail explicitly."""

    if config.rules:
        raise ValueError("simulation rules are configured but not implemented yet")
    if config.metrics:
        raise ValueError("metric collectors are configured but not implemented yet")

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
    available_actions: tuple[JsonObject, ...] = tuple(
        {
            "kind": action.kind,
            "description": "Increase the shared counter.",
            "parameters": {
                "amount": "A positive integer specifying the increase."
            },
        }
        for action in config.actions
    )
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
        agents[agent_id] = ModelBackedAgent(
            id=agent_id,
            model_ref=agent_config.model_ref,
            provider=provider,
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
    event_bus = InMemoryEventBus()
    engine = SimulationEngine(
        run_id=run_id,
        seed=config.run.seed,
        agents=agents,
        environment=CounterEnvironment(
            initial_value=config.environment.initial_value,
            agent_ids=agents,
        ),
        memory=InMemoryMemoryStore(),
        scheduler=StableScheduler(
            interval=config.scheduling.interval,
            cooldown=config.scheduling.cooldown,
            event_kinds=config.scheduling.event_kinds,
        ),
        event_bus=event_bus,
        storage=storage,
        memory_recall_limit=config.memory.recall_limit,
    )
    return ComposedSimulation(engine=engine, storage=storage, event_bus=event_bus)
