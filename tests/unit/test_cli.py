import pytest

from antfarm import cli
from antfarm.domain import AgentId, Event, EventSequence, RunId, Tick
from antfarm.runner import RunSummary


def _failed_summary() -> RunSummary:
    return RunSummary(
        run_id="failed-run",
        ticks=1,
        final_state={"value": 0},
        events=(
            Event(
                schema_version=1,
                event_id="failed-run:1",
                run_id=RunId("failed-run"),
                sequence=EventSequence(1),
                tick=Tick(1),
                kind="cognition.failed",
                actor_id=AgentId("alice"),
                causation_id=None,
                payload={"reason": "ConnectionError"},
            ),
        ),
    )


def test_run_with_cognition_failure_returns_nonzero(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    async def failed_run(path: object) -> RunSummary:
        del path
        return _failed_summary()

    monkeypatch.setattr(cli, "run_scenario", failed_run)

    result = cli.main(["run", "scenario.yaml"])
    captured = capsys.readouterr()

    assert result == 3
    assert "final_state={\"value\":0}" in captured.out
    assert "alice:cognition.failed(ConnectionError)" in captured.err


def test_unexpected_runtime_failure_returns_nonzero(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    async def broken_run(path: object) -> RunSummary:
        del path
        raise RuntimeError("unexpected failure")

    monkeypatch.setattr(cli, "run_scenario", broken_run)

    result = cli.main(["run", "scenario.yaml"])
    captured = capsys.readouterr()

    assert result == 1
    assert captured.out == ""
    assert captured.err.strip() == "runtime error: RuntimeError: unexpected failure"
