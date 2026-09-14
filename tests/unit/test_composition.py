import asyncio

import pytest

import antfarm.composition as composition
from antfarm.config.schema import ScenarioConfig
from antfarm.domain import AgentId, RunLimit
from antfarm.ports.models import ModelRequest, ModelResponse, ProviderCapabilities


def _shared_model_config() -> ScenarioConfig:
    return ScenarioConfig.model_validate(
        {
            "schema_version": 1,
            "run": {"id": "shared-context", "seed": 7, "ticks": 2},
            "providers": {
                "local": {
                    "kind": "openai_compatible",
                    "base_url": "http://localhost:11434/v1",
                }
            },
            "models": {
                "shared": {
                    "provider_ref": "local",
                    "model": "local-model",
                    "timeout_seconds": 5,
                }
            },
            "personalities": {
                "patient": {
                    "description": "Waits for a good opportunity.",
                    "traits": {"tempo": "slow"},
                },
                "bold": {
                    "description": "Acts decisively.",
                    "traits": {"tempo": "fast"},
                },
            },
            "agents": [
                {
                    "id": "alice",
                    "model_ref": "shared",
                    "personality_ref": "patient",
                },
                {
                    "id": "bob",
                    "model_ref": "shared",
                    "personality_ref": "bold",
                },
                {"id": "charlie", "model_ref": "shared"},
            ],
            "actions": [{"kind": "increment"}],
            "environment": {"kind": "counter", "initial_value": 0},
            "memory": {"kind": "in_memory", "recall_limit": 2},
            "scheduling": {"kind": "stable"},
            "storage": {"kind": "memory"},
        }
    )


class _RecordingProvider:
    capabilities = ProviderCapabilities(
        structured_output=True,
        network_required=True,
    )
    instances: list["_RecordingProvider"] = []

    def __init__(self, **kwargs: object) -> None:
        del kwargs
        self.requests: list[ModelRequest] = []
        self.close_count = 0
        self.instances.append(self)

    async def generate(self, request: ModelRequest) -> ModelResponse:
        self.requests.append(request)
        return ModelResponse(action_kind="increment", parameters={"amount": 1})

    async def close(self) -> None:
        self.close_count += 1


def test_composition_shares_backend_but_keeps_agent_context_isolated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _RecordingProvider.instances.clear()
    monkeypatch.setattr(
        composition, "OpenAICompatibleModelProvider", _RecordingProvider
    )
    simulation = composition.compose(_shared_model_config())

    asyncio.run(simulation.engine.run(limit=RunLimit(ticks=2)))
    asyncio.run(simulation.close())

    assert len(_RecordingProvider.instances) == 1
    assert _RecordingProvider.instances[0].close_count == 1
    requests = _RecordingProvider.instances[0].requests
    assert [request.identity.id for request in requests] == [
        AgentId("alice"),
        AgentId("bob"),
        AgentId("charlie"),
        AgentId("alice"),
        AgentId("bob"),
        AgentId("charlie"),
    ]
    assert [
        request.personality.description if request.personality is not None else None
        for request in requests[:3]
    ] == ["Waits for a good opportunity.", "Acts decisively.", None]
    assert [len(request.memories) for request in requests[:3]] == [0, 0, 0]
    assert [request.memories[0].content["value"] for request in requests[3:]] == [
        1,
        2,
        3,
    ]


def test_composition_delivers_distinct_rich_profiles_over_a_shared_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = _shared_model_config().model_dump(mode="json")
    source["personalities"] = {}
    source["profiles"] = {
        "patient": {
            "identity": {"display_name": "Alice"},
            "goals": ["Preserve resources"],
            "behavioral_traits": {"patience": 0.9, "risk_tolerance": 0.1},
        },
        "bold": {
            "identity": {"display_name": "Bob"},
            "goals": ["Act before rivals"],
            "behavioral_traits": {"patience": 0.1, "risk_tolerance": 0.9},
        },
    }
    source["agents"] = [
        {"id": "alice", "model_ref": "shared", "profile_ref": "patient"},
        {"id": "bob", "model_ref": "shared", "profile_ref": "bold"},
    ]
    config = ScenarioConfig.model_validate(source)
    _RecordingProvider.instances.clear()
    monkeypatch.setattr(
        composition, "OpenAICompatibleModelProvider", _RecordingProvider
    )

    simulation = composition.compose(config)
    asyncio.run(simulation.engine.step())

    requests = _RecordingProvider.instances[0].requests
    assert len(requests) == 2
    assert requests[0].profile is not None
    assert requests[1].profile is not None
    assert requests[0].profile != requests[1].profile
    assert requests[0].profile.goals is not None
    assert requests[1].profile.goals is not None
    assert requests[0].profile.goals.statements == ("Preserve resources",)
    assert requests[1].profile.goals.statements == ("Act before rivals",)
    assert requests[0].personality is None
    assert requests[1].personality is None


def test_economic_context_exposes_only_permitted_other_agent_information(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = _shared_model_config().model_dump(mode="json")
    source["personalities"] = {}
    source["profiles"] = {
        "public-wealth": {
            "beliefs": ["Alice private belief"],
            "social_status": {"label": "established", "standing": 0.8},
            "economics": {
                "money": 100,
                "resources": {"workshop": 1},
                "recurring_income": 10,
                "occupation": "builder",
            },
            "visibility": {
                "wealth": "public",
                "possessions": "public",
                "occupation": "public",
                "status": "public",
            },
            "private_information": ["Alice private secret"],
        },
        "private-wealth": {
            "beliefs": ["Bob private belief"],
            "social_status": {"label": "unknown", "standing": 0.2},
            "economics": {
                "money": 3,
                "resources": {"tools": 2},
                "recurring_income": 1,
                "occupation": "repairer",
            },
            "private_information": ["Bob private secret"],
        },
    }
    source["agents"] = [
        {"id": "alice", "model_ref": "shared", "profile_ref": "public-wealth"},
        {"id": "bob", "model_ref": "shared", "profile_ref": "private-wealth"},
    ]
    source["actions"] = [{"kind": "harvest"}]
    source["environment"] = {
        "kind": "commons",
        "initial_resource": 20,
        "initial_endowment": 0,
        "initial_holdings": {"alice": 9, "bob": 1},
        "social": {},
    }
    config = ScenarioConfig.model_validate(source)
    _RecordingProvider.instances.clear()
    monkeypatch.setattr(
        composition, "OpenAICompatibleModelProvider", _RecordingProvider
    )

    simulation = composition.compose(config)
    asyncio.run(simulation.engine.step())

    alice_request, bob_request = _RecordingProvider.instances[0].requests
    assert alice_request.profile is not None
    assert bob_request.profile is not None
    assert alice_request.profile.economics is not None
    assert bob_request.profile.economics is not None
    assert alice_request.profile.economics.money == 100
    assert bob_request.profile.economics.money == 3
    assert alice_request.observation.state["own_holding"] == 9
    assert bob_request.observation.state["own_holding"] == 1
    assert alice_request.observation.state["roster"] == (
        {"id": "alice"},
        {"id": "bob"},
    )
    assert bob_request.observation.state["roster"] == (
        {
            "id": "alice",
            "public_profile": {
                "economics": {
                    "money": 100,
                    "recurring_income": 10,
                    "resources": {"workshop": 1},
                    "occupation": "builder",
                    "holding": 9,
                },
                "social_status": {"label": "established", "standing": 0.8},
            },
        },
        {"id": "bob"},
    )
    assert "Alice private" not in str(bob_request.observation.state)
    assert "Bob private" not in str(alice_request.observation.state)


class _UnavailableProvider(_RecordingProvider):
    async def generate(self, request: ModelRequest) -> ModelResponse:
        del request
        raise ConnectionError("private backend detail")


def test_unavailable_backend_is_inert_and_reports_a_bounded_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _UnavailableProvider.instances.clear()
    monkeypatch.setattr(
        composition, "OpenAICompatibleModelProvider", _UnavailableProvider
    )
    simulation = composition.compose(_shared_model_config())

    result = asyncio.run(simulation.engine.step())

    assert dict(result.snapshot.world) == {"value": 0}
    failures = [event for event in result.events if event.kind == "cognition.failed"]
    assert len(failures) == 3
    assert all(
        dict(event.payload) == {"reason": "ConnectionError"} for event in failures
    )
    assert all(
        "private backend detail" not in str(event.payload) for event in failures
    )
