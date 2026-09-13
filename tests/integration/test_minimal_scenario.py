import subprocess
import sys
from pathlib import Path


def test_minimal_scenario_runs_end_to_end() -> None:
    repository = Path(__file__).parents[2]
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "antfarm.cli",
            "run",
            "scenarios/examples/minimal.yaml",
        ],
        cwd=repository,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == (
        'run=minimal ticks=1 events=10 final_state={"value":3}'
    )
