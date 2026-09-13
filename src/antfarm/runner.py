"""Scenario execution facade used by the CLI and tests."""

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType

from antfarm.application.continuous import ContinuousRunner
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
    metrics: JsonObject = field(default_factory=lambda: MappingProxyType({}))


async def run_scenario(path: str | Path) -> RunSummary:
    config = load_scenario(path)
    simulation = compose(config)
    try:
        result = await simulation.engine.run(RunLimit(ticks=config.run.ticks))
        return RunSummary(
            run_id=config.run.id,
            ticks=int(result.snapshot.tick),
            final_state=result.snapshot.world,
            events=tuple(result.events),
            metrics=result.snapshot.metrics,
        )
    finally:
        await simulation.close()


async def run_continuous_scenario(
    path: str | Path,
    *,
    tick_seconds: float,
    on_batch: Callable[[Sequence[Event]], None] | None = None,
) -> RunSummary:
    """Run until cancellation without accumulating committed event batches."""

    config = load_scenario(path)
    simulation = compose(config)
    try:
        result = await ContinuousRunner(
            simulation.engine,
            tick_seconds=tick_seconds,
            on_batch=on_batch,
        ).run()
        return RunSummary(
            run_id=config.run.id,
            ticks=int(result.snapshot.tick),
            final_state=result.snapshot.world,
            events=(),
            metrics=result.snapshot.metrics,
        )
    finally:
        await simulation.close()
