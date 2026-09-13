import asyncio

from antfarm.composition import compose
from antfarm.config.schema import ScenarioConfig


def _config(*, action_kind: str = "increment", amount: int = 1) -> ScenarioConfig:
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
            "scheduling": {"kind": "stable"},
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


def test_repeated_mock_runs_are_identical() -> None:
    first = asyncio.run(compose(_config(amount=2)).engine.step())
    second = asyncio.run(compose(_config(amount=2)).engine.step())

    assert first == second
