import copy
import json
from collections.abc import Callable
from typing import cast

import pytest
from pydantic import ValidationError

from antfarm.config.schema import ScenarioConfig


def _valid_data() -> dict[str, object]:
    return {
        "schema_version": 1,
        "run": {"id": "schema-test", "seed": 4, "ticks": 2},
        "providers": {
            "scripted": {
                "kind": "mock",
                "decisions": {
                    "alice": [{"kind": "increment", "parameters": {"amount": 1}}]
                },
            }
        },
        "models": {
            "deterministic": {
                "provider_ref": "scripted",
                "model": "fixed-decisions",
            }
        },
        "personalities": {
            "patient": {"description": "Patient", "traits": {"tempo": "slow"}}
        },
        "agents": [
            {
                "id": "alice",
                "model_ref": "deterministic",
                "personality_ref": "patient",
            }
        ],
        "agent_pools": [],
        "actions": [{"kind": "increment"}],
        "environment": {"kind": "counter", "initial_value": 0},
        "memory": {"kind": "in_memory", "recall_limit": 5},
        "scheduling": {"kind": "stable", "interval": 1},
        "rules": [],
        "metrics": [],
        "storage": {"kind": "memory"},
    }


def test_agent_pools_expand_in_stable_order() -> None:
    data = _valid_data()
    data["agents"] = []
    data["providers"] = {"scripted": {"kind": "mock", "decisions": {}}}
    data["agent_pools"] = [
        {"id_prefix": "zeta", "count": 2, "model_ref": "deterministic"},
        {"id_prefix": "beta", "count": 1, "model_ref": "deterministic"},
    ]

    config = ScenarioConfig.model_validate(data)

    assert [agent.id for agent in config.expand_agents()] == [
        "beta-001",
        "zeta-001",
        "zeta-002",
    ]


def test_rich_profile_validates_all_independent_traits_and_conflicts() -> None:
    data = _valid_data()
    traits = {
        "generosity": 0.9,
        "greed": 0.8,
        "selfishness": 0.7,
        "empathy": 0.6,
        "assertiveness": 0.5,
        "agreeableness": 0.4,
        "honesty": 0.3,
        "conformity": 0.2,
        "patience": 0.1,
        "impulsiveness": 0.9,
        "risk_tolerance": 0.8,
        "competitiveness": 0.7,
        "envy": 0.6,
        "aggression": 0.5,
        "trust": 0.4,
        "ambition": 0.3,
        "materialism": 0.2,
        "fairness": 0.1,
        "forgiveness": 0.9,
        "sociability": 0.8,
    }
    data["profiles"] = {
        "complex": {
            "identity": {"display_name": "Alice", "description": "A trader."},
            "personality": {
                "description": "Warm but fiercely competitive.",
                "qualities": ["observant", "direct"],
            },
            "goals": ["Build security", "Win recognition"],
            "beliefs": ["Cooperation can be useful"],
            "values": ["Fairness", "Personal success"],
            "communication_preferences": {
                "style": "concise",
                "preferences": ["Make concrete proposals"],
            },
            "behavioral_traits": traits,
            "social_status": {
                "label": "respected",
                "roles": ["merchant"],
                "standing": 0.75,
            },
            "private_information": ["Owes a private debt"],
        }
    }
    data["agents"] = [
        {"id": "alice", "model_ref": "deterministic", "profile_ref": "complex"}
    ]

    config = ScenarioConfig.model_validate(data)

    profile = config.profiles["complex"]
    assert profile.behavioral_traits is not None
    assert profile.behavioral_traits.generosity == 0.9
    assert profile.behavioral_traits.greed == 0.8
    assert config.expand_agents()[0].profile_ref == "complex"


@pytest.mark.parametrize(
    "profile",
    [
        {},
        {"goals": []},
        {"behavioral_traits": {}},
        {"behavioral_traits": {"empathy": -0.01}},
        {"behavioral_traits": {"empathy": 1.01}},
        {"communication_preferences": {}},
        {"social_status": {}},
    ],
)
def test_rich_profile_rejects_empty_or_out_of_range_sections(
    profile: dict[str, object],
) -> None:
    data = _valid_data()
    data["profiles"] = {"invalid": profile}
    data["agents"] = [
        {"id": "alice", "model_ref": "deterministic", "profile_ref": "invalid"}
    ]

    with pytest.raises(ValidationError):
        ScenarioConfig.model_validate(data)


def test_agent_cannot_combine_rich_and_legacy_profile_references() -> None:
    data = _valid_data()
    data["profiles"] = {"rich": {"goals": ["Act"]}}
    agents = cast(list[dict[str, object]], data["agents"])
    agents[0]["profile_ref"] = "rich"

    with pytest.raises(ValidationError, match="both a profile"):
        ScenarioConfig.model_validate(data)


def test_pool_expansion_rejects_identifier_collisions() -> None:
    data = _valid_data()
    data["agents"] = [
        {"id": "worker-001", "model_ref": "deterministic"},
    ]
    data["agent_pools"] = [
        {"id_prefix": "worker", "count": 1, "model_ref": "deterministic"},
    ]
    data["providers"] = {"scripted": {"kind": "mock", "decisions": {}}}

    with pytest.raises(ValidationError, match="expanded agent identifiers"):
        ScenarioConfig.model_validate(data)


def _unknown_provider(data: dict[str, object]) -> None:
    data["models"] = {"deterministic": {"provider_ref": "missing", "model": "fixed"}}


def _unknown_model(data: dict[str, object]) -> None:
    data["agents"] = [{"id": "alice", "model_ref": "missing"}]
    data["providers"] = {"scripted": {"kind": "mock", "decisions": {}}}


def _unknown_personality(data: dict[str, object]) -> None:
    data["agents"] = [
        {
            "id": "alice",
            "model_ref": "deterministic",
            "personality_ref": "missing",
        }
    ]


def _unknown_decision_agent(data: dict[str, object]) -> None:
    data["providers"] = {
        "scripted": {
            "kind": "mock",
            "decisions": {"missing": [{"kind": "increment"}]},
        }
    }


def _unknown_rule_action(data: dict[str, object]) -> None:
    data["rules"] = [
        {
            "id": "allowed-actions",
            "kind": "action_allowlist",
            "action_refs": ["missing"],
        }
    ]


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (_unknown_provider, "unknown provider"),
        (_unknown_model, "unknown model"),
        (_unknown_personality, "unknown personality"),
        (_unknown_decision_agent, "unknown agent"),
        (_unknown_rule_action, "unknown actions"),
    ],
)
def test_invalid_references_are_rejected(
    mutation: Callable[[dict[str, object]], None], message: str
) -> None:
    data = copy.deepcopy(_valid_data())
    mutation(data)

    with pytest.raises(ValidationError, match=message):
        ScenarioConfig.model_validate(data)


def test_complete_schema_represents_deferred_configuration() -> None:
    data = _valid_data()
    data["providers"] = {
        "remote": {
            "kind": "openai_compatible",
            "base_url": "http://localhost:11434/v1",
            "api_key_env": "ANTFARM_API_KEY",
        }
    }
    data["models"] = {
        "local-model": {
            "provider_ref": "remote",
            "model": "example/model",
            "timeout_seconds": 12,
            "parameters": {"temperature": 0},
        }
    }
    data["agents"] = [{"id": "alice", "model_ref": "local-model"}]
    data["rules"] = [
        {
            "id": "allowed-actions",
            "kind": "action_allowlist",
            "action_refs": ["increment"],
        }
    ]
    data["metrics"] = [
        "action_count",
        "rejection_count",
        "failure_count",
        "agent_outcomes",
    ]
    data["storage"] = {"kind": "sqlite", "path": "runs.db"}
    data["observability"] = {"event_detail": "failures", "include_model_io": False}

    config = ScenarioConfig.model_validate(data)

    assert config.models["local-model"].provider_ref == "remote"
    assert config.storage.kind == "sqlite"
    assert config.metrics == (
        "action_count",
        "rejection_count",
        "failure_count",
        "agent_outcomes",
    )


def test_openai_compatible_runtime_hint_is_closed_and_validated() -> None:
    data = _valid_data()
    data["providers"] = {
        "local": {
            "kind": "openai_compatible",
            "base_url": "http://localhost:11434/v1",
            "runtime": "not-ollama",
        }
    }
    data["models"] = {
        "deterministic": {"provider_ref": "local", "model": "test"}
    }

    with pytest.raises(ValidationError, match="runtime"):
        ScenarioConfig.model_validate(data)


def test_normalized_json_is_canonical_and_contains_expanded_agents() -> None:
    data = _valid_data()
    data["agents"] = []
    data["agent_pools"] = [
        {"id_prefix": "worker", "count": 2, "model_ref": "deterministic"},
        {"id_prefix": "beta", "count": 1, "model_ref": "deterministic"},
    ]
    data["providers"] = {"scripted": {"kind": "mock", "decisions": {}}}
    config = ScenarioConfig.model_validate(data)
    reordered_data = copy.deepcopy(data)
    pools = reordered_data["agent_pools"]
    assert isinstance(pools, list)
    reordered_data["agent_pools"] = list(reversed(pools))
    reordered = ScenarioConfig.model_validate(reordered_data)

    normalized = config.normalized_json()
    decoded = json.loads(normalized)

    assert normalized == json.dumps(decoded, sort_keys=True, separators=(",", ":"))
    assert normalized == reordered.normalized_json()
    assert [agent["id"] for agent in decoded["expanded_agents"]] == [
        "beta-001",
        "worker-001",
        "worker-002",
    ]


def test_event_only_scheduling_is_valid() -> None:
    data = _valid_data()
    data["scheduling"] = {
        "kind": "stable",
        "interval": None,
        "cooldown": 2,
        "event_kinds": ["action.applied"],
    }

    config = ScenarioConfig.model_validate(data)

    assert config.scheduling.interval is None
    assert config.scheduling.event_kinds == ("action.applied",)


def test_agent_and_pool_cadence_and_budgets_are_normalized() -> None:
    data = _valid_data()
    data["agents"] = [
        {
            "id": "alice",
            "model_ref": "deterministic",
            "cognition_interval": 4,
        }
    ]
    data["agent_pools"] = [
        {
            "id_prefix": "worker",
            "count": 2,
            "model_ref": "deterministic",
            "cognition_interval": 3,
        }
    ]
    data["providers"] = {"scripted": {"kind": "mock", "decisions": {}}}
    data["scheduling"] = {
        "kind": "stable",
        "interval": 5,
        "stagger": True,
        "max_cognitions_per_tick": 1,
        "failure_retry_cooldown_max": 4,
    }
    data["observability"] = {"event_buffer_limit": 12}

    config = ScenarioConfig.model_validate(data)

    assert [agent.cognition_interval for agent in config.expand_agents()] == [4, 3, 3]
    assert config.scheduling.max_cognitions_per_tick == 1
    assert config.scheduling.stagger is True
    assert config.observability.event_buffer_limit == 12


def test_active_agent_count_selects_a_validated_prefix() -> None:
    data = _valid_data()
    data["agents"] = []
    data["agent_pools"] = [
        {"id_prefix": "worker", "count": 3, "model_ref": "deterministic"}
    ]
    data["providers"] = {"scripted": {"kind": "mock", "decisions": {}}}
    run = data["run"]
    assert isinstance(run, dict)
    run["active_agents"] = 2

    config = ScenarioConfig.model_validate(data)

    assert [agent.id for agent in config.active_agents()] == [
        "worker-001",
        "worker-002",
    ]
    assert json.loads(config.normalized_json())["active_agent_ids"] == [
        "worker-001",
        "worker-002",
    ]


@pytest.mark.parametrize("active_agents", [0, 4, 11])
def test_active_agent_count_is_bounded_by_milestone_and_population(
    active_agents: int,
) -> None:
    data = _valid_data()
    run = data["run"]
    assert isinstance(run, dict)
    run["active_agents"] = active_agents

    with pytest.raises(ValidationError, match="active|greater than|less than"):
        ScenarioConfig.model_validate(data)


def test_scheduling_requires_a_due_strategy() -> None:
    data = _valid_data()
    data["scheduling"] = {"kind": "stable", "interval": None}

    with pytest.raises(ValidationError, match="interval or event kind"):
        ScenarioConfig.model_validate(data)


def test_unsupported_component_kinds_are_rejected() -> None:
    data = _valid_data()
    data["storage"] = {"kind": "postgres"}

    with pytest.raises(ValidationError, match="storage"):
        ScenarioConfig.model_validate(data)


def test_commons_environment_accepts_its_action_family() -> None:
    data = _valid_data()
    data["providers"] = {"scripted": {"kind": "mock", "decisions": {}}}
    data["actions"] = [{"kind": "harvest"}, {"kind": "contribute"}]
    data["environment"] = {
        "kind": "commons",
        "initial_resource": 10,
        "initial_endowment": 2,
    }

    config = ScenarioConfig.model_validate(data)

    assert config.environment.kind == "commons"
    assert {action.kind for action in config.actions} == {"harvest", "contribute"}


def test_environment_rejects_an_incompatible_action_family() -> None:
    data = _valid_data()
    data["providers"] = {"scripted": {"kind": "mock", "decisions": {}}}
    data["actions"] = [{"kind": "harvest"}]

    with pytest.raises(ValidationError, match="does not support actions: harvest"):
        ScenarioConfig.model_validate(data)


def test_social_commons_explicitly_enables_speech() -> None:
    data = _valid_data()
    data["providers"] = {
        "scripted": {
            "kind": "mock",
            "decisions": {"alice": [{"kind": "say", "parameters": {"text": "hi"}}]},
        }
    }
    data["actions"] = [{"kind": "say"}, {"kind": "harvest"}]
    data["environment"] = {
        "kind": "commons",
        "initial_resource": 3,
        "social": {"message_max_length": 40, "history_limit": 2},
    }
    data["memory"] = {
        "kind": "in_memory",
        "recall_limit": 2,
        "retention_limit": 4,
    }

    config = ScenarioConfig.model_validate(data)

    assert config.environment.kind == "commons"
    assert config.environment.social is not None
    assert config.environment.social.history_limit == 2
    assert config.memory.retention_limit == 4


def test_speech_requires_social_commons_mode() -> None:
    data = _valid_data()
    data["providers"] = {"scripted": {"kind": "mock", "decisions": {}}}
    data["actions"] = [{"kind": "say"}]
    data["environment"] = {"kind": "commons", "initial_resource": 3}

    with pytest.raises(ValidationError, match="does not support actions: say"):
        ScenarioConfig.model_validate(data)
