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
