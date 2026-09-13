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
from antfarm.adapters.storage import SQLiteStorage
from antfarm.adapters.terminal import TerminalOutputError
from antfarm.config import load_scenario
from antfarm.config.schema import ScenarioConfig
from antfarm.domain import AgentId, RunId
from antfarm.domain.json_values import JsonObject
from antfarm.ports.models import ModelRequest, ModelResponse

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
    assert rendered.index("[event tick 1]") < rendered.index("[status] Stopping...")
    assert "proposal.created" not in rendered
    assert "action.validated" not in rendered
    assert "observation.created" not in rendered
    assert "\x1b" not in rendered
    assert 'Alice says: "hello�[2J world"' in rendered
    assert "Bob harvest rejected: amount exceeds available resource" in rendered
    assert "Charlie harvests 1; resource=7; actor_holding=3" in rendered
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


class _BrokenAfterHeader(io.StringIO):
    def __init__(self) -> None:
        super().__init__()
        self.writes = 0

    def write(self, value: str) -> int:
        self.writes += 1
        if self.writes > 11:
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
