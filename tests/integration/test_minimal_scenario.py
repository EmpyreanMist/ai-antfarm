import asyncio
import json
import subprocess
import sys
from pathlib import Path

from antfarm.runner import run_scenario

REPOSITORY = Path(__file__).parents[2]


def _cli(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "antfarm.cli", *arguments],
        cwd=REPOSITORY,
        check=False,
        capture_output=True,
        text=True,
    )


def test_minimal_scenario_runs_end_to_end() -> None:
    completed = _cli("run", "scenarios/examples/minimal.yaml")

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == (
        'run=minimal ticks=1 events=10 final_state={"value":3}'
    )
    assert completed.stderr == ""


def test_two_seeded_runs_have_matching_events_and_final_state() -> None:
    path = REPOSITORY / "scenarios/examples/minimal.yaml"

    first = asyncio.run(run_scenario(path))
    second = asyncio.run(run_scenario(path))

    assert first == second
    assert [event.kind for event in first.events] == [
        event.kind for event in second.events
    ]


def test_inspect_prints_canonical_expanded_scenario() -> None:
    completed = _cli("inspect", "scenarios/examples/minimal.yaml")

    assert completed.returncode == 0, completed.stderr
    inspected = json.loads(completed.stdout)
    assert [agent["id"] for agent in inspected["expanded_agents"]] == [
        "alice-001",
        "bob",
    ]
    assert completed.stdout.strip() == json.dumps(
        inspected, sort_keys=True, separators=(",", ":")
    )


def test_validation_failure_is_reported_on_stderr(tmp_path: Path) -> None:
    invalid = tmp_path / "invalid.yaml"
    invalid.write_text("schema_version: 999\n", encoding="utf-8")

    completed = _cli("validate", str(invalid))

    assert completed.returncode == 2
    assert completed.stdout == ""
    assert completed.stderr.startswith("error:")


def test_ollama_example_validates_without_contacting_provider() -> None:
    completed = _cli("validate", "scenarios/examples/ollama.yaml")

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == "valid scenario: ollama-local"
