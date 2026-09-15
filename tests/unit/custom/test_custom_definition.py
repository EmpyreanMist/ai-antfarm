from pathlib import Path
from typing import cast

import pytest
from pydantic import ValidationError

from antfarm.custom import CustomSimulationDefinition, load_custom_definition
from antfarm.custom.runtime import DeclarativeEnvironment
from antfarm.domain.models import ActionProposal, AgentId, Tick

EXAMPLE = Path("scenarios/examples/custom-warehouse.yaml")


def test_custom_definition_is_strict_and_reference_validated() -> None:
    definition = load_custom_definition(EXAMPLE)
    raw = definition.model_dump(mode="json")
    raw["executable"] = "os.system"

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        CustomSimulationDefinition.model_validate(raw)

    invalid = definition.model_dump(mode="json")
    invalid["entities"][0]["type"] = "missing"
    with pytest.raises(ValidationError, match="references unknown type"):
        CustomSimulationDefinition.model_validate(invalid)


def test_observations_respect_public_owner_and_internal_visibility() -> None:
    definition = load_custom_definition(EXAMPLE)
    environment = DeclarativeEnvironment(definition)

    observation = environment.observe(AgentId("worker-a"), Tick(1)).state

    assert observation["world"] == {"orders_remaining": 10}
    entities = cast(dict[str, dict[str, object]], observation["entities"])
    assert entities["worker-a"] == {
        "completed": 0,
        "quota": 2,
        "skills": ("packing",),
    }
    assert entities["worker-b"] == {"completed": 0, "skills": ("sorting",)}


def test_environment_rejects_actions_that_violate_declared_constraints() -> None:
    environment = DeclarativeEnvironment(load_custom_definition(EXAMPLE))

    result = environment.validate(
        ActionProposal(
            actor_id=AgentId("worker-a"),
            kind="process",
            parameters={"amount": 3},
        )
    )

    assert not result.accepted
    assert result.reason == "action constraint was not satisfied"


def test_custom_definition_can_omit_entities_and_models() -> None:
    definition = CustomSimulationDefinition.model_validate(
        {
            "schema_version": 1,
            "kind": "custom",
            "run": {"id": "clock", "ticks": 1},
            "entity_types": {},
            "world_fields": {"phase": {"type": "string"}},
            "world_state": {"phase": "ready"},
            "actions": {},
            "storage": {"kind": "memory"},
        }
    )

    assert definition.entities == ()
    assert definition.model_refs == ()


def test_invalid_transition_types_fail_before_composition() -> None:
    definition = load_custom_definition(EXAMPLE)
    raw = definition.model_dump(mode="json")
    raw["actions"]["process"]["effects"][0]["value"] = {
        "source": "literal",
        "value": "not a number",
    }

    with pytest.raises(ValidationError, match="requires numbers"):
        CustomSimulationDefinition.model_validate(raw)
