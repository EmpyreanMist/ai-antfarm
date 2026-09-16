"""Offline tests for deterministic population and runtime resolution."""

from __future__ import annotations

from pathlib import Path
from typing import cast

import pytest
from pydantic import ValidationError

from antfarm.config import load_scenario
from antfarm.config.schema import (
    BehavioralTraitsConfig,
    PopulationConfig,
    ScenarioConfig,
)
from antfarm.population import RuntimeOverrides, WebAgentDraft, resolve_run_config


def _scenario_data() -> dict[str, object]:
    return {
        "schema_version": 1,
        "run": {"id": "population-test", "seed": 17, "ticks": 1},
        "providers": {"scripted": {"kind": "mock", "decisions": {}}},
        "models": {
            "primary": {"provider_ref": "scripted", "model": "fixed"},
            "secondary": {"provider_ref": "scripted", "model": "fixed-2"},
        },
        "agents": [{"id": "alice", "model_ref": "primary"}],
        "actions": [{"kind": "increment"}],
        "environment": {"kind": "counter"},
        "memory": {"kind": "in_memory"},
        "scheduling": {"kind": "stable"},
        "storage": {"kind": "memory"},
    }


def _full_generated(seed: int = 41) -> ScenarioConfig:
    data = _scenario_data()
    data["agents"] = []
    data["population"] = {
        "mode": "generated",
        "seed": seed,
        "generated": {
            "id_prefix": "citizen",
            "count": 3,
            "model_ref": "primary",
            "randomize": {
                "behavioral_traits": {
                    "mode": "all",
                    "default": {"minimum": 0.15, "maximum": 0.85},
                },
                "economics": {
                    "money": {"minimum": 5, "maximum": 50},
                    "recurring_income": {"minimum": 0, "maximum": 8},
                    "resources": {"tools": {"minimum": 0, "maximum": 3}},
                },
            },
        },
    }
    return ScenarioConfig.model_validate(data)


def test_fully_generated_population_is_materialized_and_reproducible() -> None:
    source = _full_generated()

    first = resolve_run_config(source)
    second = resolve_run_config(source)

    assert first == second
    assert first.population is None
    assert first.agent_pools == ()
    assert [agent.id for agent in first.agents] == [
        "citizen-001",
        "citizen-002",
        "citizen-003",
    ]
    profile = first.profiles[cast(str, first.agents[0].profile_ref)]
    assert profile.behavioral_traits is not None
    assert all(
        getattr(profile.behavioral_traits, name) is not None
        for name in BehavioralTraitsConfig.model_fields
    )
    assert profile.economics is not None
    assert 5 <= cast(int, profile.economics.money) <= 50


def test_web_agent_drafts_become_normal_resolved_agents_and_models() -> None:
    source = load_scenario(Path("scenarios/examples/live-social-ollama.yaml"))
    profile = {
        "identity": {"display_name": "New Agent"},
        "personality": {"description": "Curious and direct."},
    }
    resolved = resolve_run_config(
        source,
        RuntimeOverrides(
            web_agents=(
                WebAgentDraft(id="new-agent", profile=profile, model="gemma4:e2b"),
                WebAgentDraft(id="clone-agent", profile=profile, model="gemma4:e2b"),
            )
        ),
    )

    assert {agent.id for agent in resolved.agents} == {"new-agent", "clone-agent"}
    assert resolved.run.active_agents == 2
    assert len({agent.model_ref for agent in resolved.agents}) == 1
    assert resolved.models[resolved.agents[0].model_ref].model == "gemma4:e2b"


def test_different_seed_changes_generated_values_without_mutating_source() -> None:
    source = _full_generated()
    before = source.model_dump(mode="json")

    first = resolve_run_config(source, RuntimeOverrides(seed=101))
    second = resolve_run_config(source, RuntimeOverrides(seed=102))

    assert first.profiles != second.profiles
    assert first.run.seed == 101
    assert second.run.seed == 102
    assert source.model_dump(mode="json") == before
    assert source.population is not None


def test_mixed_population_applies_per_agent_fields_and_explicit_values_last() -> None:
    data = _scenario_data()
    data["profiles"] = {
        "alice-explicit": {
            "behavioral_traits": {"generosity": 0.99},
            "economics": {"money": 77},
            "visibility": {"wealth": "public"},
        }
    }
    data["agents"] = [
        {"id": "alice", "model_ref": "primary", "profile_ref": "alice-explicit"}
    ]
    data["population"] = {
        "mode": "mixed",
        "generated": {
            "id_prefix": "worker",
            "count": 1,
            "model_ref": "primary",
            "randomize": {
                "behavioral_traits": {
                    "mode": "selected",
                    "patience": {"minimum": 0.2, "maximum": 0.2},
                }
            },
        },
        "randomize": {
            "behavioral_traits": {
                "mode": "selected",
                "generosity": {"minimum": 0.1, "maximum": 0.1},
            },
            "economics": {"money": {"minimum": 1, "maximum": 1}},
        },
        "agents": {
            "alice": {
                "behavioral_traits": {
                    "mode": "selected",
                    "trust": {"minimum": 0.3, "maximum": 0.3},
                }
            }
        },
    }

    resolved = resolve_run_config(ScenarioConfig.model_validate(data))
    alice = resolved.profiles[cast(str, resolved.agents[0].profile_ref)]
    worker = resolved.profiles[cast(str, resolved.agents[1].profile_ref)]

    assert alice.behavioral_traits is not None
    assert alice.behavioral_traits.generosity == 0.99
    assert alice.behavioral_traits.trust == 0.3
    assert alice.economics is not None and alice.economics.money == 77
    assert alice.visibility.wealth == "public"
    assert worker.behavioral_traits is not None
    assert worker.behavioral_traits.generosity == 0.1
    assert worker.behavioral_traits.patience == 0.2
    assert worker.economics is not None and worker.economics.money == 1


def test_runtime_profile_population_and_model_assignments_are_ephemeral() -> None:
    source = ScenarioConfig.model_validate(_scenario_data())
    population = PopulationConfig.model_validate(
        {
            "mode": "mixed",
            "randomize": {
                "economics": {"money": {"minimum": 10, "maximum": 10}}
            },
        }
    )

    resolved = resolve_run_config(
        source,
        RuntimeOverrides(
            population=population,
            profiles={
                "alice": {
                    "economics": {"money": 25, "occupation": "builder"},
                    "visibility": {"occupation": "public"},
                }
            },
            model_assignments={"alice": "secondary"},
        ),
    )

    agent = resolved.agents[0]
    profile = resolved.profiles[cast(str, agent.profile_ref)]
    assert agent.model_ref == "secondary"
    assert profile.economics is not None
    assert profile.economics.money == 25
    assert profile.economics.occupation == "builder"
    assert profile.visibility.occupation == "public"
    assert source.agents[0].model_ref == "primary"
    assert source.population is None


@pytest.mark.parametrize(
    ("population", "message"),
    [
        (
            {
                "mode": "mixed",
                "randomize": {
                    "behavioral_traits": {
                        "mode": "selected",
                        "generosity": {"minimum": 0.8, "maximum": 0.2},
                    }
                },
            },
            "minimum must not exceed maximum",
        ),
        (
            {
                "mode": "mixed",
                "randomize": {"behavioral_traits": {"mode": "selected"}},
            },
            "requires at least one field",
        ),
        (
            {"mode": "generated"},
            "requires generated settings",
        ),
    ],
)
def test_population_modes_and_ranges_are_strictly_validated(
    population: dict[str, object], message: str
) -> None:
    data = _scenario_data()
    data["population"] = population

    with pytest.raises(ValidationError, match=message):
        ScenarioConfig.model_validate(data)


def test_invalid_runtime_override_fails_before_database_creation(
    tmp_path: Path,
) -> None:
    data = _scenario_data()
    database = tmp_path / "must-not-exist.db"
    data["storage"] = {"kind": "sqlite", "path": str(database)}
    source = ScenarioConfig.model_validate(data)

    with pytest.raises(ValidationError, match="unknown model"):
        resolve_run_config(
            source,
            RuntimeOverrides(model_assignments={"alice": "missing-model"}),
        )

    assert not database.exists()
