import asyncio
from pathlib import Path
from typing import cast

import pytest

import antfarm.composition as composition
from antfarm.adapters.storage import SQLiteStorage
from antfarm.config.schema import ScenarioConfig
from antfarm.domain import AgentId, RunId, RunLimit
from antfarm.domain.json_values import JsonObject
from antfarm.ports.models import ModelRequest, ModelResponse, ProviderCapabilities
from antfarm.runner import run_scenario

REPOSITORY = Path(__file__).parents[2]


def test_social_mock_scenario_delivers_bounded_public_messages() -> None:
    summary = asyncio.run(
        run_scenario(REPOSITORY / "scenarios/examples/social-mock.yaml")
    )

    assert summary.ticks == 3
    messages: list[JsonObject] = [
        cast(JsonObject, event.payload["message"])
        for event in summary.events
        if event.kind == "action.applied" and "message" in event.payload
    ]
    assert [message["id"] for message in messages] == [
        "message-1",
        "message-2",
        "message-3",
        "message-4",
    ]
    assert [message["sender_id"] for message in messages] == [
        "alice",
        "charlie",
        "bob",
        "charlie",
    ]
    world_messages = summary.final_state["messages"]
    assert world_messages == tuple(messages)
    action_count = cast(JsonObject, summary.metrics["action_count"])
    by_kind = cast(JsonObject, action_count["by_kind"])
    assert by_kind["say"] == 4


def test_social_ollama_example_validates_without_network() -> None:
    from antfarm.config import load_scenario

    config = load_scenario(REPOSITORY / "scenarios/examples/social-ollama.yaml")

    assert config.environment.kind == "commons"
    assert config.environment.social is not None
    assert config.environment.social.history_limit == 8
    assert dict(config.models["qwen-local"].parameters) == {
        "temperature": 0,
        "seed": 73,
        "reasoning_effort": "none",
        "max_tokens": 256,
    }
    assert {action.kind for action in config.actions} == {
        "harvest",
        "contribute",
        "say",
    }


def test_continuous_example_composes_one_staggered_cognition_per_tick() -> None:
    from antfarm.config import load_scenario

    source = load_scenario(
        REPOSITORY / "scenarios/examples/continuous-social-mock.yaml"
    )
    data = source.model_dump(mode="json")
    data["run"] = {"id": "continuous-composition", "seed": 79, "ticks": 3}
    data["storage"] = {"kind": "memory"}
    simulation = composition.compose(ScenarioConfig.model_validate(data))

    first = asyncio.run(simulation.engine.step())

    observations = [
        event for event in first.events if event.kind == "observation.created"
    ]
    assert [event.actor_id for event in observations] == [AgentId("alice")]


def test_sqlite_retains_speech_after_it_leaves_live_context(tmp_path: Path) -> None:
    from antfarm.config import load_scenario

    source = load_scenario(REPOSITORY / "scenarios/examples/social-mock.yaml")
    data = source.model_dump(mode="json")
    environment = cast(dict[str, object], data["environment"])
    social = cast(dict[str, object], environment["social"])
    social["history_limit"] = 2
    database = tmp_path / "social.db"
    data["storage"] = {"kind": "sqlite", "path": str(database)}
    config = ScenarioConfig.model_validate(data)
    simulation = composition.compose(config)

    asyncio.run(simulation.engine.run(RunLimit(ticks=3)))
    assert isinstance(simulation.storage, SQLiteStorage)
    simulation.storage.close()

    with SQLiteStorage(database) as reopened:
        speech = [
            event
            for event in reopened.read_events(RunId(config.run.id))
            if event.kind == "action.applied" and event.payload.get("kind") == "say"
        ]
        checkpoint = reopened.load_latest(RunId(config.run.id))
    assert len(speech) == 4
    assert checkpoint is not None
    live_messages = cast(tuple[JsonObject, ...], checkpoint.snapshot.world["messages"])
    assert [message["id"] for message in live_messages] == [
        "message-3",
        "message-4",
    ]


class _RecordingSocialProvider:
    capabilities = ProviderCapabilities(
        structured_output=True,
        network_required=True,
    )
    instance: "_RecordingSocialProvider | None" = None

    def __init__(self, **kwargs: object) -> None:
        del kwargs
        self.requests: list[ModelRequest] = []
        type(self).instance = self

    async def generate(self, request: ModelRequest) -> ModelResponse:
        self.requests.append(request)
        if len(self.requests) == 1:
            return ModelResponse(
                action_kind="say", parameters={"text": "hello everyone"}
            )
        return ModelResponse(action_kind=None)


def test_speech_waits_for_next_tick_and_private_context_stays_isolated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from antfarm.config import load_scenario

    config = load_scenario(REPOSITORY / "scenarios/examples/social-ollama.yaml")
    monkeypatch.setattr(
        composition, "OpenAICompatibleModelProvider", _RecordingSocialProvider
    )
    simulation = composition.compose(config)

    asyncio.run(simulation.engine.run(RunLimit(ticks=2)))

    provider = _RecordingSocialProvider.instance
    assert provider is not None
    requests = provider.requests
    assert len(requests) == 6
    assert requests[1].observation.state["recent_messages"] == ()
    assert requests[1].memories == ()
    expected_message = {
        "id": "message-1",
        "sender_id": "alice",
        "tick": 1,
        "text": "hello everyone",
    }
    assert requests[3].observation.state["recent_messages"] == (expected_message,)
    assert requests[4].observation.state["recent_messages"] == (expected_message,)
    assert requests[4].memories[-1].kind == "public_message"
    assert requests[4].memories[-1].content == expected_message
    assert "personality" not in requests[4].observation.state
    assert requests[4].personality is not None
    assert requests[4].personality.description.startswith("Balance personal")
