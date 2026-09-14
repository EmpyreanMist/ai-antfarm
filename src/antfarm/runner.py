"""Scenario execution facade used by the CLI and tests."""

from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import TextIO
from uuid import uuid4

from antfarm.adapters.models.ollama import OllamaModelPreflight
from antfarm.adapters.terminal import LiveTerminalObserver, checkpoint_location
from antfarm.application.continuous import PacingClock
from antfarm.application.contracts import RunSummary as RunSummary
from antfarm.config import load_scenario
from antfarm.config.schema import OpenAICompatibleProviderConfig, ScenarioConfig
from antfarm.domain.models import AgentId, Event, Tick
from antfarm.facade import AntFarmApplication, event_view
from antfarm.population import (
    RuntimeOverrides,
    resolve_run_config,
)


async def run_scenario(path: str | Path) -> RunSummary:
    application = AntFarmApplication()
    resolved = application.resolve_population(load_scenario(path))
    handle = application.start_run(resolved)
    snapshot = await application.wait_run(handle.run_id)
    return RunSummary(
        run_id=str(handle.run_id),
        ticks=int(snapshot.tick),
        final_state=snapshot.world,
        events=tuple(
            event_view(event) for event in application.read_events(handle.run_id)
        ),
        metrics=snapshot.metrics,
    )


async def run_continuous_scenario(
    path: str | Path,
    *,
    tick_seconds: float,
    on_batch: Callable[[Sequence[Event]], None] | None = None,
) -> RunSummary:
    """Run until cancellation without accumulating committed event batches."""

    application = AntFarmApplication()
    resolved = application.resolve_population(load_scenario(path))
    handle = application.start_run(
        resolved,
        continuous=True,
        tick_seconds=tick_seconds,
        on_batch=on_batch,
    )
    snapshot = await application.wait_run(handle.run_id)
    return RunSummary(
        run_id=str(handle.run_id),
        ticks=int(snapshot.tick),
        final_state=snapshot.world,
        events=(),
        metrics=snapshot.metrics,
    )


def prepare_live_config(
    path: str | Path,
    *,
    active_agents: int | None = None,
    model: str | None = None,
    run_id: str | None = None,
) -> ScenarioConfig:
    """Apply live-only overrides and revalidate the complete scenario."""

    source = load_scenario(path)
    selected_count = active_agents
    if selected_count is None:
        selected_count = source.run.active_agents or len(source.expand_agents())
    return resolve_run_config(
        source,
        RuntimeOverrides(
            active_agents=selected_count,
            model=model,
            run_id=run_id or _fresh_run_id(source.run.id),
        ),
    )


async def run_live_scenario(
    path: str | Path,
    *,
    tick_seconds: float,
    output: TextIO,
    active_agents: int | None = None,
    model: str | None = None,
    verbose: bool = False,
    run_id: str | None = None,
    clock: PacingClock | None = None,
    should_stop: Callable[[], bool] | None = None,
) -> RunSummary:
    """Run a live society and render committed events without retaining batches."""

    config = prepare_live_config(
        path, active_agents=active_agents, model=model, run_id=run_id
    )
    await _preflight_ollama(config)
    terminal = LiveTerminalObserver(output, verbose=verbose)

    def cognition_started(tick: Tick, agent_id: AgentId, model_ref: str) -> None:
        resolved = config.models[model_ref]
        provider = config.providers[resolved.provider_ref]
        backend = (
            "Ollama"
            if getattr(provider, "runtime", None) == "ollama"
            else provider.kind
        )
        terminal.thinking(
            tick,
            agent_id,
            model_ref,
            backend,
            resolved.model,
        )

    def batch_completed(events: Sequence[Event]) -> None:
        del events
        terminal.raise_if_failed()

    application = AntFarmApplication()
    resolved = application.resolve_population(
        config,
        RuntimeOverrides(
            active_agents=config.run.active_agents,
            model=model,
            run_id=config.run.id,
        ),
    )
    handle = application.start_run(
        resolved,
        continuous=True,
        tick_seconds=tick_seconds,
        on_cognition_started=cognition_started if verbose else None,
        clock=clock,
        should_stop=should_stop,
        on_waiting=terminal.waiting if verbose else None,
        on_batch=batch_completed,
    )
    subscription = application.subscribe_events(
        handle.run_id,
        terminal.event_kinds, terminal.observe
    )
    try:
        terminal.header(config, tick_seconds=tick_seconds)

        snapshot = await application.wait_run(handle.run_id)
        summary = RunSummary(
            run_id=config.run.id,
            ticks=int(snapshot.tick),
            final_state=snapshot.world,
            events=(),
            metrics=snapshot.metrics,
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


def _fresh_run_id(base: str) -> str:
    timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S-%f")
    return f"{base}-{timestamp}-{uuid4().hex[:8]}"


async def _preflight_ollama(config: ScenarioConfig) -> None:
    grouped: dict[str, set[str]] = {}
    for agent in config.active_agents():
        model = config.models[agent.model_ref]
        provider = config.providers[model.provider_ref]
        if (
            isinstance(provider, OpenAICompatibleProviderConfig)
            and provider.runtime == "ollama"
        ):
            grouped.setdefault(model.provider_ref, set()).add(model.model)
    for provider_ref in sorted(grouped):
        provider = config.providers[provider_ref]
        if not isinstance(provider, OpenAICompatibleProviderConfig):
            raise TypeError("Ollama preflight requires an OpenAI-compatible provider")
        await OllamaModelPreflight(base_url=provider.base_url).ensure_available(
            sorted(grouped[provider_ref])
        )
