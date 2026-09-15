"""Composition and environment for data-only custom simulations."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from antfarm.adapters.events import InMemoryEventBus
from antfarm.adapters.memory import InMemoryMemoryStore
from antfarm.adapters.storage import InMemoryStorage, SQLiteStorage
from antfarm.application.agent import ModelBackedAgent
from antfarm.application.engine import SimulationEngine
from antfarm.application.metrics import BuiltInMetricCollector
from antfarm.application.scheduler import StableScheduler
from antfarm.composition import ComposedSimulation
from antfarm.config.schema import SqliteStorageConfig
from antfarm.custom.schema import (
    ActionDefinition,
    CustomSimulationDefinition,
    DeterministicBehavior,
    ModelBehavior,
    StateReference,
    ValueSource,
)
from antfarm.domain.json_values import JsonObject, freeze_object, thaw_json
from antfarm.domain.models import (
    ActionProposal,
    ActionResult,
    AgentContext,
    AgentId,
    MemoryItem,
    Observation,
    RunId,
    RunMetadata,
    Tick,
    ValidatedAction,
    ValidationResult,
)
from antfarm.domain.protocols import Agent, RandomSource
from antfarm.ports.models import ModelProvider
from antfarm.ports.storage import Storage


@dataclass(slots=True)
class DeterministicEntity:
    id: AgentId
    actions: tuple[ActionProposal, ...]
    repeat: bool
    model_ref: str = "deterministic"

    async def decide(self, context: AgentContext) -> ActionProposal | None:
        index = int(context.observation.tick) - 1
        if not self.actions:
            return None
        if self.repeat:
            return self.actions[index % len(self.actions)]
        return self.actions[index] if index < len(self.actions) else None


class DeclarativeEnvironment:
    """Own and mutate state only through validated declarative transitions."""

    def __init__(self, definition: CustomSimulationDefinition) -> None:
        self._definition = definition
        self._world: dict[str, object] = dict(definition.world_state)
        self._entity_types = {entity.id: entity.type for entity in definition.entities}
        self._entities: dict[str, dict[str, object]] = {
            entity.id: dict(entity.state) for entity in definition.entities
        }

    def observe(self, agent_id: AgentId, tick: Tick) -> Observation:
        selected = str(agent_id)
        if selected not in self._entities:
            raise ValueError(f"unknown custom entity: {selected}")
        visible_world = {
            name: value
            for name, value in self._world.items()
            if self._definition.observations.include_public_world
            and self._definition.world_fields[name].visibility == "public"
        }
        visible_entities: dict[str, object] = {}
        for entity_id, state in self._entities.items():
            fields = self._definition.entity_types[
                self._entity_types[entity_id]
            ].fields
            visible_entities[entity_id] = {
                name: value
                for name, value in state.items()
                if (
                    self._definition.observations.include_public_entities
                    and fields[name].visibility == "public"
                )
                or (
                    entity_id == selected
                    and self._definition.observations.include_owner_state
                    and fields[name].visibility == "owner"
                )
            }
        return Observation(
            agent_id=agent_id,
            tick=tick,
            state=freeze_object(
                {"world": visible_world, "entities": visible_entities}
            ),
        )

    def validate(self, proposal: ActionProposal) -> ValidationResult:
        actor_id = str(proposal.actor_id)
        action = self._definition.actions.get(proposal.kind)
        if action is None:
            return ValidationResult(None, "action is not defined")
        if actor_id not in self._entities:
            return ValidationResult(None, "actor is not a known entity")
        if self._entity_types[actor_id] not in action.actor_types:
            return ValidationResult(None, "action is not available to this entity type")
        parameter_error = _validate_parameters(action, proposal.parameters)
        if parameter_error is not None:
            return ValidationResult(None, parameter_error)
        for constraint in action.constraints:
            left = self._read(actor_id, constraint.left)
            right = _source_value(constraint.right, proposal.parameters)
            if not _compare(left, constraint.operator, right):
                return ValidationResult(None, "action constraint was not satisfied")
        return ValidationResult(
            ValidatedAction(
                actor_id=proposal.actor_id,
                kind=proposal.kind,
                parameters=proposal.parameters,
            )
        )

    def apply(
        self, action: ValidatedAction, rng: RandomSource, tick: Tick
    ) -> ActionResult:
        del rng, tick
        definition = self._definition.actions[action.kind]
        actor_id = str(action.actor_id)
        changes: dict[str, object] = {}
        for effect in definition.effects:
            current = self._read(actor_id, effect.target)
            operand = _source_value(effect.value, action.parameters)
            updated = operand
            if effect.operation == "add":
                if (
                    isinstance(current, bool)
                    or isinstance(operand, bool)
                    or not isinstance(current, (int, float))
                    or not isinstance(operand, (int, float))
                ):
                    raise TypeError("add effects require numeric values")
                updated = current + operand
            self._write(actor_id, effect.target, updated)
            changes[f"{effect.target.scope}.{effect.target.field}"] = updated
        return ActionResult(success=True, payload=freeze_object({"changes": changes}))

    def memory_deliveries(
        self, action: ValidatedAction, result: ActionResult
    ) -> Mapping[AgentId, Sequence[MemoryItem]]:
        del action, result
        return {}

    def snapshot(self) -> JsonObject:
        return freeze_object(
            {
                "world": self._world,
                "entities": self._entities,
            }
        )

    def restore(self, state: JsonObject) -> None:
        raw = thaw_json(state)
        if not isinstance(raw, dict):
            raise TypeError("custom state must be an object")
        world = raw.get("world")
        entities = raw.get("entities")
        if not isinstance(world, dict) or not isinstance(entities, dict):
            raise TypeError("custom state requires world and entities objects")
        if set(entities) != set(self._entity_types) or any(
            not isinstance(value, dict) for value in entities.values()
        ):
            raise ValueError("custom state entity identifiers do not match definition")
        candidate = self._definition.model_dump(mode="json")
        candidate["world_state"] = world
        for entity in candidate["entities"]:
            entity["state"] = entities[entity["id"]]
        validated = CustomSimulationDefinition.model_validate(candidate)
        self._world = dict(validated.world_state)
        self._entities = {
            entity.id: dict(entity.state) for entity in validated.entities
        }

    def _read(self, actor_id: str, reference: StateReference) -> object:
        if reference.scope == "world":
            return self._world[reference.field]
        return self._entities[actor_id][reference.field]

    def _write(
        self, actor_id: str, reference: StateReference, value: object
    ) -> None:
        if reference.scope == "world":
            self._world[reference.field] = value
        else:
            self._entities[actor_id][reference.field] = value


def compose_custom(
    definition: CustomSimulationDefinition,
    *,
    model_providers: Mapping[str, ModelProvider] | None = None,
    runtime_overrides: JsonObject | None = None,
) -> ComposedSimulation:
    """Compose a custom definition into the existing authoritative engine."""

    supplied_models = dict(model_providers or {})
    missing_models = set(definition.model_refs) - set(supplied_models)
    if missing_models:
        raise ValueError(
            f"custom model providers are missing: {', '.join(sorted(missing_models))}"
        )

    action_views = tuple(
        freeze_object(
            {
                "kind": action_id,
                "description": action.description,
                "parameters": {
                    name: parameter.type
                    for name, parameter in action.parameters.items()
                },
            }
        )
        for action_id, action in definition.actions.items()
    )
    agents: dict[AgentId, Agent] = {}
    for entity in definition.entities:
        behavior = entity.behavior
        if behavior is None:
            continue
        agent_id = AgentId(entity.id)
        if isinstance(behavior, DeterministicBehavior):
            agents[agent_id] = DeterministicEntity(
                id=agent_id,
                actions=tuple(
                    ActionProposal(
                        actor_id=agent_id,
                        kind=planned.kind,
                        parameters=freeze_object(planned.parameters),
                    )
                    for planned in behavior.actions
                ),
                repeat=behavior.repeat,
            )
        elif isinstance(behavior, ModelBehavior):
            agents[agent_id] = ModelBackedAgent(
                id=agent_id,
                model_ref=behavior.model_ref,
                provider=supplied_models[behavior.model_ref],
                available_actions=action_views,
            )

    storage: Storage
    if isinstance(definition.storage, SqliteStorageConfig):
        storage = SQLiteStorage(definition.storage.path)
    else:
        storage = InMemoryStorage()
    run_id = RunId(definition.run.id)
    storage.create_run(
        RunMetadata(
            run_id=run_id,
            seed=definition.run.seed,
            runtime_overrides=runtime_overrides or {},
        ),
        definition.normalized_data(),
    )
    event_bus = InMemoryEventBus(
        max_retained_events=definition.observability.event_buffer_limit
    )
    metrics = BuiltInMetricCollector(
        ("action_count", "rejection_count", "agent_outcomes"),
        action_kinds=tuple(definition.actions),
        agent_ids=tuple(str(agent_id) for agent_id in agents),
    )
    engine = SimulationEngine(
        run_id=run_id,
        seed=definition.run.seed,
        agents=agents,
        environment=DeclarativeEnvironment(definition),
        memory=InMemoryMemoryStore(),
        scheduler=StableScheduler(
            interval=definition.activation.interval,
            stagger=definition.activation.stagger,
            max_cognitions_per_tick=definition.activation.max_activations_per_tick,
        ),
        event_bus=event_bus,
        storage=storage,
        metrics=metrics,
    )
    return ComposedSimulation(
        engine=engine,
        storage=storage,
        event_bus=event_bus,
        metrics=metrics,
        providers=tuple(dict.fromkeys(supplied_models.values())),
    )


def _validate_parameters(
    action: ActionDefinition, parameters: Mapping[str, object]
) -> str | None:
    required = {
        name for name, definition in action.parameters.items() if definition.required
    }
    if required - set(parameters):
        return "required action parameters are missing"
    if set(parameters) - set(action.parameters):
        return "action has unknown parameters"
    for name, value in parameters.items():
        expected = action.parameters[name].type
        valid = {
            "integer": isinstance(value, int) and not isinstance(value, bool),
            "number": isinstance(value, (int, float)) and not isinstance(value, bool),
            "string": isinstance(value, str),
            "boolean": isinstance(value, bool),
            "array": isinstance(value, tuple),
            "object": isinstance(value, Mapping),
        }[expected]
        if not valid:
            return f"action parameter {name!r} must be {expected}"
    return None


def _source_value(source: ValueSource, parameters: Mapping[str, object]) -> object:
    if source.source == "parameter":
        if source.parameter is None:
            raise RuntimeError("validated parameter source is incomplete")
        value = parameters[source.parameter]
    else:
        value = source.value
    if source.multiplier == 1:
        return value
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
    ):
        raise TypeError("value source multipliers require numeric values")
    multiplied = value * source.multiplier
    if isinstance(value, int) and source.multiplier.is_integer():
        return int(multiplied)
    return multiplied


def _compare(left: object, operator: str, right: object) -> bool:
    if operator == "eq":
        return left == right
    if operator == "not_eq":
        return left != right
    if (
        isinstance(left, bool)
        or isinstance(right, bool)
        or not isinstance(left, (int, float))
        or not isinstance(right, (int, float))
    ):
        return False
    return left >= right if operator == "gte" else left <= right
