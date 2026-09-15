"""Transport-neutral application facade at the composition boundary."""

from __future__ import annotations

import asyncio
import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from threading import Event as StopEvent

from antfarm.adapters.storage import SQLiteStorage
from antfarm.application.continuous import ContinuousRunner, PacingClock
from antfarm.application.contracts import (
    AgentPage,
    AgentQuery,
    ApplicationError,
    ErrorCode,
    EventPage,
    EventQuery,
    EventView,
    ModeView,
    RunMode,
    RunState,
    RunStatus,
    RunView,
    SnapshotView,
)
from antfarm.application.modes import BuiltInModeRegistry
from antfarm.composition import ComposedSimulation, compose
from antfarm.config import load_scenario
from antfarm.config.schema import ScenarioConfig, SqliteStorageConfig
from antfarm.domain.json_values import JsonObject, freeze_object, thaw_json
from antfarm.domain.models import (
    AgentId,
    Event,
    RunId,
    RunLimit,
    SimulationSnapshot,
    StoredRun,
    Tick,
)
from antfarm.population import (
    RuntimeOverrides,
    resolve_run_config,
    runtime_overrides_data,
)
from antfarm.ports.events import Subscription
from antfarm.ports.storage import Storage

EventViewHandler = Callable[[EventView], None]


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


@dataclass(frozen=True, slots=True)
class StartRunCommand:
    resolved: ResolvedRunConfiguration | ScenarioConfig
    mode: RunMode = RunMode.BOUNDED
    tick_seconds: float = 1.0


@dataclass(frozen=True, slots=True)
class StopRunCommand:
    run_id: str


@dataclass(slots=True)
class ApplicationRun:
    run_id: RunId
    resolved: ResolvedRunConfiguration
    simulation: ComposedSimulation
    stop_requested: StopEvent
    task: asyncio.Task[SimulationSnapshot]
    mode: RunMode = RunMode.BOUNDED
    status: RunStatus = RunStatus.RUNNING
    failure: ErrorCode | None = None


class AntFarmApplication:
    """Shared application entry point for CLI, tests, and future transports."""

    def __init__(
        self,
        storage: Storage | None = None,
        *,
        modes: BuiltInModeRegistry | None = None,
    ) -> None:
        self._runs: dict[RunId, ApplicationRun] = {}
        self._query_storage = storage
        self._modes = modes or BuiltInModeRegistry()

    def list_modes(self) -> tuple[ModeView, ...]:
        """Enumerate the closed set of curated simulation modes."""

        return self._modes.list()

    def get_mode(self, mode_id: str) -> ModeView:
        """Return one mode or raise the stable not-found application error."""

        return self._modes.get(mode_id)

    def mode_template_source(self, mode_id: str, template_id: str) -> str:
        """Resolve a registered template to its server-owned scenario resource."""

        return self._modes.template_source(mode_id, template_id)

    def load_scenario(self, path: str | Path) -> ScenarioConfig:
        try:
            return load_scenario(path)
        except Exception as error:
            raise ApplicationError(
                ErrorCode.INVALID_SCENARIO,
                f"scenario could not be loaded: {error}",
                details={"error_type": type(error).__name__},
            ) from error

    def resolve_population(
        self,
        source: ScenarioConfig,
        overrides: RuntimeOverrides | None = None,
    ) -> ResolvedRunConfiguration:
        try:
            return ResolvedRunConfiguration(
                config=resolve_run_config(source, overrides),
                runtime_overrides=runtime_overrides_data(overrides),
            )
        except ValueError as error:
            raise ApplicationError(
                ErrorCode.INVALID_ARGUMENT,
                f"runtime overrides are invalid: {error}",
                details={"error_type": type(error).__name__},
            ) from error

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
        on_batch: Callable[[Sequence[Event]], None] | None = None,
        clock: PacingClock | None = None,
        should_stop: Callable[[], bool] | None = None,
        on_waiting: Callable[[Tick, float], None] | None = None,
        on_cognition_started: Callable[[Tick, AgentId, str], None] | None = None,
    ) -> ApplicationRun:
        selected = (
            resolved
            if isinstance(resolved, ResolvedRunConfiguration)
            else ResolvedRunConfiguration(resolved, freeze_object({}))
        )
        run_id = RunId(selected.config.run.id)
        if run_id in self._runs:
            raise ApplicationError(
                ErrorCode.CONFLICT,
                f"run is already managed: {run_id}",
                details={"run_id": str(run_id)},
            )
        if not math.isfinite(tick_seconds) or tick_seconds <= 0:
            raise ApplicationError(
                ErrorCode.INVALID_ARGUMENT,
                "tick_seconds must be a finite positive number",
            )
        simulation = compose(
            selected.config,
            on_cognition_started=on_cognition_started,
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
                on_batch=on_batch,
                clock=clock,
                should_stop=should_stop,
                on_waiting=on_waiting,
            )
        )
        handle = ApplicationRun(
            run_id=run_id,
            resolved=selected,
            simulation=simulation,
            stop_requested=stop_requested,
            task=task,
            mode=RunMode.CONTINUOUS if continuous else RunMode.BOUNDED,
        )
        self._runs[run_id] = handle
        task.add_done_callback(
            lambda completed: self._record_completion(handle, completed)
        )
        return handle

    def start(self, command: StartRunCommand) -> RunState:
        """Start a run through the stable command surface."""

        handle = self.start_run(
            command.resolved,
            continuous=command.mode is RunMode.CONTINUOUS,
            tick_seconds=command.tick_seconds,
        )
        return self.read_run_state(handle.run_id)

    async def wait_run(self, run_id: RunId | str) -> SimulationSnapshot:
        handle = self._require_run(run_id)
        snapshot = await handle.task
        if handle.status is RunStatus.RUNNING:
            handle.status = (
                RunStatus.STOPPED
                if handle.mode is RunMode.CONTINUOUS
                else RunStatus.COMPLETED
            )
        return snapshot

    async def stop_run(self, run_id: RunId | str) -> SimulationSnapshot:
        handle = self._require_run(run_id)
        if handle.status in {RunStatus.COMPLETED, RunStatus.STOPPED, RunStatus.FAILED}:
            raise ApplicationError(
                ErrorCode.INVALID_STATE,
                f"run cannot be stopped from state {handle.status}: {handle.run_id}",
            )
        handle.status = RunStatus.STOPPING
        handle.stop_requested.set()
        if not handle.task.done():
            handle.task.cancel()
        snapshot = await handle.task
        handle.status = RunStatus.STOPPED
        return snapshot

    async def stop(self, command: StopRunCommand) -> RunState:
        """Stop a continuous run and return its last atomic lifecycle state."""

        await self.stop_run(command.run_id)
        return self.read_run_state(command.run_id)

    def read_run_state(self, run_id: RunId | str) -> RunState:
        handle = self._require_run(run_id)
        if handle.task.done() and handle.status is RunStatus.RUNNING:
            self._record_completion(handle, handle.task)
        return RunState(
            run_id=str(handle.run_id),
            mode=handle.mode,
            status=handle.status,
            tick=int(handle.simulation.engine.snapshot().tick),
            failure=handle.failure,
        )

    def query_run(self, run_id: RunId | str) -> RunView:
        selected = RunId(str(run_id))
        try:
            stored = self.read_run(selected)
        except ValueError as error:
            raise ApplicationError(
                ErrorCode.NOT_FOUND,
                f"run was not found: {selected}",
                details={"run_id": str(selected)},
            ) from error
        if stored is None:
            raise ApplicationError(
                ErrorCode.NOT_FOUND,
                f"run was not found: {selected}",
                details={"run_id": str(selected)},
            )
        return RunView(
            run_id=str(stored.metadata.run_id),
            seed=stored.metadata.seed,
            runtime_overrides=stored.metadata.runtime_overrides,
            scenario=stored.scenario,
        )

    def query_agents(self, query: AgentQuery) -> AgentPage[ResolvedAgentInspection]:
        self.query_run(query.run_id)
        agents = self.read_agents(query.run_id)
        end = query.offset + query.limit
        items = agents[query.offset:end]
        next_offset = end if end < len(agents) else None
        return AgentPage(items=items, next_offset=next_offset)

    def query_snapshot(self, run_id: RunId | str) -> SnapshotView | None:
        self.query_run(run_id)
        snapshot = self.read_snapshot(run_id)
        if snapshot is None:
            return None
        return SnapshotView(
            run_id=str(run_id),
            tick=int(snapshot.tick),
            world=snapshot.world,
            metrics=snapshot.metrics,
        )

    def query_events(self, query: EventQuery) -> EventPage:
        self.query_run(query.run_id)
        events = self._read_filtered_events(query, limit=query.limit + 1)
        has_more = len(events) > query.limit
        selected = events[: query.limit]
        return EventPage(
            items=tuple(event_view(event) for event in selected),
            next_after=(int(selected[-1].sequence) if has_more and selected else None),
        )

    def subscribe_events(
        self,
        run_id: RunId | str,
        kinds: set[str],
        handler: EventViewHandler,
    ) -> Subscription:
        handle = self._require_run(run_id)
        if not kinds or any(not kind for kind in kinds):
            raise ApplicationError(
                ErrorCode.INVALID_ARGUMENT,
                "at least one non-empty event kind is required",
            )
        return handle.simulation.event_bus.subscribe(
            kinds, lambda event: handler(event_view(event))
        )

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

    def _read_filtered_events(
        self, query: EventQuery, *, limit: int
    ) -> tuple[Event, ...]:
        selected = RunId(query.run_id)
        handle = self._runs.get(selected)
        if handle is None:
            if self._query_storage is None:
                raise ApplicationError(
                    ErrorCode.NOT_FOUND,
                    f"run is not managed by this application: {selected}",
                )
            return tuple(
                self._query_storage.read_events(
                    selected,
                    after=query.after,
                    limit=limit,
                    kinds=query.kinds,
                    actor_id=query.actor_id,
                    from_tick=query.from_tick,
                    to_tick=query.to_tick,
                )
            )
        if (
            isinstance(handle.resolved.config.storage, SqliteStorageConfig)
            and handle.task.done()
        ):
            with SQLiteStorage(handle.resolved.config.storage.path) as storage:
                return tuple(
                    storage.read_events(
                        selected,
                        after=query.after,
                        limit=limit,
                        kinds=query.kinds,
                        actor_id=query.actor_id,
                        from_tick=query.from_tick,
                        to_tick=query.to_tick,
                    )
                )
        return tuple(
            handle.simulation.storage.read_events(
                selected,
                after=query.after,
                limit=limit,
                kinds=query.kinds,
                actor_id=query.actor_id,
                from_tick=query.from_tick,
                to_tick=query.to_tick,
            )
        )

    def _require_run(self, run_id: RunId | str) -> ApplicationRun:
        selected = RunId(str(run_id))
        try:
            return self._runs[selected]
        except KeyError as error:
            raise ApplicationError(
                ErrorCode.NOT_FOUND,
                f"run is not managed by this application: {selected}"
            ) from error

    @staticmethod
    def _record_completion(
        handle: ApplicationRun, task: asyncio.Task[SimulationSnapshot]
    ) -> None:
        if task.cancelled():
            handle.status = RunStatus.STOPPED
            return
        if task.exception() is not None:
            handle.status = RunStatus.FAILED
            handle.failure = ErrorCode.EXECUTION_FAILED
            return
        handle.status = (
            RunStatus.STOPPED
            if handle.status is RunStatus.STOPPING
            or handle.mode is RunMode.CONTINUOUS
            else RunStatus.COMPLETED
        )

    @staticmethod
    async def _execute(
        simulation: ComposedSimulation,
        config: ScenarioConfig,
        stop_requested: StopEvent,
        *,
        continuous: bool,
        tick_seconds: float,
        on_batch: Callable[[Sequence[Event]], None] | None,
        clock: PacingClock | None,
        should_stop: Callable[[], bool] | None,
        on_waiting: Callable[[Tick, float], None] | None,
    ) -> SimulationSnapshot:
        try:
            if continuous:
                continuous_result = await ContinuousRunner(
                    simulation.engine,
                    tick_seconds=tick_seconds,
                    on_batch=on_batch,
                    clock=clock,
                    should_stop=(
                        lambda: stop_requested.is_set()
                        or (should_stop is not None and should_stop())
                    ),
                    on_waiting=on_waiting,
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


def event_view(event: Event) -> EventView:
    """Project an internal domain event into the stable service contract."""

    return EventView(
        schema_version=event.schema_version,
        event_id=event.event_id,
        run_id=str(event.run_id),
        sequence=int(event.sequence),
        tick=int(event.tick),
        kind=event.kind,
        actor_id=str(event.actor_id) if event.actor_id is not None else None,
        causation_id=event.causation_id,
        payload=event.payload,
    )


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
