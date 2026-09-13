import asyncio
import io
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import cast

import pytest
from pydantic import ValidationError

import antfarm.composition as composition
import antfarm.runner as runner
from antfarm.adapters.models import MockModelProvider
from antfarm.adapters.models.ollama import OllamaPreflightError
from antfarm.adapters.storage import SQLiteStorage
from antfarm.adapters.terminal import LiveTerminalObserver, TerminalOutputError
from antfarm.config import load_scenario
from antfarm.config.schema import ScenarioConfig
from antfarm.domain import AgentId, RunId
from antfarm.domain.json_values import JsonObject
from antfarm.ports.models import (
    ModelRequest,
    ModelResponse,
    ProviderCapabilities,
)

REPOSITORY = Path(__file__).parents[2]
SCENARIO = REPOSITORY / "scenarios/examples/live-social-mock.yaml"


class _FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def monotonic(self) -> float:
        return self.now

    async def sleep(self, delay: float) -> None:
        self.now += delay


class _RecordingMockProvider(MockModelProvider):
    instance: "_RecordingMockProvider | None" = None

    def __init__(
        self,
        decisions: Mapping[AgentId, Sequence[ModelResponse | Exception]],
    ) -> None:
        super().__init__(decisions)
        self.requests: list[ModelRequest] = []
        type(self).instance = self

    async def generate(self, request: ModelRequest) -> ModelResponse:
        self.requests.append(request)
        return await super().generate(request)


class _RecordingNetworkProvider:
    capabilities = ProviderCapabilities(
        structured_output=True,
        network_required=True,
    )
    models: list[str] = []

    def __init__(self, **kwargs: object) -> None:
        model = kwargs.get("model")
        assert isinstance(model, str)
        type(self).models.append(model)

    async def generate(self, request: ModelRequest) -> ModelResponse:
        del request
        raise AssertionError("stopped test must not start cognition")

    async def close(self) -> None:
        pass


class _RecordingPreflight:
    checks: list[tuple[str, tuple[str, ...]]] = []

    def __init__(self, *, base_url: str) -> None:
        self.base_url = base_url

    async def ensure_available(self, models: Sequence[str]) -> None:
        type(self).checks.append((self.base_url, tuple(models)))


class _MissingModelPreflight:
    def __init__(self, *, base_url: str) -> None:
        del base_url

    async def ensure_available(self, models: Sequence[str]) -> None:
        raise OllamaPreflightError(f"missing {models[0]}")


def _stop_after(ticks: int) -> Callable[[], bool]:
    checks = 0

    def should_stop() -> bool:
        nonlocal checks
        checks += 1
        return checks > ticks

    return should_stop


def _temporary_config(tmp_path: Path) -> ScenarioConfig:
    source = load_scenario(SCENARIO)
    data = source.model_dump(mode="json")
    data["storage"] = {"kind": "sqlite", "path": str(tmp_path / "live.db")}
    providers = cast(dict[str, object], data["providers"])
    scripted = cast(dict[str, object], providers["scripted"])
    decisions = cast(dict[str, list[dict[str, object]]], scripted["decisions"])
    decisions["alice"][0] = {
        "kind": "say",
        "parameters": {"text": "hello\x1b[2J\nworld"},
    }
    return ScenarioConfig.model_validate(data)


def test_live_social_end_to_end_uses_committed_events_and_isolated_context(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _temporary_config(tmp_path)
    monkeypatch.setattr(runner, "load_scenario", lambda path: config)
    monkeypatch.setattr(composition, "MockModelProvider", _RecordingMockProvider)
    output = io.StringIO()

    summary = asyncio.run(
        runner.run_live_scenario(
            "unused.yaml",
            tick_seconds=1,
            output=output,
            run_id="live-e2e",
            clock=_FakeClock(),
            should_stop=_stop_after(13),
        )
    )

    rendered = output.getvalue()
    assert rendered.index("[tick 1]") < rendered.index("Stopping...")
    assert "thinking via" not in rendered
    assert "[status]" not in rendered
    assert "proposal.created" not in rendered
    assert "action.validated" not in rendered
    assert "observation.created" not in rendered
    assert "\x1b" not in rendered
    assert 'Alice says: "hello�[2J world"' in rendered
    assert "Bob's harvest was rejected: amount exceeds available resource." in rendered
    assert "Charlie harvested 1; resource=7; holding=3." in rendered
    assert summary.ticks == 13
    assert summary.active_agent_count == 3

    provider = _RecordingMockProvider.instance
    assert provider is not None
    assert [str(request.actor_id) for request in provider.requests[:3]] == [
        "alice",
        "bob",
        "charlie",
    ]
    personalities = [request.personality for request in provider.requests[:3]]
    assert all(personality is not None for personality in personalities)
    assert len(
        {
            personality.description
            for personality in personalities
            if personality is not None
        }
    ) == 3
    recent_messages = cast(
        tuple[JsonObject, ...],
        provider.requests[1].observation.state["recent_messages"],
    )
    assert recent_messages[0]["sender_id"] == "alice"
    assert provider.requests[1].memories[-1].content["sender_id"] == "alice"
    assert all(
        "personality" not in request.observation.state
        for request in provider.requests[:3]
    )

    database = tmp_path / "live.db"
    with SQLiteStorage(database) as storage:
        checkpoint = storage.load_latest(RunId("live-e2e"))
        events = tuple(storage.read_events(RunId("live-e2e")))
    assert checkpoint is not None
    assert checkpoint.snapshot.tick == summary.ticks
    assert checkpoint.snapshot.world == summary.final_state
    assert any(event.kind == "action.rejected" for event in events)
    assert sum(event.kind == "action.applied" for event in events) == 4


def test_live_agent_override_selects_a_bounded_distinct_population(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _temporary_config(tmp_path)
    monkeypatch.setattr(runner, "load_scenario", lambda path: config)

    selected = runner.prepare_live_config(
        "unused.yaml", active_agents=10, run_id="ten-agents"
    )
    simulation = composition.compose(selected)

    assert len(selected.active_agents()) == 10
    assert len({agent.id for agent in selected.active_agents()}) == 10
    assert len(simulation.providers) == 1
    holdings = cast(
        Mapping[str, object], simulation.engine.snapshot().world["holdings"]
    )
    assert set(holdings) == {
        agent.id for agent in selected.active_agents()
    }
    asyncio.run(simulation.close())

    data = selected.model_dump(mode="json")
    run = cast(dict[str, object], data["run"])
    run["active_agents"] = 11
    with pytest.raises(ValidationError, match="less than or equal to 10"):
        ScenarioConfig.model_validate(data)


def test_runtime_model_override_is_ephemeral_and_header_shows_resolved_model() -> None:
    scenario = REPOSITORY / "scenarios/examples/live-social-ollama.yaml"
    before = scenario.read_bytes()

    overridden = runner.prepare_live_config(
        scenario,
        model="gemma4:e2b",
        run_id="model-override",
    )
    unchanged = runner.prepare_live_config(
        scenario,
        run_id="model-default",
    )
    output = io.StringIO()
    LiveTerminalObserver(output).header(overridden, tick_seconds=1)

    assert scenario.read_bytes() == before
    assert overridden.models["local-model"].model == "gemma4:e2b"
    assert unchanged.models["local-model"].model == "qwen3.5:0.8b"
    assert "Backend  Ollama" in output.getvalue()
    assert "Model    gemma4:e2b" in output.getvalue()
    assert "local-model" not in output.getvalue()


def test_live_run_preflights_and_composes_the_runtime_model(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = load_scenario(
        REPOSITORY / "scenarios/examples/live-social-ollama.yaml"
    )
    data = source.model_dump(mode="json")
    data["storage"] = {"kind": "sqlite", "path": str(tmp_path / "ollama.db")}
    config = ScenarioConfig.model_validate(data)
    monkeypatch.setattr(runner, "load_scenario", lambda path: config)
    monkeypatch.setattr(runner, "OllamaModelPreflight", _RecordingPreflight)
    monkeypatch.setattr(
        composition,
        "OpenAICompatibleModelProvider",
        _RecordingNetworkProvider,
    )
    _RecordingPreflight.checks = []
    _RecordingNetworkProvider.models = []

    summary = asyncio.run(
        runner.run_live_scenario(
            "unused.yaml",
            tick_seconds=1,
            output=io.StringIO(),
            model="gemma4:e2b",
            run_id="ollama-runtime-model",
            clock=_FakeClock(),
            should_stop=lambda: True,
        )
    )

    assert summary.ticks == 0
    assert _RecordingPreflight.checks == [
        ("http://localhost:11434/v1", ("gemma4:e2b",))
    ]
    assert _RecordingNetworkProvider.models == ["gemma4:e2b"]


def test_failed_preflight_does_not_create_a_durable_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = load_scenario(
        REPOSITORY / "scenarios/examples/live-social-ollama.yaml"
    )
    database = tmp_path / "not-created.db"
    data = source.model_dump(mode="json")
    data["storage"] = {"kind": "sqlite", "path": str(database)}
    config = ScenarioConfig.model_validate(data)
    monkeypatch.setattr(runner, "load_scenario", lambda path: config)
    monkeypatch.setattr(runner, "OllamaModelPreflight", _MissingModelPreflight)

    with pytest.raises(OllamaPreflightError, match="missing gemma4:e2b"):
        asyncio.run(
            runner.run_live_scenario(
                "unused.yaml",
                tick_seconds=1,
                output=io.StringIO(),
                model="gemma4:e2b",
                run_id="must-not-exist",
                clock=_FakeClock(),
                should_stop=lambda: True,
            )
        )

    assert not database.exists()


def test_runtime_model_override_rejects_incompatible_active_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = load_scenario(SCENARIO)
    monkeypatch.setattr(runner, "load_scenario", lambda path: config)

    with pytest.raises(ValueError, match="requires OpenAI-compatible"):
        runner.prepare_live_config("unused.yaml", model="gemma4:e2b")


def test_verbose_live_mode_exposes_resolved_cognition_status(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _temporary_config(tmp_path)
    monkeypatch.setattr(runner, "load_scenario", lambda path: config)
    output = io.StringIO()

    asyncio.run(
        runner.run_live_scenario(
            "unused.yaml",
            tick_seconds=1,
            output=output,
            verbose=True,
            run_id="verbose-live",
            clock=_FakeClock(),
            should_stop=_stop_after(1),
        )
    )

    rendered = output.getvalue()
    assert "[status] Alice -> provider=scripted; model_ref=shared-model" in rendered
    assert "[status] [tick 1] Alice thinking via " in rendered
    assert "shared-model / mock / fixed-social-decisions" in rendered


class _BrokenAfterHeader(io.StringIO):
    def write(self, value: str) -> int:
        if value.startswith("[tick 1]"):
            raise BrokenPipeError
        return super().write(value)


def test_output_failure_stops_after_commit_without_duplicate_action(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _temporary_config(tmp_path)
    monkeypatch.setattr(runner, "load_scenario", lambda path: config)

    with pytest.raises(TerminalOutputError, match="output stream failed"):
        asyncio.run(
            runner.run_live_scenario(
                "unused.yaml",
                tick_seconds=1,
                output=_BrokenAfterHeader(),
                run_id="broken-output",
                clock=_FakeClock(),
                should_stop=_stop_after(3),
            )
        )

    with SQLiteStorage(tmp_path / "live.db") as storage:
        checkpoint = storage.load_latest(RunId("broken-output"))
        events = tuple(storage.read_events(RunId("broken-output")))
    assert checkpoint is not None
    assert int(checkpoint.snapshot.tick) == 1
    assert sum(event.kind == "action.applied" for event in events) == 1
