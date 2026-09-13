"""Deterministic, sequential simulation orchestration."""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from random import Random
from typing import cast

from antfarm.application.agent import MalformedDecisionError
from antfarm.application.metrics import BuiltInMetricCollector
from antfarm.application.scheduler import CognitionScheduler, ScheduleContext
from antfarm.domain.json_values import JsonObject
from antfarm.domain.models import (
    ActionProposal,
    AgentContext,
    AgentId,
    CognitionOutcome,
    Event,
    EventSequence,
    MemoryItem,
    MemoryQuery,
    RunId,
    RunLimit,
    RunResult,
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
        metrics: BuiltInMetricCollector | None = None,
        memory_recall_limit: int = 10,
        on_cognition_started: Callable[[Tick, AgentId, str], None] | None = None,
    ) -> None:
        if memory_recall_limit < 0:
            raise ValueError("memory recall limit must not be negative")
        self._run_id = run_id
        self._agents = dict(agents)
        self._environment = environment
        self._memory = memory
        self._scheduler = scheduler
        self._event_bus = event_bus
        self._storage = storage
        self._metrics = metrics or BuiltInMetricCollector(
            (), action_kinds=(), agent_ids=tuple(str(agent_id) for agent_id in agents)
        )
        if self._metrics.event_kinds:
            self._event_bus.subscribe(self._metrics.event_kinds, self._metrics.observe)
        self._memory_recall_limit = memory_recall_limit
        self._rng = Random(seed)
        self._tick = Tick(0)
        self._sequence = 0
        self._on_cognition_started = on_cognition_started

    @property
    def metrics(self) -> BuiltInMetricCollector:
        return self._metrics

    async def step(self) -> StepResult:
        """Advance atomically, restoring all live state if commit is not reached."""

        preceding = self.snapshot()
        try:
            result = await self._step()
        except BaseException:
            self.restore(preceding)
            raise
        self._event_bus.publish(result.events)
        return result

    async def _step(self) -> StepResult:
        tick = Tick(int(self._tick) + 1)
        events: list[Event] = [self._event(tick, "tick.started")]
        outcomes: list[CognitionOutcome] = []
        pending_memory: dict[AgentId, list[MemoryItem]] = {}
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
                memories=tuple(
                    self._memory.recall(
                        agent_id,
                        MemoryQuery(limit=self._memory_recall_limit),
                    )
                ),
            )
            if self._on_cognition_started is not None:
                self._on_cognition_started(tick, agent_id, agent.model_ref)
            try:
                proposal = await agent.decide(context)
            except TimeoutError:
                events.append(
                    self._event(
                        tick,
                        "cognition.timed_out",
                        actor_id=agent_id,
                        causation_id=observation_event.event_id,
                        payload={"reason": "timeout"},
                    )
                )
                outcomes.append(
                    CognitionOutcome(agent_id=agent_id, tick=tick, kind="timed_out")
                )
                continue
            except MalformedDecisionError as error:
                events.append(
                    self._event(
                        tick,
                        "cognition.malformed",
                        actor_id=agent_id,
                        causation_id=observation_event.event_id,
                        payload={"reason": str(error) or "invalid decision"},
                    )
                )
                outcomes.append(
                    CognitionOutcome(agent_id=agent_id, tick=tick, kind="malformed")
                )
                continue
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
                outcomes.append(
                    CognitionOutcome(agent_id=agent_id, tick=tick, kind="failed")
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
                outcomes.append(
                    CognitionOutcome(agent_id=agent_id, tick=tick, kind="noop")
                )
                continue

            if (
                not isinstance(proposal, ActionProposal)
                or proposal.actor_id != agent_id
            ):
                events.append(
                    self._event(
                        tick,
                        "cognition.malformed",
                        actor_id=agent_id,
                        causation_id=observation_event.event_id,
                        payload={"reason": "invalid action proposal"},
                    )
                )
                outcomes.append(
                    CognitionOutcome(agent_id=agent_id, tick=tick, kind="malformed")
                )
                continue

            proposal_event = self._event(
                tick,
                "proposal.created",
                actor_id=agent_id,
                causation_id=observation_event.event_id,
                payload={"kind": proposal.kind, "parameters": proposal.parameters},
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
                        payload={
                            "kind": proposal.kind,
                            "reason": validation.reason or "rejected",
                        },
                    )
                )
                outcomes.append(
                    CognitionOutcome(agent_id=agent_id, tick=tick, kind="rejected")
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
                payload={"kind": action.kind, "parameters": action.parameters},
            )
            events.append(validated_event)
            result = self._environment.apply(action, self._rng, tick)
            result_event = self._event(
                tick,
                "action.applied",
                actor_id=agent_id,
                causation_id=validated_event.event_id,
                payload={
                    **result.payload,
                    "kind": action.kind,
                    "parameters": action.parameters,
                },
            )
            events.append(result_event)
            self._memory.append(
                agent_id,
                (MemoryItem(kind="action_result", content=result.payload),),
            )
            for recipient_id, items in self._environment.memory_deliveries(
                action, result
            ).items():
                if recipient_id not in self._agents:
                    raise ValueError("environment returned an unknown memory recipient")
                pending_memory.setdefault(recipient_id, []).extend(items)
            outcomes.append(
                CognitionOutcome(agent_id=agent_id, tick=tick, kind="applied")
            )

        for recipient_id in sorted(pending_memory, key=str):
            self._memory.append(recipient_id, tuple(pending_memory[recipient_id]))
        self._scheduler.record(tuple(outcomes))
        events.append(self._event(tick, "tick.completed"))
        self._scheduler.notify(tuple(events))
        self._tick = tick
        metric_state = self._metrics.project(tuple(events))
        snapshot = SimulationSnapshot(
            tick=tick,
            world=self._environment.snapshot(),
            memory=self._memory.snapshot(),
            scheduler=self._scheduler.snapshot(),
            metrics=metric_state,
            engine=self._engine_state(),
        )
        committed_events = tuple(events)
        self._storage.commit_step(self._run_id, snapshot, committed_events)
        return StepResult(snapshot=snapshot, events=committed_events)

    def snapshot(self) -> SimulationSnapshot:
        return SimulationSnapshot(
            tick=self._tick,
            world=self._environment.snapshot(),
            memory=self._memory.snapshot(),
            scheduler=self._scheduler.snapshot(),
            metrics=self._metrics.snapshot(),
            engine=self._engine_state(),
        )

    def restore(self, snapshot: SimulationSnapshot) -> None:
        """Restore every stateful engine component from a durable checkpoint."""

        event_sequence = snapshot.engine.get("event_sequence")
        random_state = snapshot.engine.get("random_state")
        if (
            isinstance(event_sequence, bool)
            or not isinstance(event_sequence, int)
            or event_sequence < 0
        ):
            raise TypeError("engine event sequence must be a non-negative integer")
        if not isinstance(random_state, tuple) or len(random_state) != 3:
            raise TypeError("engine random state must be a three-item array")
        version, internal_state, gaussian = random_state
        if isinstance(version, bool) or not isinstance(version, int):
            raise TypeError("engine random state version must be an integer")
        if not isinstance(internal_state, tuple) or not all(
            isinstance(item, int) and not isinstance(item, bool)
            for item in internal_state
        ):
            raise TypeError("engine random internal state must be an integer array")
        if gaussian is not None and not isinstance(gaussian, float):
            raise TypeError("engine random gaussian cache must be a number or null")

        self._environment.restore(snapshot.world)
        self._memory.restore(snapshot.memory)
        self._scheduler.restore(snapshot.scheduler)
        self._metrics.restore(snapshot.metrics)
        self._rng.setstate(
            cast(tuple[int, tuple[int, ...], float | None], tuple(random_state))
        )
        self._tick = snapshot.tick
        self._sequence = event_sequence

    async def run(self, limit: RunLimit) -> RunResult:
        events: list[Event] = []
        for _ in range(limit.ticks):
            result = await self.step()
            events.extend(result.events)
        return RunResult(snapshot=self.snapshot(), events=events)

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

    def _engine_state(self) -> JsonObject:
        version, internal_state, gaussian = self._rng.getstate()
        return {
            "event_sequence": self._sequence,
            "random_state": (version, internal_state, gaussian),
        }
