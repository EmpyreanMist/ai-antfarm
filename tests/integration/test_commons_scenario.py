import asyncio
import subprocess
import sys
from pathlib import Path

from antfarm.domain.json_values import thaw_json
from antfarm.runner import run_scenario


def test_commons_scenario_runs_deterministically_end_to_end() -> None:
    repository = Path(__file__).parents[2]
    scenario = repository / "scenarios/examples/commons.yaml"

    first = asyncio.run(run_scenario(scenario))
    second = asyncio.run(run_scenario(scenario))

    assert first == second
    assert dict(first.final_state) == {
        "resource": 2,
        "holdings": {"alice": 2, "bob": 1},
    }
    assert len(first.events) == 20
    assert [event.kind for event in first.events].count("action.applied") == 4
    metrics = thaw_json(first.metrics)
    assert isinstance(metrics, dict)
    assert metrics["action_count"] == {
        "total": 4,
        "by_kind": {"contribute": 2, "harvest": 2},
    }
    assert metrics["rejection_count"] == {"total": 0}


def test_commons_scenario_runs_through_cli() -> None:
    repository = Path(__file__).parents[2]

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "antfarm.cli",
            "run",
            "scenarios/examples/commons.yaml",
        ],
        cwd=repository,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == (
        "run=commons-example ticks=2 events=20 "
        'final_state={"holdings":{"alice":2,"bob":1},"resource":2} '
        'metrics={"action_count":{"by_kind":{"contribute":2,"harvest":2},'
        '"total":4},"agent_outcomes":{"alice":{"applied":2,"failed":0,'
        '"malformed":0,"noop":0,"rejected":0,"timed_out":0},"bob":'
        '{"applied":2,"failed":0,"malformed":0,"noop":0,"rejected":0,'
        '"timed_out":0}},"failure_count":{"by_kind":{"failed":0,'
        '"malformed":0,"timed_out":0},"total":0},"rejection_count":'
        '{"total":0}}'
    )
