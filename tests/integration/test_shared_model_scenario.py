import asyncio
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


def test_three_agent_mock_scenario_is_finite_and_deterministic() -> None:
    path = REPOSITORY / "scenarios/examples/shared-model-mock.yaml"

    first = asyncio.run(run_scenario(path))
    second = asyncio.run(run_scenario(path))

    assert first == second
    assert first.ticks == 2
    assert dict(first.final_state) == {
        "resource": 4,
        "holdings": {"alice": 1, "bob": 0, "charlie": 1},
    }
    assert [event.kind for event in first.events].count("action.applied") == 6


def test_three_agent_ollama_example_validates_and_inspects_offline() -> None:
    validated = _cli("validate", "scenarios/examples/shared-model-ollama.yaml")
    inspected = _cli("inspect", "scenarios/examples/shared-model-ollama.yaml")

    assert validated.returncode == 0, validated.stderr
    assert validated.stdout.strip() == "valid scenario: shared-model-ollama"
    assert inspected.returncode == 0, inspected.stderr
    assert '"personality_ref":"cautious"' in inspected.stdout
    assert inspected.stdout.count('"model_ref":"qwen-local"') == 6
