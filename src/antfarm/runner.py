"""Scenario execution facade used by the CLI and tests."""

from dataclasses import dataclass
from pathlib import Path

from antfarm.composition import compose
from antfarm.config import load_scenario
from antfarm.domain.models import Event, JsonObject


@dataclass(frozen=True, slots=True)
class RunSummary:
    run_id: str
    ticks: int
    final_state: JsonObject
    events: tuple[Event, ...]


async def run_scenario(path: str | Path) -> RunSummary:
    config = load_scenario(path)
    simulation = compose(config)
    events: list[Event] = []
    for _ in range(config.run.ticks):
        result = await simulation.engine.step()
        events.extend(result.events)
    return RunSummary(
        run_id=config.run.id,
        ticks=config.run.ticks,
        final_state=simulation.engine.snapshot().world,
        events=tuple(events),
    )
