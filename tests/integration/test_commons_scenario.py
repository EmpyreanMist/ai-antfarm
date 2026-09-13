import asyncio
import subprocess
import sys
from pathlib import Path

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
        'final_state={"holdings":{"alice":2,"bob":1},"resource":2}'
    )
