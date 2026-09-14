"""Transport-neutral application facade at the composition boundary."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from threading import Event as StopEvent

from antfarm.adapters.storage import SQLiteStorage
from antfarm.application.continuous import ContinuousRunner
from antfarm.composition import ComposedSimulation, compose
from antfarm.config import load_scenario
from antfarm.config.schema import ScenarioConfig, SqliteStorageConfig
from antfarm.domain.json_values import JsonObject, freeze_object, thaw_json
from antfarm.domain.models import Event, RunId, RunLimit, SimulationSnapshot, StoredRun
from antfarm.population import (
    RuntimeOverrides,
    resolve_run_config,
    runtime_overrides_data,
)
from antfarm.ports.storage import Storage


@dataclass(frozen=True, slots=True)
class ResolvedRunConfiguration:
    """A complete scenario paired with the runtime choices that produced it."""

    config: ScenarioConfig
    runtime_overrides: JsonObject


@dataclass(frozen=True, slots=True)
class ResolvedAgentInspection:
    """Inspectable configuration and explicitly observable fields for one agent."""

    agent_id: str
    model_ref: str
    model: str
    configuration: JsonObject
    public: JsonObject


@dataclass(slots=True)
class ApplicationRun:
    run_id: RunId
    resolved: ResolvedRunConfiguration
    simulation: ComposedSimulation
    stop_requested: StopEvent
    task: asyncio.Task[SimulationSnapshot]


class AntFarmApplication:
    """Shared application entry point for CLI, tests, and future transports."""

    def __init__(self, storage: Storage | None = None) -> None:
        self._runs: dict[RunId, ApplicationRun] = {}
        self._query_storage = storage

    def load_scenario(self, path: str | Path) -> ScenarioConfig:
        return load_scenario(path)

    def resolve_population(
        self,
        source: ScenarioConfig,
        overrides: RuntimeOverrides | None = None,
    ) -> ResolvedRunConfiguration:
        return ResolvedRunConfiguration(
            config=resolve_run_config(source, overrides),
            runtime_overrides=runtime_overrides_data(overrides),
        )

    def inspect_resolved_agents(
        self, resolved: ResolvedRunConfiguration | ScenarioConfig
    ) -> tuple[ResolvedAgentInspection, ...]:
        config = (
            resolved.config
            if isinstance(resolved, ResolvedRunConfiguration)
            else resolved
        )
        return inspect_resolved_agents(config)

    def start_run(
        self,
        resolved: ResolvedRunConfiguration | ScenarioConfig,
        *,
        continuous: bool = False,
        tick_seconds: float = 1.0,
    ) -> ApplicationRun:
        selected = (
            resolved
            if isinstance(resolved, ResolvedRunConfiguration)
            else ResolvedRunConfiguration(resolved, freeze_object({}))
        )
        run_id = RunId(selected.config.run.id)
        if run_id in self._runs:
            raise ValueError(f"run is already managed: {run_id}")
        simulation = compose(
            selected.config,
            runtime_overrides=selected.runtime_overrides,
        )
        stop_requested = StopEvent()
        task = asyncio.create_task(
            self._execute(
                simulation,
                selected.config,
                stop_requested,
                continuous=continuous,
                tick_seconds=tick_seconds,
            )
        )
        handle = ApplicationRun(
            run_id=run_id,
            resolved=selected,
            simulation=simulation,
            stop_requested=stop_requested,
            task=task,
        )
        self._runs[run_id] = handle
        return handle

    async def wait_run(self, run_id: RunId | str) -> SimulationSnapshot:
        return await self._require_run(run_id).task

    async def stop_run(self, run_id: RunId | str) -> SimulationSnapshot:
        handle = self._require_run(run_id)
        handle.stop_requested.set()
        if not handle.task.done():
            handle.task.cancel()
        return await handle.task

    def read_run(self, run_id: RunId | str) -> StoredRun | None:
        selected = RunId(str(run_id))
        handle = self._runs.get(selected)
        if handle is None:
            if self._query_storage is None:
                raise ValueError(
                    f"run is not managed by this application: {selected}"
                )
            return self._query_storage.read_run(selected)
        if (
            isinstance(handle.resolved.config.storage, SqliteStorageConfig)
            and handle.task.done()
        ):
            with SQLiteStorage(handle.resolved.config.storage.path) as storage:
                return storage.read_run(selected)
        return handle.simulation.storage.read_run(selected)

    def read_agents(
        self, run_id: RunId | str
    ) -> tuple[ResolvedAgentInspection, ...]:
        stored = self.read_run(run_id)
        if stored is None:
            return ()
        scenario = thaw_json(stored.scenario)
        if not isinstance(scenario, dict):
            raise TypeError("stored scenario must be an object")
        scenario.pop("active_agent_ids", None)
        scenario.pop("expanded_agents", None)
        config = ScenarioConfig.model_validate(scenario)
        return inspect_resolved_agents(config)

    def read_snapshot(self, run_id: RunId | str) -> SimulationSnapshot | None:
        selected = RunId(str(run_id))
        handle = self._runs.get(selected)
        if handle is None:
            if self._query_storage is None:
                raise ValueError(
                    f"run is not managed by this application: {selected}"
                )
            checkpoint = self._query_storage.load_latest(selected)
            return checkpoint.snapshot if checkpoint is not None else None
        if (
            isinstance(handle.resolved.config.storage, SqliteStorageConfig)
            and handle.task.done()
        ):
            with SQLiteStorage(handle.resolved.config.storage.path) as storage:
                checkpoint = storage.load_latest(selected)
        else:
            checkpoint = handle.simulation.storage.load_latest(selected)
        return checkpoint.snapshot if checkpoint is not None else None

    def read_events(self, run_id: RunId | str, *, after: int = 0) -> tuple[Event, ...]:
        selected = RunId(str(run_id))
        handle = self._runs.get(selected)
        if handle is None:
            if self._query_storage is None:
                raise ValueError(
                    f"run is not managed by this application: {selected}"
                )
            return tuple(self._query_storage.read_events(selected, after=after))
        if (
            isinstance(handle.resolved.config.storage, SqliteStorageConfig)
            and handle.task.done()
        ):
            with SQLiteStorage(handle.resolved.config.storage.path) as storage:
                return tuple(storage.read_events(selected, after=after))
        return tuple(handle.simulation.storage.read_events(selected, after=after))

    def _require_run(self, run_id: RunId | str) -> ApplicationRun:
        selected = RunId(str(run_id))
        try:
            return self._runs[selected]
        except KeyError as error:
            raise ValueError(
                f"run is not managed by this application: {selected}"
            ) from error

    @staticmethod
    async def _execute(
        simulation: ComposedSimulation,
        config: ScenarioConfig,
        stop_requested: StopEvent,
        *,
        continuous: bool,
        tick_seconds: float,
    ) -> SimulationSnapshot:
        try:
            if continuous:
                continuous_result = await ContinuousRunner(
                    simulation.engine,
                    tick_seconds=tick_seconds,
                    should_stop=stop_requested.is_set,
                ).run()
                return continuous_result.snapshot
            bounded_result = await simulation.engine.run(
                RunLimit(ticks=config.run.ticks)
            )
            return bounded_result.snapshot
        except asyncio.CancelledError:
            return simulation.engine.snapshot()
        finally:
            await simulation.close()


def inspect_resolved_agents(
    config: ScenarioConfig,
) -> tuple[ResolvedAgentInspection, ...]:
    """Project complete resolved configuration without composing a run."""

    inspections: list[ResolvedAgentInspection] = []
    for agent in config.expand_agents():
        profile = config.profiles.get(agent.profile_ref) if agent.profile_ref else None
        configuration: dict[str, object] = agent.model_dump(
            mode="json", exclude_none=True
        )
        if profile is not None:
            configuration["profile"] = profile.model_dump(
                mode="json", exclude_none=True
            )
        public: dict[str, object] = {"id": agent.id}
        if profile is not None:
            if profile.identity is not None:
                public["identity"] = profile.identity.model_dump(
                    mode="json", exclude_none=True
                )
            visibility = profile.visibility
            if visibility.status == "public" and profile.social_status is not None:
                public["social_status"] = profile.social_status.model_dump(
                    mode="json", exclude_none=True
                )
            if visibility.reputation == "public" and profile.reputation is not None:
                public["reputation"] = profile.reputation.model_dump(
                    mode="json", exclude_none=True
                )
            if visibility.relationships == "public" and profile.relationships:
                public["relationships"] = {
                    key: value.model_dump(mode="json", exclude_none=True)
                    for key, value in profile.relationships.items()
                }
            economics: dict[str, object] = {}
            if profile.economics is not None:
                if visibility.wealth == "public":
                    if profile.economics.money is not None:
                        economics["money"] = profile.economics.money
                    if profile.economics.recurring_income is not None:
                        economics["recurring_income"] = (
                            profile.economics.recurring_income
                        )
                if visibility.possessions == "public" and profile.economics.resources:
                    economics["resources"] = dict(profile.economics.resources)
                if visibility.occupation == "public" and profile.economics.occupation:
                    economics["occupation"] = profile.economics.occupation
            if economics:
                public["economics"] = economics
        model = config.models[agent.model_ref]
        inspections.append(
            ResolvedAgentInspection(
                agent_id=agent.id,
                model_ref=agent.model_ref,
                model=model.model,
                configuration=freeze_object(configuration),
                public=freeze_object(public),
            )
        )
    return tuple(inspections)
