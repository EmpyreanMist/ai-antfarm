import asyncio
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from random import Random
from typing import cast

from antfarm.adapters.events import InMemoryEventBus
from antfarm.adapters.memory import InMemoryMemoryStore
from antfarm.adapters.storage import InMemoryStorage
from antfarm.application.agent import MalformedDecisionError
from antfarm.application.engine import SimulationEngine
from antfarm.application.scheduler import ScheduleContext
from antfarm.composition import compose
from antfarm.config.schema import ScenarioConfig
from antfarm.domain import (
    ActionProposal,
    ActionResult,
    AgentContext,
    AgentId,
    CognitionOutcome,
    Event,
    Observation,
    RunId,
    RunLimit,
    RunMetadata,
    Tick,
    ValidatedAction,
    ValidationResult,
)
from antfarm.domain.json_values import JsonObject
from antfarm.domain.protocols import Agent, RandomSource


def _config(
    *,
    action_kind: str = "increment",
    amount: int = 1,
    interval: int | None = 1,
    event_kinds: tuple[str, ...] = (),
) -> ScenarioConfig:
    return ScenarioConfig.model_validate(
        {
            "schema_version": 1,
            "run": {"id": "test-run", "seed": 23, "ticks": 1},
            "providers": {
                "scripted": {
                    "kind": "mock",
                    "decisions": {
                        "alice": [
                            {"kind": action_kind, "parameters": {"amount": amount}}
                        ]
                    },
                }
            },
            "models": {
                "deterministic": {
                    "provider_ref": "scripted",
                    "model": "fixed-decisions",
                }
            },
            "agents": [{"id": "alice", "model_ref": "deterministic"}],
            "actions": [{"kind": "increment"}],
            "environment": {"kind": "counter", "initial_value": 4},
            "memory": {"kind": "in_memory"},
            "scheduling": {
                "kind": "stable",
                "interval": interval,
                "event_kinds": event_kinds,
            },
            "storage": {"kind": "memory"},
        }
    )


def test_invalid_proposal_cannot_mutate_world_state() -> None:
    simulation = compose(_config(amount=0))

    result = asyncio.run(simulation.engine.step())

    assert dict(result.snapshot.world) == {"value": 4}
    assert [event.kind for event in result.events] == [
        "tick.started",
        "observation.created",
        "proposal.created",
        "action.rejected",
        "tick.completed",
    ]


def test_successful_action_emits_ordered_events() -> None:
    simulation = compose(_config(amount=3))

    result = asyncio.run(simulation.engine.step())

    assert dict(result.snapshot.world) == {"value": 7}
    assert [event.kind for event in result.events] == [
        "tick.started",
        "observation.created",
        "proposal.created",
        "action.validated",
        "action.applied",
        "tick.completed",
    ]
    assert [int(event.sequence) for event in result.events] == list(range(1, 7))
    assert result.events[4].causation_id == result.events[3].event_id
    assert simulation.event_bus.published == list(result.events)


def test_event_only_scheduler_can_leave_a_tick_without_due_agents() -> None:
    simulation = compose(
        _config(interval=None, event_kinds=("external.world_changed",))
    )

    result = asyncio.run(simulation.engine.step())

    assert dict(result.snapshot.world) == {"value": 4}
    assert [event.kind for event in result.events] == [
        "tick.started",
        "tick.completed",
    ]


def test_repeated_mock_runs_are_identical() -> None:
    first = asyncio.run(compose(_config(amount=2)).engine.run(RunLimit(ticks=2)))
    second = asyncio.run(compose(_config(amount=2)).engine.run(RunLimit(ticks=2)))

    assert first == second


@dataclass(slots=True)
class _TestAgent:
    id: AgentId
    decision: object
    model_ref: str = "test"

    async def decide(self, context: AgentContext) -> ActionProposal | None:
        del context
        if isinstance(self.decision, BaseException):
            raise self.decision
        return cast(ActionProposal | None, self.decision)


class _RecordingScheduler:
    def __init__(self) -> None:
        self.recorded: list[CognitionOutcome] = []

    def select(self, context: ScheduleContext) -> Sequence[AgentId]:
        return tuple(sorted(context.agent_ids, key=str))

    def record(self, outcomes: Sequence[CognitionOutcome]) -> None:
        self.recorded.extend(outcomes)

    def notify(self, events: Sequence[Event]) -> None:
        del events

    def snapshot(self) -> JsonObject:
        return {}

    def restore(self, state: JsonObject) -> None:
        del state


class _RandomEnvironment:
    def __init__(self, agent_ids: Sequence[AgentId]) -> None:
        self._agent_ids = frozenset(agent_ids)
        self._values: list[int] = []

    def observe(self, agent_id: AgentId, tick: Tick) -> Observation:
        return Observation(agent_id=agent_id, tick=tick, state=self.snapshot())

    def validate(self, proposal: ActionProposal) -> ValidationResult:
        if proposal.actor_id not in self._agent_ids or proposal.kind != "draw":
            return ValidationResult(action=None, reason="invalid proposal")
        return ValidationResult(
            action=ValidatedAction(
                actor_id=proposal.actor_id,
                kind=proposal.kind,
                parameters=proposal.parameters,
            )
        )

    def apply(self, action: ValidatedAction, rng: RandomSource) -> ActionResult:
        assert action.kind == "draw"
        value = rng.randint(1, 1_000_000)
        self._values.append(value)
        return ActionResult(success=True, payload={"value": value})

    def snapshot(self) -> JsonObject:
        return {"values": tuple(self._values)}

    def restore(self, state: JsonObject) -> None:
        values = state["values"]
        if not isinstance(values, tuple):
            raise TypeError("values must be an array")
        self._values = [cast(int, value) for value in values]


def _engine(
    decisions: Mapping[AgentId, object], *, seed: int = 11
) -> tuple[SimulationEngine, _RecordingScheduler]:
    run_id = RunId("engine-test")
    storage = InMemoryStorage()
    storage.create_run(RunMetadata(run_id=run_id, seed=seed), {})
    scheduler = _RecordingScheduler()
    agents: dict[AgentId, Agent] = {
        agent_id: _TestAgent(id=agent_id, decision=decision)
        for agent_id, decision in decisions.items()
    }
    return (
        SimulationEngine(
            run_id=run_id,
            seed=seed,
            agents=agents,
            environment=_RandomEnvironment(tuple(agents)),
            memory=InMemoryMemoryStore(),
            scheduler=scheduler,
            event_bus=InMemoryEventBus(),
            storage=storage,
        ),
        scheduler,
    )


def test_failure_noop_and_malformed_decisions_do_not_mutate_state() -> None:
    alice = AgentId("alice")
    bob = AgentId("bob")
    charlie = AgentId("charlie")
    diana = AgentId("diana")
    engine, scheduler = _engine(
        {
            alice: TimeoutError(),
            bob: MalformedDecisionError("raw model output was invalid"),
            charlie: None,
            diana: cast(ActionProposal, {"kind": "draw"}),
        }
    )

    result = asyncio.run(engine.step())

    assert dict(result.snapshot.world) == {"values": ()}
    assert [event.kind for event in result.events] == [
        "tick.started",
        "observation.created",
        "cognition.timed_out",
        "observation.created",
        "cognition.malformed",
        "observation.created",
        "action.noop",
        "observation.created",
        "cognition.malformed",
        "tick.completed",
    ]
    assert [outcome.kind for outcome in scheduler.recorded] == [
        "timed_out",
        "malformed",
        "noop",
        "malformed",
    ]


def test_agent_cannot_propose_an_action_for_another_agent() -> None:
    alice = AgentId("alice")
    bob = AgentId("bob")
    engine, _ = _engine(
        {
            alice: ActionProposal(actor_id=bob, kind="draw"),
            bob: None,
        }
    )

    result = asyncio.run(engine.step())

    assert dict(result.snapshot.world) == {"values": ()}
    assert [event.kind for event in result.events].count("cognition.malformed") == 1
    assert all(event.kind != "action.applied" for event in result.events)


def test_seeded_random_actions_are_stable_and_ordered() -> None:
    decisions = {
        AgentId("bob"): ActionProposal(actor_id=AgentId("bob"), kind="draw"),
        AgentId("alice"): ActionProposal(actor_id=AgentId("alice"), kind="draw"),
    }
    first, first_scheduler = _engine(decisions, seed=37)
    second, _ = _engine(dict(reversed(tuple(decisions.items()))), seed=37)

    first_result = asyncio.run(first.step())
    second_result = asyncio.run(second.step())

    expected_rng = Random(37)
    expected_values = (
        expected_rng.randint(1, 1_000_000),
        expected_rng.randint(1, 1_000_000),
    )
    assert dict(first_result.snapshot.world) == {"values": expected_values}
    assert first_result == second_result
    assert [outcome.agent_id for outcome in first_scheduler.recorded] == [
        AgentId("alice"),
        AgentId("bob"),
    ]
    assert [int(event.sequence) for event in first_result.events] == list(
        range(1, len(first_result.events) + 1)
    )
