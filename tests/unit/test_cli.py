import sys

import pytest

from antfarm import cli
from antfarm.application import EventView
from antfarm.runner import RunSummary


def _failed_summary() -> RunSummary:
    return RunSummary(
        run_id="failed-run",
        ticks=1,
        final_state={"value": 0},
        events=(
            EventView(
                schema_version=1,
                event_id="failed-run:1",
                run_id="failed-run",
                sequence=1,
                tick=1,
                kind="cognition.failed",
                actor_id="alice",
                causation_id=None,
                payload={"reason": "ConnectionError"},
            ),
        ),
        metrics={"failure_count": {"total": 1}},
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
    assert 'metrics={"failure_count":{"total":1}}' in captured.out
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


def test_continuous_run_is_explicit_and_reports_last_committed_tick(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    async def continuous_run(
        path: object, *, tick_seconds: float
    ) -> RunSummary:
        del path
        assert tick_seconds == 0.5
        return RunSummary(
            run_id="continuous-test",
            ticks=7,
            final_state={"value": 4},
            events=(),
        )

    monkeypatch.setattr(cli, "run_continuous_scenario", continuous_run)

    result = cli.main(
        ["run", "scenario.yaml", "--continuous", "--tick-seconds", "0.5"]
    )
    captured = capsys.readouterr()

    assert result == 0
    assert "continuous; tick interval >= 0.5s; Ctrl+C to stop" in captured.out
    assert "stopped; last committed tick=7" in captured.out
    assert "events=0" in captured.out


def test_live_run_forwards_agent_count_and_owns_its_output(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    async def live_run(
        path: object,
        *,
        tick_seconds: float,
        active_agents: int | None,
        model: str | None,
        verbose: bool,
        output: object,
    ) -> RunSummary:
        del path
        assert tick_seconds == 0.25
        assert active_agents == 7
        assert model == "gemma4:e2b"
        assert verbose is True
        assert output is sys.stdout
        print("live output")
        return RunSummary("fresh-live", 2, {"resource": 3}, ())

    monkeypatch.setattr(cli, "run_live_scenario", live_run)

    result = cli.main(
        [
            "run",
            "scenario.yaml",
            "--live",
            "--continuous",
            "--agents",
            "7",
            "--model",
            "gemma4:e2b",
            "--verbose",
            "--tick-seconds",
            "0.25",
        ]
    )

    assert result == 0
    assert capsys.readouterr().out == "live output\n"


def test_live_flags_require_explicit_continuous_mode(
    capsys: pytest.CaptureFixture[str],
) -> None:
    result = cli.main(["run", "scenario.yaml", "--live"])

    assert result == 2
    assert "--live requires --continuous" in capsys.readouterr().err


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        (["--model", "gemma4:e2b"], "--model requires --live"),
        (["--verbose"], "--verbose requires --live"),
    ],
)
def test_live_only_options_fail_deterministically_without_live_mode(
    arguments: list[str],
    message: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    result = cli.main(["run", "scenario.yaml", *arguments])

    assert result == 2
    assert message in capsys.readouterr().err


def test_runtime_model_cli_value_rejects_whitespace(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit):
        cli.build_parser().parse_args(
            [
                "run",
                "scenario.yaml",
                "--live",
                "--continuous",
                "--model",
                "  ",
            ]
        )

    assert "non-empty trimmed value" in capsys.readouterr().err
