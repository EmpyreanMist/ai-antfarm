"""Scenario execution facade used by the CLI and tests."""

from dataclasses import dataclass
from pathlib import Path

from antfarm.composition import compose
from antfarm.config import load_scenario
from antfarm.domain.json_values import JsonObject
from antfarm.domain.models import Event, RunLimit


@dataclass(frozen=True, slots=True)
class RunSummary:
    run_id: str
    ticks: int
    final_state: JsonObject
    events: tuple[Event, ...]


async def run_scenario(path: str | Path) -> RunSummary:
    config = load_scenario(path)
    simulation = compose(config)
    result = await simulation.engine.run(RunLimit(ticks=config.run.ticks))
    return RunSummary(
        run_id=config.run.id,
        ticks=config.run.ticks,
        final_state=result.snapshot.world,
        events=tuple(result.events),
    )
