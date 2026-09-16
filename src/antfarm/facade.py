"""Transport-neutral application facade at the composition boundary."""

from __future__ import annotations

import asyncio
import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from threading import Event as StopEvent

from antfarm.adapters.storage import SQLiteStorage
from antfarm.application.continuous import ContinuousRunner, PacingClock
from antfarm.application.contracts import (
    AgentDraftView,
    AgentPage,
    AgentQuery,
    ApplicationError,
    EntityPage,
    EntityQuery,
    ErrorCode,
    EventPage,
    EventQuery,
    EventView,
    LocalModelsView,
    ModeView,
    ReplayPage,
    ReplayQuery,
    RunComparisonView,
    RunHistoryItem,
    RunHistoryPage,
    RunHistoryQuery,
    RunMode,
    RunState,
    RunStatus,
    RunView,
    SnapshotView,
)
from antfarm.application.modes import BuiltInModeRegistry
from antfarm.application.replay import ReplayResult, json_deltas, replay_events
from antfarm.composition import ComposedSimulation, build_environment, compose
from antfarm.config import load_scenario
from antfarm.config.schema import ScenarioConfig, SqliteStorageConfig, StorageConfig
from antfarm.custom.generation import (
    CustomGenerationService,
    GenerateCustomDefinitionCommand,
    GeneratedCustomDefinition,
)
from antfarm.custom.runtime import DeclarativeEnvironment, compose_custom
from antfarm.custom.schema import (
    CustomRunConfig,
    CustomSimulationDefinition,
    load_custom_definition,
)
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
from antfarm.domain.protocols import Environment
from antfarm.population import (
    RuntimeOverrides,
    resolve_run_config,
    runtime_overrides_data,
)
from antfarm.population_builder import generate_agent_drafts, scenario_agent_drafts
from antfarm.ports.events import Subscription
from antfarm.ports.generation import CustomDefinitionGenerator
from antfarm.ports.models import ModelInventory, ModelProvider
from antfarm.ports.storage import Storage

EventViewHandler = Callable[[EventView], None]


@dataclass(frozen=True, slots=True)
class ResolvedRunConfiguration:
    """A complete scenario paired with the runtime choices that produced it."""

    config: ScenarioConfig
    runtime_overrides: JsonObject


@dataclass(frozen=True, slots=True)
class ResolvedCustomDefinition:
    """A complete custom definition paired with ephemeral runtime choices."""

    definition: CustomSimulationDefinition
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
class ResolvedEntityInspection:
    """Generic custom-entity view without Society/model assumptions."""

    entity_id: str
    entity_type: str
    behavior: str | None
    configuration: JsonObject
    public: JsonObject


@dataclass(frozen=True, slots=True)
class StartRunCommand:
    resolved: (
        ResolvedRunConfiguration
        | ResolvedCustomDefinition
        | ScenarioConfig
        | CustomSimulationDefinition
    )
    mode: RunMode = RunMode.BOUNDED
    tick_seconds: float = 1.0


@dataclass(frozen=True, slots=True)
class StopRunCommand:
    run_id: str


@dataclass(slots=True)
class ApplicationRun:
    run_id: RunId
    resolved: ResolvedRunConfiguration | ResolvedCustomDefinition
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
        custom_model_providers: Mapping[str, ModelProvider] | None = None,
        custom_definition_generator: CustomDefinitionGenerator | None = None,
        model_inventory: ModelInventory | None = None,
    ) -> None:
        self._runs: dict[RunId, ApplicationRun] = {}
        self._query_storage = storage
        self._modes = modes or BuiltInModeRegistry()
        self._custom_model_providers = dict(custom_model_providers or {})
        self._model_inventory = model_inventory
        self._custom_generation = (
            CustomGenerationService(custom_definition_generator)
            if custom_definition_generator is not None
            else None
        )

    def list_modes(self) -> tuple[ModeView, ...]:
        """Enumerate the closed set of curated simulation modes."""

        return self._modes.list()

    def get_mode(self, mode_id: str) -> ModeView:
        """Return one mode or raise the stable not-found application error."""

        return self._modes.get(mode_id)

    def mode_template_source(self, mode_id: str, template_id: str) -> str:
        """Resolve a registered template to its server-owned scenario resource."""

        return self._modes.template_source(mode_id, template_id)

    async def discover_local_models(self) -> LocalModelsView:
        if self._model_inventory is None:
            return LocalModelsView(
                runtime="unconfigured",
                connected=False,
                models=(),
                error="local model discovery is not configured",
            )
        try:
            models = tuple(await self._model_inventory.list_installed())
        except Exception:
            return LocalModelsView(
                runtime=self._model_inventory.runtime,
                connected=False,
                models=(),
                error="local model runtime is unavailable",
            )
        return LocalModelsView(
            runtime=self._model_inventory.runtime,
            connected=True,
            models=tuple(sorted(dict.fromkeys(models))),
        )

    def scenario_agent_drafts(
        self, config: ScenarioConfig
    ) -> tuple[AgentDraftView, ...]:
        return scenario_agent_drafts(config)

    def generate_agent_drafts(
        self, *, count: int, seed: int, model: str
    ) -> tuple[AgentDraftView, ...]:
        return generate_agent_drafts(count=count, seed=seed, model=model)

    def resolve_custom(
        self,
        source: CustomSimulationDefinition,
        *,
        run_id: str | None = None,
        seed: int | None = None,
    ) -> ResolvedCustomDefinition:
        """Apply ephemeral run choices without mutating a custom definition."""

        updates: dict[str, object] = {}
        if run_id is not None:
            updates["id"] = run_id
        if seed is not None:
            updates["seed"] = seed
        try:
            run_data = source.run.model_dump(mode="json")
            run_data.update(updates)
            run = CustomRunConfig.model_validate(run_data)
            definition_data = source.model_dump(mode="json")
            definition_data["run"] = run.model_dump(mode="json")
            definition = CustomSimulationDefinition.model_validate(definition_data)
            return ResolvedCustomDefinition(
                definition=definition,
                runtime_overrides=freeze_object(updates),
            )
        except ValueError as error:
            raise ApplicationError(
                ErrorCode.INVALID_ARGUMENT,
                f"custom runtime overrides are invalid: {error}",
            ) from error

    async def generate_custom_definition(
        self, description: str
    ) -> GeneratedCustomDefinition:
        if self._custom_generation is None:
            raise ApplicationError(
                ErrorCode.INVALID_STATE,
                "custom definition generation is not configured",
            )
        return await self._custom_generation.generate(
            GenerateCustomDefinitionCommand(description)
        )

    async def close(self) -> None:
        if self._custom_generation is not None:
            await self._custom_generation.close()

    def inspect_resolved_entities(
        self,
        resolved: ResolvedCustomDefinition | CustomSimulationDefinition,
    ) -> tuple[ResolvedEntityInspection, ...]:
        definition = (
            resolved.definition
            if isinstance(resolved, ResolvedCustomDefinition)
            else resolved
        )
        return inspect_custom_entities(definition)

    def load_scenario(self, path: str | Path) -> ScenarioConfig:
        try:
            return load_scenario(path)
        except Exception as error:
            raise ApplicationError(
                ErrorCode.INVALID_SCENARIO,
                f"scenario could not be loaded: {error}",
                details={"error_type": type(error).__name__},
            ) from error

    def load_custom_definition(
        self, path: str | Path
    ) -> CustomSimulationDefinition:
        try:
            return load_custom_definition(path)
        except Exception as error:
            raise ApplicationError(
                ErrorCode.INVALID_SCENARIO,
                f"custom definition could not be loaded: {error}",
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
        resolved: (
            ResolvedRunConfiguration
            | ResolvedCustomDefinition
            | ScenarioConfig
            | CustomSimulationDefinition
        ),
        *,
        continuous: bool = False,
        tick_seconds: float = 1.0,
        on_batch: Callable[[Sequence[Event]], None] | None = None,
        clock: PacingClock | None = None,
        should_stop: Callable[[], bool] | None = None,
        on_waiting: Callable[[Tick, float], None] | None = None,
        on_cognition_started: Callable[[Tick, AgentId, str], None] | None = None,
    ) -> ApplicationRun:
        if isinstance(resolved, ScenarioConfig):
            selected: ResolvedRunConfiguration | ResolvedCustomDefinition = (
                ResolvedRunConfiguration(resolved, freeze_object({}))
            )
        elif isinstance(resolved, CustomSimulationDefinition):
            selected = ResolvedCustomDefinition(resolved, freeze_object({}))
        else:
            selected = resolved
        if isinstance(selected, ResolvedRunConfiguration):
            run_id = RunId(selected.config.run.id)
            ticks = selected.config.run.ticks
        else:
            run_id = RunId(selected.definition.run.id)
            ticks = selected.definition.run.ticks
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
        if isinstance(selected, ResolvedRunConfiguration):
            simulation = compose(
                selected.config,
                on_cognition_started=on_cognition_started,
                runtime_overrides=selected.runtime_overrides,
            )
        else:
            simulation = compose_custom(
                selected.definition,
                model_providers=self._custom_model_providers,
                runtime_overrides=selected.runtime_overrides,
            )
        stop_requested = StopEvent()
        task = asyncio.create_task(
            self._execute(
                simulation,
                ticks,
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

    def query_entities(
        self, query: EntityQuery
    ) -> EntityPage[ResolvedEntityInspection]:
        self.query_run(query.run_id)
        entities = self.read_entities(query.run_id)
        end = query.offset + query.limit
        items = entities[query.offset:end]
        next_offset = end if end < len(entities) else None
        return EntityPage(items=items, next_offset=next_offset)

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

    def query_run_history(self, query: RunHistoryQuery) -> RunHistoryPage:
        stored: dict[str, StoredRun] = {}
        for run_id in self._runs:
            run = self.read_run(run_id)
            if run is not None:
                stored[str(run_id)] = run
        if self._query_storage is not None:
            for run in self._query_storage.list_runs(
                offset=0, limit=query.offset + query.limit + 1
            ):
                stored.setdefault(str(run.metadata.run_id), run)
        ordered = sorted(stored.values(), key=lambda run: str(run.metadata.run_id))
        selected = ordered[query.offset : query.offset + query.limit + 1]
        has_more = len(selected) > query.limit
        items = tuple(self._history_item(run) for run in selected[: query.limit])
        return RunHistoryPage(
            items=items,
            next_offset=(query.offset + query.limit if has_more else None),
        )

    def query_replay(self, query: ReplayQuery) -> ReplayPage:
        result = self._replay(query.run_id)
        end = query.offset + query.limit
        items = result.frames[query.offset:end]
        return ReplayPage(
            run_id=query.run_id,
            items=items,
            next_offset=end if end < len(result.frames) else None,
            final_state_verified=True,
        )

    def compare_runs(
        self, baseline_run_id: str, candidate_run_id: str
    ) -> RunComparisonView:
        baseline_run = self.query_run(baseline_run_id)
        candidate_run = self.query_run(candidate_run_id)
        incompatible = _compatibility_differences(
            baseline_run.scenario, candidate_run.scenario
        )
        baseline = self._replay(baseline_run_id)
        candidate = self._replay(candidate_run_id)
        return RunComparisonView(
            baseline_run_id=baseline_run_id,
            candidate_run_id=candidate_run_id,
            compatible=not incompatible,
            incompatible_fields=tuple(incompatible),
            tick_delta=len(candidate.frames) - len(baseline.frames),
            metric_deltas=json_deltas(
                baseline.final_metrics, candidate.final_metrics
            ),
            state_deltas=json_deltas(baseline.final_world, candidate.final_world),
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

    def _replay(self, run_id: RunId | str) -> ReplayResult:
        stored = self.read_run(run_id)
        checkpoint = self.read_snapshot(run_id)
        if stored is None or checkpoint is None:
            raise ApplicationError(
                ErrorCode.NOT_FOUND,
                f"completed run data was not found: {run_id}",
            )
        raw = thaw_json(stored.scenario)
        if not isinstance(raw, dict):
            raise ApplicationError(
                ErrorCode.INVALID_STATE, "stored scenario is invalid"
            )
        raw.pop("active_agent_ids", None)
        raw.pop("expanded_agents", None)
        try:
            environment: Environment
            if raw.get("kind") == "custom":
                environment = DeclarativeEnvironment(
                    CustomSimulationDefinition.model_validate(raw)
                )
            else:
                environment = build_environment(ScenarioConfig.model_validate(raw))
            return replay_events(
                environment=environment,
                seed=stored.metadata.seed,
                events=self.read_events(run_id),
                checkpoint=checkpoint,
            )
        except ApplicationError:
            raise
        except (TypeError, ValueError) as error:
            raise ApplicationError(
                ErrorCode.INVALID_STATE,
                "stored run is incompatible with replay",
                details={"error_type": type(error).__name__},
            ) from error

    def _history_item(self, stored: StoredRun) -> RunHistoryItem:
        run_id = stored.metadata.run_id
        handle = self._runs.get(run_id)
        checkpoint = self.read_snapshot(run_id)
        tick = 0 if checkpoint is None else int(checkpoint.tick)
        raw_kind = stored.scenario.get("kind")
        kind = raw_kind if isinstance(raw_kind, str) else "society"
        if handle is not None:
            state = self.read_run_state(run_id)
            status = state.status
        else:
            target = _scenario_ticks(stored.scenario)
            status = (
                RunStatus.COMPLETED
                if target is not None and tick >= target
                else RunStatus.STOPPED
            )
        return RunHistoryItem(
            run_id=str(run_id),
            seed=stored.metadata.seed,
            kind=kind,
            status=status,
            tick=tick,
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
            isinstance(_resolved_storage(handle.resolved), SqliteStorageConfig)
            and handle.task.done()
        ):
            storage_config = _resolved_storage(handle.resolved)
            if not isinstance(storage_config, SqliteStorageConfig):
                raise RuntimeError("resolved SQLite storage changed unexpectedly")
            with SQLiteStorage(storage_config.path) as storage:
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
        if scenario.get("kind") == "custom":
            definition = CustomSimulationDefinition.model_validate(scenario)
            return tuple(
                _entity_as_agent(entity)
                for entity in inspect_custom_entities(definition)
            )
        config = ScenarioConfig.model_validate(scenario)
        return inspect_resolved_agents(config)

    def read_entities(
        self, run_id: RunId | str
    ) -> tuple[ResolvedEntityInspection, ...]:
        stored = self.read_run(run_id)
        if stored is None:
            return ()
        raw = thaw_json(stored.scenario)
        if not isinstance(raw, dict) or raw.get("kind") != "custom":
            raise ApplicationError(
                ErrorCode.INVALID_ARGUMENT,
                "run does not contain a custom simulation definition",
                details={"run_id": str(run_id)},
            )
        return inspect_custom_entities(CustomSimulationDefinition.model_validate(raw))

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
            isinstance(_resolved_storage(handle.resolved), SqliteStorageConfig)
            and handle.task.done()
        ):
            storage_config = _resolved_storage(handle.resolved)
            if not isinstance(storage_config, SqliteStorageConfig):
                raise RuntimeError("resolved SQLite storage changed unexpectedly")
            with SQLiteStorage(storage_config.path) as storage:
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
            isinstance(_resolved_storage(handle.resolved), SqliteStorageConfig)
            and handle.task.done()
        ):
            storage_config = _resolved_storage(handle.resolved)
            if not isinstance(storage_config, SqliteStorageConfig):
                raise RuntimeError("resolved SQLite storage changed unexpectedly")
            with SQLiteStorage(storage_config.path) as storage:
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
            isinstance(_resolved_storage(handle.resolved), SqliteStorageConfig)
            and handle.task.done()
        ):
            storage_config = _resolved_storage(handle.resolved)
            if not isinstance(storage_config, SqliteStorageConfig):
                raise RuntimeError("resolved SQLite storage changed unexpectedly")
            with SQLiteStorage(storage_config.path) as storage:
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
        ticks: int,
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
            bounded_result = await simulation.engine.run(RunLimit(ticks=ticks))
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


def inspect_custom_entities(
    definition: CustomSimulationDefinition,
) -> tuple[ResolvedEntityInspection, ...]:
    """Project custom entities without treating their fields as Society data."""

    inspections: list[ResolvedEntityInspection] = []
    for entity in definition.entities:
        entity_type = definition.entity_types[entity.type]
        public_state = {
            name: value
            for name, value in entity.state.items()
            if entity_type.fields[name].visibility == "public"
        }
        behavior = entity.behavior
        behavior_kind = (
            None if behavior is None else behavior.kind
        )
        inspections.append(
            ResolvedEntityInspection(
                entity_id=entity.id,
                entity_type=entity.type,
                behavior=behavior_kind,
                configuration=freeze_object(
                    entity.model_dump(mode="json", exclude_none=True)
                ),
                public=freeze_object(
                    {"id": entity.id, "type": entity.type, "state": public_state}
                ),
            )
        )
    return tuple(inspections)


def _entity_as_agent(entity: ResolvedEntityInspection) -> ResolvedAgentInspection:
    behavior = entity.behavior or "inert"
    return ResolvedAgentInspection(
        agent_id=entity.entity_id,
        model_ref=behavior,
        model=behavior,
        configuration=entity.configuration,
        public=entity.public,
    )


def _scenario_ticks(scenario: Mapping[str, object]) -> int | None:
    run = scenario.get("run")
    if not isinstance(run, Mapping):
        return None
    ticks = run.get("ticks")
    return ticks if isinstance(ticks, int) and not isinstance(ticks, bool) else None


def _compatibility_differences(
    baseline: Mapping[str, object], candidate: Mapping[str, object]
) -> list[str]:
    differences: list[str] = []
    baseline_custom = baseline.get("kind") == "custom"
    candidate_custom = candidate.get("kind") == "custom"
    if baseline_custom != candidate_custom:
        return ["kind"]
    if baseline.get("schema_version") != candidate.get("schema_version"):
        differences.append("schema_version")
    if baseline_custom:
        for field in ("world_fields", "entity_types", "actions"):
            if baseline.get(field) != candidate.get(field):
                differences.append(field)
    else:
        baseline_environment = baseline.get("environment")
        candidate_environment = candidate.get("environment")
        if _mapping_value(baseline_environment, "kind") != _mapping_value(
            candidate_environment, "kind"
        ):
            differences.append("environment.kind")
        if _action_kinds(baseline.get("actions")) != _action_kinds(
            candidate.get("actions")
        ):
            differences.append("actions")
    return differences


def _mapping_value(value: object, key: str) -> object:
    return value.get(key) if isinstance(value, Mapping) else None


def _action_kinds(value: object) -> frozenset[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return frozenset()
    return frozenset(
        str(kind)
        for item in value
        if isinstance(item, Mapping)
        and isinstance((kind := item.get("kind")), str)
    )


def _resolved_storage(
    resolved: ResolvedRunConfiguration | ResolvedCustomDefinition,
) -> StorageConfig:
    if isinstance(resolved, ResolvedRunConfiguration):
        return resolved.config.storage
    return resolved.definition.storage
