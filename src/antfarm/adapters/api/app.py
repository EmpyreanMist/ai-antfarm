"""Versioned FastAPI adapter over the stable M4 application service."""

from __future__ import annotations

import asyncio
import math
import os
from collections.abc import AsyncIterator, Mapping, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated
from uuid import uuid4

from fastapi import FastAPI, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator

from antfarm.adapters.api.catalog import CatalogScenario, ScenarioCatalog
from antfarm.adapters.generation import (
    OpenAICompatibleDefinitionGenerator,
    StaticCustomDefinitionGenerator,
)
from antfarm.adapters.models.ollama import OllamaModelPreflight
from antfarm.adapters.storage import SQLiteStorage
from antfarm.adapters.terminal import VISIBLE_EVENT_KINDS
from antfarm.application.contracts import (
    AgentDraftView,
    AgentQuery,
    ApplicationError,
    EntityQuery,
    ErrorCode,
    EventQuery,
    EventView,
    ModeView,
    ReplayQuery,
    RunHistoryQuery,
    RunMode,
    RunState,
    RunStatus,
)
from antfarm.config.schema import AgentProfileConfig, PopulationConfig
from antfarm.custom.schema import CustomSimulationDefinition, load_custom_definition
from antfarm.domain.json_values import JsonObject, thaw_json
from antfarm.facade import (
    AntFarmApplication,
    ResolvedAgentInspection,
    ResolvedCustomDefinition,
    ResolvedEntityInspection,
    ResolvedRunConfiguration,
    StartRunCommand,
    StopRunCommand,
)
from antfarm.population import RuntimeOverrides, WebAgentDraft
from antfarm.ports.generation import CustomDefinitionGenerator
from antfarm.ports.models import ModelInventory
from antfarm.preflight import preflight_ollama

API_PREFIX = "/api/v1"
ALL_EVENT_KINDS = VISIBLE_EVENT_KINDS | {
    "tick.started",
    "tick.completed",
    "observation.created",
    "proposal.created",
    "action.validated",
}
TERMINAL_STATUSES = {RunStatus.COMPLETED, RunStatus.STOPPED, RunStatus.FAILED}
MAX_RECOVERY_EVENTS = 1_000
DEFAULT_STREAM_BUFFER = 100


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AgentDraftRequest(ApiModel):
    id: Annotated[str, Field(min_length=1, max_length=100)]
    model: Annotated[str | None, Field(min_length=1, max_length=300)] = None
    profile: AgentProfileConfig
    cognition_interval: Annotated[int | None, Field(ge=1)] = None


class ResolveRequest(ApiModel):
    seed: int | None = None
    run_id: str | None = None
    active_agents: Annotated[int | None, Field(ge=1)] = None
    model: str | None = None
    population: PopulationConfig | None = None
    profiles: dict[str, dict[str, object]] = Field(default_factory=dict)
    model_assignments: dict[str, str] = Field(default_factory=dict)
    agents: list[AgentDraftRequest] | None = None


class GeneratePopulationRequest(ApiModel):
    count: Annotated[int, Field(ge=1, le=10)]
    seed: int
    model: Annotated[str, Field(min_length=1, max_length=300)]


class StartRequest(ApiModel):
    resolution_id: str
    mode: RunMode = RunMode.BOUNDED
    tick_seconds: float = 1.0

    @field_validator("tick_seconds")
    @classmethod
    def validate_tick_seconds(cls, value: float) -> float:
        if not math.isfinite(value) or value <= 0:
            raise ValueError("tick_seconds must be a finite positive number")
        return value


class CustomResolveRequest(ApiModel):
    definition: CustomSimulationDefinition
    run_id: str | None = None
    seed: int | None = None


class GenerateCustomRequest(ApiModel):
    description: Annotated[str, Field(min_length=1, max_length=4_000)]


@dataclass(slots=True)
class ApiRuntime:
    application: AntFarmApplication
    catalog: ScenarioCatalog
    resolutions: dict[str, ResolvedRunConfiguration | ResolvedCustomDefinition]
    custom_starter: CustomSimulationDefinition
    run_ids: set[str]
    history_storage: SQLiteStorage | None


def create_app(
    *,
    scenario_directory: str | Path = "scenarios/examples",
    allowed_origins: Sequence[str] = (
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ),
    stream_buffer_size: int = DEFAULT_STREAM_BUFFER,
    custom_definition_generator: CustomDefinitionGenerator | None = None,
    history_database: str | Path | None = None,
    model_inventory: ModelInventory | None = None,
) -> FastAPI:
    """Create the local M5 control-plane API."""

    if stream_buffer_size < 1:
        raise ValueError("stream_buffer_size must be positive")
    scenario_root = Path(scenario_directory)
    custom_starter = load_custom_definition(scenario_root / "custom-warehouse.yaml")
    generator = custom_definition_generator or _configured_generator(custom_starter)
    history_path = history_database or os.environ.get("ANTFARM_HISTORY_DB")
    history_storage = SQLiteStorage(history_path) if history_path else None
    inventory = model_inventory or OllamaModelPreflight(
        base_url=os.environ.get(
            "ANTFARM_OLLAMA_BASE_URL", "http://127.0.0.1:11434/v1"
        ),
        timeout_seconds=2,
    )
    application = AntFarmApplication(
        storage=history_storage,
        custom_definition_generator=generator,
        model_inventory=inventory,
    )
    runtime = ApiRuntime(
        application=application,
        catalog=ScenarioCatalog(scenario_root, application),
        resolutions={},
        custom_starter=custom_starter,
        run_ids=set(),
        history_storage=history_storage,
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        await _stop_active_runs(runtime)
        await runtime.application.close()
        if runtime.history_storage is not None:
            runtime.history_storage.close()

    app = FastAPI(
        title="AntFarm Control API",
        version="1.0.0",
        lifespan=lifespan,
    )
    app.state.antfarm = runtime
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(allowed_origins),
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type"],
    )

    @app.exception_handler(ApplicationError)
    async def application_error_handler(
        _: Request, error: ApplicationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=_error_status(error.code),
            content=_error_content(error.code, error.message, error.details),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        _: Request, error: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=_error_content(
                ErrorCode.INVALID_ARGUMENT,
                "request validation failed",
                {"errors": error.errors()},
            ),
        )

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get(f"{API_PREFIX}/scenarios")
    async def list_scenarios() -> dict[str, object]:
        return {"items": [scenario.view() for scenario in runtime.catalog.list()]}

    @app.get(f"{API_PREFIX}/modes")
    async def list_modes() -> dict[str, object]:
        modes = runtime.application.list_modes()
        return {"items": [_mode_view(mode) for mode in modes]}

    @app.get(f"{API_PREFIX}/modes/{{mode_id}}")
    async def inspect_mode(mode_id: str) -> dict[str, object]:
        return _mode_view(runtime.application.get_mode(mode_id))

    @app.get(f"{API_PREFIX}/modes/{{mode_id}}/scenarios")
    async def list_mode_scenarios(mode_id: str) -> dict[str, object]:
        runtime.application.get_mode(mode_id)
        return {
            "items": [
                scenario.view() for scenario in runtime.catalog.list(mode_id=mode_id)
            ]
        }

    @app.get(f"{API_PREFIX}/runtimes/local-models")
    async def local_models() -> dict[str, object]:
        view = await runtime.application.discover_local_models()
        return {
            "runtime": view.runtime,
            "connected": view.connected,
            "models": list(view.models),
            "error": view.error,
        }

    @app.get(f"{API_PREFIX}/scenarios/{{scenario_id}}/agent-drafts")
    async def get_agent_drafts(scenario_id: str) -> dict[str, object]:
        scenario = _require_scenario(runtime, scenario_id)
        return {
            "items": [
                _agent_draft_view(item)
                for item in runtime.application.scenario_agent_drafts(scenario.config)
            ]
        }

    @app.post(f"{API_PREFIX}/scenarios/{{scenario_id}}/agent-drafts/generate")
    async def generate_population(
        scenario_id: str, request: GeneratePopulationRequest
    ) -> dict[str, object]:
        _require_scenario(runtime, scenario_id)
        return {
            "items": [
                _agent_draft_view(item)
                for item in runtime.application.generate_agent_drafts(
                    count=request.count, seed=request.seed, model=request.model
                )
            ]
        }

    @app.post(f"{API_PREFIX}/scenarios/{{scenario_id}}/resolve")
    async def resolve_scenario(
        scenario_id: str, request: ResolveRequest
    ) -> dict[str, object]:
        scenario = _require_scenario(runtime, scenario_id)
        run_id = request.run_id or _fresh_run_id(scenario.config.run.id)
        resolved = runtime.application.resolve_population(
            scenario.config,
            RuntimeOverrides(
                seed=request.seed,
                run_id=run_id,
                active_agents=request.active_agents,
                population=request.population,
                profiles=request.profiles,
                model_assignments=request.model_assignments,
                model=request.model,
                web_agents=(
                    tuple(
                        WebAgentDraft(
                            id=agent.id,
                            model=agent.model,
                            profile=agent.profile.model_dump(
                                mode="json", exclude_none=True
                            ),
                            cognition_interval=agent.cognition_interval,
                        )
                        for agent in request.agents
                    )
                    if request.agents is not None
                    else None
                ),
            ),
        )
        resolution_id = uuid4().hex
        runtime.resolutions[resolution_id] = resolved
        return _resolution_view(runtime, scenario, resolution_id, resolved)

    @app.get(f"{API_PREFIX}/custom/starter")
    async def get_custom_starter() -> dict[str, object]:
        return runtime.custom_starter.model_dump(mode="json", exclude_none=True)

    @app.post(f"{API_PREFIX}/custom/validate")
    async def validate_custom(
        definition: CustomSimulationDefinition,
    ) -> dict[str, object]:
        _validate_web_custom(definition)
        return _custom_preview(runtime.application, definition)

    @app.post(f"{API_PREFIX}/custom/resolve")
    async def resolve_custom(request: CustomResolveRequest) -> dict[str, object]:
        _validate_web_custom(request.definition)
        resolved = runtime.application.resolve_custom(
            request.definition,
            run_id=request.run_id or _fresh_run_id(request.definition.run.id),
            seed=request.seed,
        )
        resolution_id = uuid4().hex
        runtime.resolutions[resolution_id] = resolved
        return {
            "resolution_id": resolution_id,
            "kind": "custom",
            "run_id": resolved.definition.run.id,
            "seed": resolved.definition.run.seed,
            "ticks": resolved.definition.run.ticks,
            "runtime_overrides": thaw_json(resolved.runtime_overrides),
            **_custom_preview(runtime.application, resolved.definition),
        }

    @app.post(f"{API_PREFIX}/custom/generate")
    async def generate_custom(request: GenerateCustomRequest) -> dict[str, object]:
        generated = await runtime.application.generate_custom_definition(
            request.description
        )
        _validate_web_custom(generated.definition)
        return {
            "definition": generated.definition.model_dump(
                mode="json", exclude_none=True
            ),
            "provenance": thaw_json(generated.provenance),
        }

    @app.post(f"{API_PREFIX}/runs", status_code=201)
    async def start_run(request: StartRequest) -> dict[str, object]:
        resolved = runtime.resolutions.get(request.resolution_id)
        if resolved is None:
            raise ApplicationError(
                ErrorCode.NOT_FOUND,
                "resolved preview was not found or was already used",
                details={"resolution_id": request.resolution_id},
            )
        if isinstance(resolved, ResolvedRunConfiguration):
            try:
                await preflight_ollama(resolved.config)
            except ValueError as error:
                raise ApplicationError(
                    ErrorCode.EXECUTION_FAILED,
                    str(error),
                    details={"runtime": "ollama"},
                ) from error
        state = runtime.application.start(
            StartRunCommand(
                resolved=resolved,
                mode=request.mode,
                tick_seconds=request.tick_seconds,
            )
        )
        runtime.resolutions.pop(request.resolution_id)
        runtime.run_ids.add(state.run_id)
        return _run_state_view(state)

    @app.get(f"{API_PREFIX}/runs")
    async def list_runs(
        offset: Annotated[int, Query(ge=0)] = 0,
        limit: Annotated[int, Query(ge=1, le=1_000)] = 100,
    ) -> dict[str, object]:
        page = runtime.application.query_run_history(
            RunHistoryQuery(offset=offset, limit=limit)
        )
        return {
            "items": [
                {
                    "run_id": item.run_id,
                    "seed": item.seed,
                    "kind": item.kind,
                    "status": item.status.value,
                    "tick": item.tick,
                }
                for item in page.items
            ],
            "next_offset": page.next_offset,
        }

    @app.get(f"{API_PREFIX}/runs/compare")
    async def compare_runs(baseline: str, candidate: str) -> dict[str, object]:
        comparison = runtime.application.compare_runs(baseline, candidate)
        return {
            "baseline_run_id": comparison.baseline_run_id,
            "candidate_run_id": comparison.candidate_run_id,
            "compatible": comparison.compatible,
            "incompatible_fields": list(comparison.incompatible_fields),
            "tick_delta": comparison.tick_delta,
            "metric_deltas": thaw_json(comparison.metric_deltas),
            "state_deltas": thaw_json(comparison.state_deltas),
        }

    @app.get(f"{API_PREFIX}/runs/{{run_id}}/replay")
    async def replay_run(
        run_id: str,
        offset: Annotated[int, Query(ge=0)] = 0,
        limit: Annotated[int, Query(ge=1, le=1_000)] = 100,
    ) -> dict[str, object]:
        page = runtime.application.query_replay(
            ReplayQuery(run_id=run_id, offset=offset, limit=limit)
        )
        return {
            "run_id": page.run_id,
            "items": [
                {
                    "tick": item.tick,
                    "event_sequence": item.event_sequence,
                    "world": thaw_json(item.world),
                    "metrics": thaw_json(item.metrics),
                }
                for item in page.items
            ],
            "next_offset": page.next_offset,
            "final_state_verified": page.final_state_verified,
        }

    @app.get(f"{API_PREFIX}/runs/{{run_id}}/state")
    async def run_state(run_id: str) -> dict[str, object]:
        return _run_state_view(runtime.application.read_run_state(run_id))

    @app.post(f"{API_PREFIX}/runs/{{run_id}}/stop")
    async def stop_run(run_id: str) -> dict[str, object]:
        return _run_state_view(
            await runtime.application.stop(StopRunCommand(run_id))
        )

    @app.get(f"{API_PREFIX}/runs/{{run_id}}")
    async def inspect_run(run_id: str) -> dict[str, object]:
        view = runtime.application.query_run(run_id)
        return {
            "run_id": view.run_id,
            "seed": view.seed,
            "runtime_overrides": thaw_json(view.runtime_overrides),
            "scenario": thaw_json(view.scenario),
        }

    @app.get(f"{API_PREFIX}/runs/{{run_id}}/agents")
    async def inspect_agents(
        run_id: str,
        offset: Annotated[int, Query(ge=0)] = 0,
        limit: Annotated[int, Query(ge=1, le=1_000)] = 100,
    ) -> dict[str, object]:
        page = runtime.application.query_agents(
            AgentQuery(run_id=run_id, offset=offset, limit=limit)
        )
        return {
            "items": [_agent_view(agent) for agent in page.items],
            "next_offset": page.next_offset,
        }

    @app.get(f"{API_PREFIX}/runs/{{run_id}}/entities")
    async def inspect_entities(
        run_id: str,
        offset: Annotated[int, Query(ge=0)] = 0,
        limit: Annotated[int, Query(ge=1, le=1_000)] = 100,
    ) -> dict[str, object]:
        page = runtime.application.query_entities(
            EntityQuery(run_id=run_id, offset=offset, limit=limit)
        )
        return {
            "items": [_entity_view(entity) for entity in page.items],
            "next_offset": page.next_offset,
        }

    @app.get(f"{API_PREFIX}/runs/{{run_id}}/snapshot")
    async def inspect_snapshot(run_id: str) -> dict[str, object] | None:
        view = runtime.application.query_snapshot(run_id)
        if view is None:
            return None
        return {
            "run_id": view.run_id,
            "tick": view.tick,
            "world": thaw_json(view.world),
            "metrics": thaw_json(view.metrics),
        }

    @app.get(f"{API_PREFIX}/runs/{{run_id}}/events")
    async def inspect_events(
        run_id: str,
        after: Annotated[int, Query(ge=0)] = 0,
        limit: Annotated[int, Query(ge=1, le=1_000)] = 100,
        kind: Annotated[list[str] | None, Query()] = None,
        actor_id: str | None = None,
        from_tick: Annotated[int | None, Query(ge=0)] = None,
        to_tick: Annotated[int | None, Query(ge=0)] = None,
    ) -> dict[str, object]:
        page = runtime.application.query_events(
            EventQuery(
                run_id=run_id,
                after=after,
                limit=limit,
                kinds=frozenset(kind or ()),
                actor_id=actor_id,
                from_tick=from_tick,
                to_tick=to_tick,
            )
        )
        return {
            "items": [_event_view(event) for event in page.items],
            "next_after": page.next_after,
        }

    @app.websocket(f"{API_PREFIX}/runs/{{run_id}}/events/stream")
    async def stream_events(
        websocket: WebSocket,
        run_id: str,
        after: int = 0,
        kinds: str | None = None,
    ) -> None:
        await _stream_events(
            runtime,
            websocket,
            run_id,
            after=max(0, after),
            kinds=_stream_kinds(kinds),
            buffer_size=stream_buffer_size,
        )

    return app


def _require_scenario(runtime: ApiRuntime, scenario_id: str) -> CatalogScenario:
    scenario = runtime.catalog.get(scenario_id)
    if scenario is None:
        raise ApplicationError(
            ErrorCode.NOT_FOUND,
            f"scenario was not found: {scenario_id}",
            details={"scenario_id": scenario_id},
        )
    return scenario


def _resolution_view(
    runtime: ApiRuntime,
    scenario: CatalogScenario,
    resolution_id: str,
    resolved: ResolvedRunConfiguration,
) -> dict[str, object]:
    agents = runtime.application.inspect_resolved_agents(resolved)
    return {
        "resolution_id": resolution_id,
        "scenario_id": scenario.template.id,
        "mode": scenario.mode.id,
        "run_id": resolved.config.run.id,
        "seed": resolved.config.run.seed,
        "ticks": resolved.config.run.ticks,
        "active_agent_count": len(resolved.config.active_agents()),
        "runtime_overrides": thaw_json(resolved.runtime_overrides),
        "agents": [_agent_view(agent) for agent in agents],
    }


def _mode_view(mode: ModeView) -> dict[str, object]:
    return {
        "id": mode.id,
        "name": mode.name,
        "description": mode.description,
        "capabilities": list(mode.capabilities),
        "configuration_hints": thaw_json(mode.configuration_hints),
        "visualization_hints": thaw_json(mode.visualization_hints),
        "templates": [
            {
                "id": template.id,
                "name": template.name,
                "description": template.description,
                "runtime": template.runtime,
                "featured": template.featured,
            }
            for template in mode.templates
        ],
    }


def _agent_view(agent: ResolvedAgentInspection) -> dict[str, object]:
    return {
        "agent_id": agent.agent_id,
        "model_ref": agent.model_ref,
        "model": agent.model,
        "configuration": thaw_json(agent.configuration),
        "public": thaw_json(agent.public),
    }


def _agent_draft_view(agent: AgentDraftView) -> dict[str, object]:
    return {
        "id": agent.id,
        "model": agent.model,
        "profile": thaw_json(agent.profile),
        "cognition_interval": agent.cognition_interval,
    }


def _entity_view(entity: ResolvedEntityInspection) -> dict[str, object]:
    return {
        "entity_id": entity.entity_id,
        "entity_type": entity.entity_type,
        "behavior": entity.behavior,
        "configuration": thaw_json(entity.configuration),
        "public": thaw_json(entity.public),
    }


def _custom_preview(
    application: AntFarmApplication,
    definition: CustomSimulationDefinition,
) -> dict[str, object]:
    entities = application.inspect_resolved_entities(definition)
    return {
        "definition": definition.model_dump(mode="json", exclude_none=True),
        "entities": [_entity_view(entity) for entity in entities],
    }


def _validate_web_custom(definition: CustomSimulationDefinition) -> None:
    if definition.storage.kind != "memory":
        raise ApplicationError(
            ErrorCode.INVALID_ARGUMENT,
            "web-authored custom simulations currently require memory storage",
        )
    if definition.model_refs:
        raise ApplicationError(
            ErrorCode.INVALID_ARGUMENT,
            "web-authored custom simulations currently require deterministic behavior",
        )


def _run_state_view(state: RunState) -> dict[str, object]:
    return {
        "run_id": state.run_id,
        "mode": state.mode.value,
        "status": state.status.value,
        "tick": state.tick,
        "failure": state.failure.value if state.failure is not None else None,
    }


def _event_view(event: EventView) -> dict[str, object]:
    return {
        "schema_version": event.schema_version,
        "event_id": event.event_id,
        "run_id": event.run_id,
        "sequence": event.sequence,
        "tick": event.tick,
        "kind": event.kind,
        "actor_id": event.actor_id,
        "causation_id": event.causation_id,
        "payload": thaw_json(event.payload),
    }


async def _stream_events(
    runtime: ApiRuntime,
    websocket: WebSocket,
    run_id: str,
    *,
    after: int,
    kinds: set[str],
    buffer_size: int,
) -> None:
    try:
        state = runtime.application.read_run_state(run_id)
    except ApplicationError as error:
        await websocket.close(code=4404, reason=error.message)
        return

    await websocket.accept()
    queue: asyncio.Queue[EventView] = asyncio.Queue(maxsize=buffer_size)
    overflowed = asyncio.Event()

    def receive_committed(event: EventView) -> None:
        try:
            queue.put_nowait(event)
        except asyncio.QueueFull:
            overflowed.set()

    subscription = runtime.application.subscribe_events(
        run_id, kinds, receive_committed
    )
    last_sequence = after
    last_state: dict[str, object] | None = None
    try:
        recovery = runtime.application.query_events(
            EventQuery(
                run_id=run_id,
                after=after,
                limit=MAX_RECOVERY_EVENTS,
                kinds=frozenset(kinds),
            )
        )
        for event in recovery.items:
            await websocket.send_json({"type": "event", "event": _event_view(event)})
            last_sequence = max(last_sequence, event.sequence)
        if recovery.next_after is not None:
            await websocket.send_json(
                {
                    "type": "recovery_required",
                    "after": recovery.next_after,
                    "reason": "durable history exceeds the stream recovery window",
                }
            )
            await websocket.close(code=4009, reason="reconnect to continue recovery")
            return

        while True:
            state = runtime.application.read_run_state(run_id)
            encoded_state = _run_state_view(state)
            if encoded_state != last_state:
                await websocket.send_json({"type": "state", "state": encoded_state})
                last_state = encoded_state

            if overflowed.is_set():
                await websocket.send_json(
                    {
                        "type": "recovery_required",
                        "after": last_sequence,
                        "reason": "client fell behind the live event buffer",
                    }
                )
                await websocket.close(code=4009, reason="client fell behind")
                return

            try:
                event = await asyncio.wait_for(queue.get(), timeout=0.25)
            except TimeoutError:
                if state.status in TERMINAL_STATUSES and queue.empty():
                    return
                continue
            if event.sequence <= last_sequence:
                continue
            await websocket.send_json({"type": "event", "event": _event_view(event)})
            last_sequence = event.sequence
    except WebSocketDisconnect:
        return
    finally:
        subscription.cancel()


def _stream_kinds(value: str | None) -> set[str]:
    if value is None:
        return set(ALL_EVENT_KINDS)
    selected = {item.strip() for item in value.split(",") if item.strip()}
    if not selected:
        return set(ALL_EVENT_KINDS)
    return selected


async def _stop_active_runs(runtime: ApiRuntime) -> None:
    for run_id in sorted(runtime.run_ids):
        try:
            state = runtime.application.read_run_state(run_id)
            if state.status not in TERMINAL_STATUSES:
                await runtime.application.stop(StopRunCommand(run_id))
        except ApplicationError:
            continue


def _error_status(code: ErrorCode) -> int:
    return {
        ErrorCode.INVALID_ARGUMENT: 422,
        ErrorCode.INVALID_SCENARIO: 422,
        ErrorCode.NOT_FOUND: 404,
        ErrorCode.CONFLICT: 409,
        ErrorCode.INVALID_STATE: 409,
        ErrorCode.EXECUTION_FAILED: 500,
    }[code]


def _error_content(
    code: ErrorCode,
    message: str,
    details: Mapping[str, object] | JsonObject,
) -> dict[str, object]:
    return {
        "error": {
            "code": code.value,
            "message": message,
            "details": jsonable_encoder(details),
        }
    }


def _fresh_run_id(base: str) -> str:
    return f"{base}-{uuid4().hex[:10]}"


def _configured_generator(
    starter: CustomSimulationDefinition,
) -> CustomDefinitionGenerator:
    model = os.environ.get("ANTFARM_GENERATOR_MODEL")
    if not model:
        return StaticCustomDefinitionGenerator(starter)
    return OpenAICompatibleDefinitionGenerator(
        base_url=os.environ.get(
            "ANTFARM_GENERATOR_BASE_URL", "http://127.0.0.1:11434/v1"
        ),
        model=model,
        api_key=os.environ.get("ANTFARM_GENERATOR_API_KEY"),
    )
