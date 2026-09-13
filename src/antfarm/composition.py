"""Closed composition root for the supported M0.1 component kinds."""

from dataclasses import dataclass

from antfarm.adapters.events import InMemoryEventBus
from antfarm.adapters.memory import InMemoryMemoryStore
from antfarm.adapters.models import MockModelProvider
from antfarm.adapters.storage import InMemoryStorage
from antfarm.application.agent import ModelBackedAgent
from antfarm.application.engine import SimulationEngine
from antfarm.application.scheduler import StableScheduler
from antfarm.config.schema import ScenarioConfig
from antfarm.domain.models import AgentId, RunId
from antfarm.environments import CounterEnvironment
from antfarm.ports.models import ModelResponse


@dataclass(frozen=True, slots=True)
class ComposedSimulation:
    engine: SimulationEngine
    storage: InMemoryStorage
    event_bus: InMemoryEventBus


def compose(config: ScenarioConfig) -> ComposedSimulation:
    agent_ids = tuple(AgentId(agent.id) for agent in config.agents)
    configured_decisions = {
        AgentId(agent_id): tuple(
            ModelResponse(
                action_kind=decision.kind,
                parameters=decision.parameters,
            )
            for decision in decisions
        )
        for agent_id, decisions in config.provider.decisions.items()
    }
    unknown_decision_agents = set(configured_decisions).difference(agent_ids)
    if unknown_decision_agents:
        names = ", ".join(sorted(unknown_decision_agents))
        raise ValueError(f"mock decisions reference unknown agents: {names}")

    provider = MockModelProvider(configured_decisions)
    agents = {
        agent_id: ModelBackedAgent(id=agent_id, provider=provider)
        for agent_id in agent_ids
    }
    storage = InMemoryStorage()
    run_id = RunId(config.run.id)
    storage.create_run(run_id, config.model_dump(mode="json"))
    event_bus = InMemoryEventBus()
    engine = SimulationEngine(
        run_id=run_id,
        seed=config.run.seed,
        agents=agents,
        environment=CounterEnvironment(
            initial_value=config.environment.initial_value,
            agent_ids=agent_ids,
        ),
        memory=InMemoryMemoryStore(),
        scheduler=StableScheduler(),
        event_bus=event_bus,
        storage=storage,
    )
    return ComposedSimulation(engine=engine, storage=storage, event_bus=event_bus)
