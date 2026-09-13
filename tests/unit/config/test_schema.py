import copy
import json
from collections.abc import Callable

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
    data["metrics"] = ["action_count", "rejection_count"]
    data["storage"] = {"kind": "sqlite", "path": "runs.db"}
    data["observability"] = {"event_detail": "failures", "include_model_io": False}

    config = ScenarioConfig.model_validate(data)

    assert config.models["local-model"].provider_ref == "remote"
    assert config.storage.kind == "sqlite"
    assert config.metrics == ("action_count", "rejection_count")


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


def test_unsupported_component_kinds_are_rejected() -> None:
    data = _valid_data()
    data["storage"] = {"kind": "postgres"}

    with pytest.raises(ValidationError, match="storage"):
        ScenarioConfig.model_validate(data)
