"""The deterministic, sequential M0.1 simulation engine."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from random import Random

from antfarm.application.scheduler import CognitionScheduler, ScheduleContext
from antfarm.domain.models import (
    AgentContext,
    AgentId,
    Event,
    EventSequence,
    JsonObject,
    MemoryItem,
    RunId,
    SimulationSnapshot,
    Tick,
)
from antfarm.domain.protocols import Agent, Environment
from antfarm.ports.events import EventBus
from antfarm.ports.memory import MemoryStore
from antfarm.ports.storage import Storage


@dataclass(frozen=True, slots=True)
class StepResult:
    snapshot: SimulationSnapshot
    events: Sequence[Event]


class SimulationEngine:
    def __init__(
        self,
        *,
        run_id: RunId,
        seed: int,
        agents: Mapping[AgentId, Agent],
        environment: Environment,
        memory: MemoryStore,
        scheduler: CognitionScheduler,
        event_bus: EventBus,
        storage: Storage,
    ) -> None:
        self._run_id = run_id
        self._agents = dict(agents)
        self._environment = environment
        self._memory = memory
        self._scheduler = scheduler
        self._event_bus = event_bus
        self._storage = storage
        self._rng = Random(seed)
        self._tick = Tick(0)
        self._sequence = 0

    async def step(self) -> StepResult:
        tick = Tick(int(self._tick) + 1)
        events: list[Event] = [self._event(tick, "tick.started")]
        selected = self._scheduler.select(
            ScheduleContext(tick=tick, agent_ids=tuple(self._agents))
        )

        for agent_id in selected:
            agent = self._agents[agent_id]
            observation = self._environment.observe(agent_id, tick)
            observation_event = self._event(
                tick,
                "observation.created",
                actor_id=agent_id,
                payload=observation.state,
            )
            events.append(observation_event)
            context = AgentContext(
                observation=observation,
                memories=tuple(self._memory.recall(agent_id, limit=10)),
            )
            try:
                proposal = await agent.decide(context)
            except Exception as error:  # Provider failures become inert events.
                events.append(
                    self._event(
                        tick,
                        "cognition.failed",
                        actor_id=agent_id,
                        causation_id=observation_event.event_id,
                        payload={"reason": type(error).__name__},
                    )
                )
                continue

            if proposal is None:
                events.append(
                    self._event(
                        tick,
                        "action.noop",
                        actor_id=agent_id,
                        causation_id=observation_event.event_id,
                    )
                )
                continue

            proposal_event = self._event(
                tick,
                "proposal.created",
                actor_id=agent_id,
                causation_id=observation_event.event_id,
                payload={"kind": proposal.kind},
            )
            events.append(proposal_event)
            validation = self._environment.validate(proposal)
            if not validation.accepted:
                events.append(
                    self._event(
                        tick,
                        "action.rejected",
                        actor_id=agent_id,
                        causation_id=proposal_event.event_id,
                        payload={"reason": validation.reason or "rejected"},
                    )
                )
                continue

            action = validation.action
            if action is None:  # Narrowing guard; accepted guarantees an action.
                raise RuntimeError("accepted validation did not contain an action")
            validated_event = self._event(
                tick,
                "action.validated",
                actor_id=agent_id,
                causation_id=proposal_event.event_id,
                payload={"kind": action.kind},
            )
            events.append(validated_event)
            result = self._environment.apply(action, self._rng)
            result_event = self._event(
                tick,
                "action.applied",
                actor_id=agent_id,
                causation_id=validated_event.event_id,
                payload=result.payload,
            )
            events.append(result_event)
            self._memory.append(
                agent_id,
                (MemoryItem(kind="action_result", content=result.payload),),
            )

        events.append(self._event(tick, "tick.completed"))
        self._tick = tick
        snapshot = SimulationSnapshot(tick=tick, world=self._environment.snapshot())
        committed_events = tuple(events)
        self._storage.commit_step(self._run_id, snapshot, committed_events)
        self._event_bus.publish(committed_events)
        return StepResult(snapshot=snapshot, events=committed_events)

    def snapshot(self) -> SimulationSnapshot:
        return SimulationSnapshot(tick=self._tick, world=self._environment.snapshot())

    def _event(
        self,
        tick: Tick,
        kind: str,
        *,
        actor_id: AgentId | None = None,
        causation_id: str | None = None,
        payload: JsonObject | None = None,
    ) -> Event:
        self._sequence += 1
        sequence = EventSequence(self._sequence)
        return Event(
            schema_version=1,
            event_id=f"{self._run_id}:{sequence}",
            run_id=self._run_id,
            sequence=sequence,
            tick=tick,
            kind=kind,
            actor_id=actor_id,
            causation_id=causation_id,
            payload=payload or {},
        )
