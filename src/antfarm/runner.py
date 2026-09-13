"""Scenario execution facade used by the CLI and tests."""

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from types import MappingProxyType
from typing import TextIO, cast
from uuid import uuid4

from antfarm.adapters.terminal import LiveTerminalObserver, checkpoint_location
from antfarm.application.continuous import ContinuousRunner, PacingClock
from antfarm.composition import compose
from antfarm.config import load_scenario
from antfarm.config.schema import ScenarioConfig
from antfarm.domain.json_values import JsonObject
from antfarm.domain.models import Event, RunLimit


@dataclass(frozen=True, slots=True)
class RunSummary:
    run_id: str
    ticks: int
    final_state: JsonObject
    events: tuple[Event, ...]
    metrics: JsonObject = field(default_factory=lambda: MappingProxyType({}))
    active_agent_count: int = 0
    checkpoint: str = "memory (not durable)"


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


def prepare_live_config(
    path: str | Path,
    *,
    active_agents: int | None = None,
    run_id: str | None = None,
) -> ScenarioConfig:
    """Apply live-only overrides and revalidate the complete scenario."""

    source = load_scenario(path)
    data = source.model_dump(mode="json")
    run = cast(dict[str, object], data["run"])
    selected_count = active_agents
    if selected_count is None:
        selected_count = source.run.active_agents or len(source.expand_agents())
    run["active_agents"] = selected_count
    run["id"] = run_id or _fresh_run_id(source.run.id)
    return ScenarioConfig.model_validate(data)


async def run_live_scenario(
    path: str | Path,
    *,
    tick_seconds: float,
    output: TextIO,
    active_agents: int | None = None,
    run_id: str | None = None,
    clock: PacingClock | None = None,
    should_stop: Callable[[], bool] | None = None,
) -> RunSummary:
    """Run a live society and render committed events without retaining batches."""

    config = prepare_live_config(
        path, active_agents=active_agents, run_id=run_id
    )
    terminal = LiveTerminalObserver(output)
    simulation = compose(config, on_cognition_started=terminal.thinking)
    subscription = simulation.event_bus.subscribe(
        terminal.event_kinds, terminal.observe
    )
    try:
        terminal.header(config, tick_seconds=tick_seconds)

        def batch_completed(events: Sequence[Event]) -> None:
            del events
            terminal.raise_if_failed()

        result = await ContinuousRunner(
            simulation.engine,
            tick_seconds=tick_seconds,
            clock=clock,
            on_batch=batch_completed,
            should_stop=should_stop,
            on_waiting=terminal.waiting,
        ).run()
        summary = RunSummary(
            run_id=config.run.id,
            ticks=int(result.snapshot.tick),
            final_state=result.snapshot.world,
            events=(),
            metrics=result.snapshot.metrics,
            active_agent_count=len(config.active_agents()),
            checkpoint=checkpoint_location(config),
        )
        terminal.final(
            tick=summary.ticks,
            active_agents=summary.active_agent_count,
            world=summary.final_state,
            metrics=summary.metrics,
            checkpoint=summary.checkpoint,
        )
        return summary
    finally:
        subscription.cancel()
        await simulation.close()


def _fresh_run_id(base: str) -> str:
    timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S-%f")
    return f"{base}-{timestamp}-{uuid4().hex[:8]}"
