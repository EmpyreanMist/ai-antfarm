import json
from pathlib import Path

from antfarm.config import ScenarioConfig, load_scenario
from antfarm.domain import (
    ActionProposal,
    ActionResult,
    AgentId,
    Event,
    EventSequence,
    RunId,
    SimulationSnapshot,
    Tick,
    ValidatedAction,
)
from antfarm.domain.serialization import (
    action_proposal_from_data,
    action_proposal_to_data,
    action_result_from_data,
    action_result_to_data,
    event_from_data,
    event_to_data,
    snapshot_from_data,
    snapshot_to_data,
    validated_action_from_data,
    validated_action_to_data,
)


def _through_json(data: dict[str, object]) -> dict[str, object]:
    decoded = json.loads(json.dumps(data))
    assert isinstance(decoded, dict)
    return decoded


def test_scenario_round_trip() -> None:
    repository = Path(__file__).parents[3]
    scenario = load_scenario(repository / "scenarios/examples/minimal.yaml")

    restored = ScenarioConfig.model_validate_json(scenario.model_dump_json())

    assert restored == scenario


def test_action_values_round_trip() -> None:
    proposal = ActionProposal(
        actor_id=AgentId("alice"),
        kind="increment",
        parameters={"amount": 2, "metadata": {"source": "mock"}},
    )
    validated = ValidatedAction(
        actor_id=proposal.actor_id,
        kind=proposal.kind,
        parameters=proposal.parameters,
    )
    result = ActionResult(
        success=True,
        payload={"value": 2, "audit": ("accepted", 1)},
    )

    assert (
        action_proposal_from_data(_through_json(action_proposal_to_data(proposal)))
        == proposal
    )
    assert (
        validated_action_from_data(_through_json(validated_action_to_data(validated)))
        == validated
    )
    assert (
        action_result_from_data(_through_json(action_result_to_data(result))) == result
    )


def test_event_round_trip() -> None:
    event = Event(
        schema_version=1,
        event_id="run-1:4",
        run_id=RunId("run-1"),
        sequence=EventSequence(4),
        tick=Tick(2),
        kind="action.applied",
        actor_id=AgentId("alice"),
        causation_id="run-1:3",
        payload={"value": 2, "tags": ("deterministic", "offline")},
    )

    restored = event_from_data(_through_json(event_to_data(event)))

    assert restored == event


def test_snapshot_round_trip() -> None:
    snapshot = SimulationSnapshot(
        tick=Tick(3),
        world={"value": 7},
        memory={"alice": ({"kind": "result", "value": 7},)},
        scheduler={"last_tick": 3},
        engine={"event_sequence": 8, "random_state": (3, (1, 2, 3), None)},
    )

    restored = snapshot_from_data(_through_json(snapshot_to_data(snapshot)))

    assert restored == snapshot
