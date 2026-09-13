import math
from collections.abc import Mapping

import pytest

from antfarm.domain import ActionProposal, AgentId, AgentPersonality


def test_json_values_are_deeply_immutable() -> None:
    proposal = ActionProposal(
        actor_id=AgentId("alice"),
        kind="increment",
        parameters={"nested": {"items": (1, 2)}},
    )

    nested = proposal.parameters["nested"]
    assert not isinstance(nested, (str, int, float, bool, type(None), tuple))
    with pytest.raises(TypeError):
        nested["items"] = (3,)  # type: ignore[index]


def test_non_finite_json_numbers_are_rejected() -> None:
    with pytest.raises(ValueError, match="finite"):
        ActionProposal(
            actor_id=AgentId("alice"),
            kind="increment",
            parameters={"amount": math.nan},
        )


def test_agent_personality_traits_are_deeply_immutable() -> None:
    personality = AgentPersonality(
        description="Patient", traits={"preferences": {"pace": "slow"}}
    )

    preferences = personality.traits["preferences"]
    assert isinstance(preferences, Mapping)
    with pytest.raises(TypeError):
        preferences["pace"] = "fast"  # type: ignore[index]
