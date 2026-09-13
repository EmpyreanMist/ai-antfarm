"""Closed composition root for the runtime components implemented so far."""

from dataclasses import dataclass

from antfarm.adapters.events import InMemoryEventBus
from antfarm.adapters.memory import InMemoryMemoryStore
from antfarm.adapters.models import MockModelProvider
from antfarm.adapters.storage import InMemoryStorage
from antfarm.application.agent import ModelBackedAgent
from antfarm.application.engine import SimulationEngine
from antfarm.application.scheduler import StableScheduler
from antfarm.config.schema import MockProviderConfig, ScenarioConfig
from antfarm.domain.models import AgentId, RunId, RunMetadata
from antfarm.environments import CounterEnvironment
from antfarm.ports.models import ModelProvider, ModelResponse


@dataclass(frozen=True, slots=True)
class ComposedSimulation:
    engine: SimulationEngine
    storage: InMemoryStorage
    event_bus: InMemoryEventBus


def compose(config: ScenarioConfig) -> ComposedSimulation:
    """Compose only the M0.1 runtime kinds; later kinds fail explicitly."""

    if config.storage.kind != "memory":
        raise ValueError("sqlite storage is configured but not implemented yet")

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
    agents: dict[AgentId, ModelBackedAgent] = {}
    for agent_config in resolved_agents:
        model = config.models[agent_config.model_ref]
        provider = providers.get(model.provider_ref)
        if provider is None:
            raise ValueError(
                f"provider kind for model {agent_config.model_ref!r} is not implemented"
            )
        agent_id = AgentId(agent_config.id)
        agents[agent_id] = ModelBackedAgent(
            id=agent_id,
            model_ref=agent_config.model_ref,
            provider=provider,
        )

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
