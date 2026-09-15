from pathlib import Path
from typing import cast

import pytest

from antfarm.adapters.models import MockModelProvider
from antfarm.application import AgentQuery, EntityQuery, EventQuery, RunStatus
from antfarm.custom import CustomSimulationDefinition, load_custom_definition
from antfarm.domain.json_values import freeze_object, thaw_json
from antfarm.domain.models import AgentId
from antfarm.facade import AntFarmApplication, StartRunCommand
from antfarm.ports.models import ModelResponse

EXAMPLE = Path("scenarios/examples/custom-warehouse.yaml")


@pytest.mark.asyncio
async def test_custom_definition_uses_existing_lifecycle_and_queries() -> None:
    source = load_custom_definition(EXAMPLE)
    application = AntFarmApplication()
    resolved = application.resolve_custom(source, run_id="warehouse-test", seed=91)

    started = application.start(StartRunCommand(resolved))
    await application.wait_run(started.run_id)

    state = application.read_run_state(started.run_id)
    assert state.status is RunStatus.COMPLETED
    assert state.tick == 2
    snapshot = application.query_snapshot(started.run_id)
    assert snapshot is not None
    assert snapshot.world["world"] == {
        "orders_remaining": 0,
        "audit_note": "internal-only",
    }
    assert snapshot.world["entities"] == {
        "worker-a": {
            "completed": 4,
            "quota": 2,
            "internal_code": "alpha",
            "skills": ("packing",),
        },
        "worker-b": {
            "completed": 6,
            "quota": 3,
            "internal_code": "beta",
            "skills": ("sorting",),
        },
    }
    agents = application.query_agents(AgentQuery(started.run_id, limit=10))
    assert agents.items[0].public["state"] == {
        "completed": 0,
        "skills": ("packing",),
    }
    configured_state = cast(
        dict[str, object], agents.items[0].configuration["state"]
    )
    assert "quota" in configured_state
    events = application.query_events(EventQuery(started.run_id, limit=100))
    assert sum(event.kind == "action.applied" for event in events.items) == 4
    assert source.run.id == "custom-warehouse"
    assert resolved.runtime_overrides == {"id": "warehouse-test", "seed": 91}
    entities = application.query_entities(EntityQuery(started.run_id, limit=10))
    assert entities.items[0].entity_id == "worker-a"
    assert entities.items[0].entity_type == "worker"
    assert entities.items[0].behavior == "deterministic"


@pytest.mark.asyncio
async def test_custom_sqlite_result_is_inspectable_after_execution(
    tmp_path: Path,
) -> None:
    source = load_custom_definition(EXAMPLE)
    raw = source.model_dump(mode="json")
    raw["run"]["id"] = "warehouse-sqlite"
    raw["storage"] = {"kind": "sqlite", "path": str(tmp_path / "custom.db")}
    definition = CustomSimulationDefinition.model_validate(raw)
    application = AntFarmApplication()

    started = application.start(StartRunCommand(definition))
    await application.wait_run(started.run_id)

    stored = application.query_run(started.run_id)
    stored_definition = cast(dict[str, object], thaw_json(stored.scenario))
    assert stored_definition["kind"] == "custom"
    assert application.query_agents(
        AgentQuery(started.run_id, limit=10)
    ).items[1].agent_id == "worker-b"
    assert application.query_entities(
        EntityQuery(started.run_id, limit=10)
    ).items[1].entity_id == "worker-b"


@pytest.mark.asyncio
async def test_same_custom_input_is_deterministic_and_rejections_are_audited() -> None:
    source = load_custom_definition(EXAMPLE)
    raw = source.model_dump(mode="json")
    raw["run"] = {"id": "warehouse-rejected", "seed": 31, "ticks": 1}
    raw["entities"][0]["behavior"]["actions"][0]["parameters"]["amount"] = 3
    definition = CustomSimulationDefinition.model_validate(raw)
    application = AntFarmApplication()

    first = application.start(StartRunCommand(definition))
    await application.wait_run(first.run_id)
    first_snapshot = application.query_snapshot(first.run_id)
    events = application.query_events(EventQuery(first.run_id, limit=100))

    assert first_snapshot is not None
    assert any(event.kind == "action.rejected" for event in events.items)
    second_application = AntFarmApplication()
    second = second_application.start(
        StartRunCommand(
            second_application.resolve_custom(
                definition, run_id="warehouse-rejected-copy"
            )
        )
    )
    await second_application.wait_run(second.run_id)
    second_snapshot = second_application.query_snapshot(second.run_id)
    assert second_snapshot is not None
    assert second_snapshot.world == first_snapshot.world


@pytest.mark.asyncio
async def test_custom_entities_can_use_an_injected_model_provider() -> None:
    source = load_custom_definition(EXAMPLE)
    raw = source.model_dump(mode="json")
    raw["run"] = {"id": "warehouse-model", "seed": 31, "ticks": 1}
    raw["model_refs"] = ["planner"]
    raw["entities"][0]["behavior"] = {"kind": "model", "model_ref": "planner"}
    definition = CustomSimulationDefinition.model_validate(raw)
    provider = MockModelProvider(
        {
            AgentId("worker-a"): (
                ModelResponse(
                    action_kind="process",
                    parameters=freeze_object({"amount": 2}),
                ),
            )
        }
    )
    application = AntFarmApplication(custom_model_providers={"planner": provider})

    started = application.start(StartRunCommand(definition))
    await application.wait_run(started.run_id)

    events = application.query_events(EventQuery(started.run_id, limit=100))
    assert sum(event.kind == "action.applied" for event in events.items) == 2
