"""Strict data-only schema for custom simulations."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Annotated, Any, Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    PositiveInt,
    model_validator,
)
from ruamel.yaml import YAML

from antfarm.config.schema import Identifier, ObservabilityConfig, StorageConfig
from antfarm.domain.json_values import JsonObject, freeze_object

type CustomValue = JsonValue
type ValueType = Literal["integer", "number", "string", "boolean", "array", "object"]
type Visibility = Literal["public", "owner", "internal"]


class CustomModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


class CustomRunConfig(CustomModel):
    id: Identifier
    seed: int = 0
    ticks: PositiveInt = 1


class StateFieldConfig(CustomModel):
    type: ValueType
    visibility: Visibility = "public"


class EntityTypeConfig(CustomModel):
    fields: dict[Identifier, StateFieldConfig] = Field(default_factory=dict)


class ParameterConfig(CustomModel):
    type: ValueType
    required: bool = True


class StateReference(CustomModel):
    scope: Literal["world", "actor"]
    field: Identifier


class ValueSource(CustomModel):
    source: Literal["literal", "parameter"]
    value: CustomValue = None
    parameter: Identifier | None = None
    multiplier: float = 1.0

    @model_validator(mode="after")
    def selected_source_is_complete(self) -> Self:
        if self.source == "parameter" and self.parameter is None:
            raise ValueError("parameter value sources require parameter")
        if self.source == "literal" and self.parameter is not None:
            raise ValueError("literal value sources cannot specify parameter")
        if not math.isfinite(self.multiplier):
            raise ValueError("value source multiplier must be finite")
        return self


class ConstraintConfig(CustomModel):
    left: StateReference
    operator: Literal["eq", "not_eq", "gte", "lte"]
    right: ValueSource


class EffectConfig(CustomModel):
    target: StateReference
    operation: Literal["set", "add"]
    value: ValueSource


class ActionDefinition(CustomModel):
    description: Annotated[str, Field(min_length=1)]
    actor_types: Annotated[tuple[Identifier, ...], Field(min_length=1)]
    parameters: dict[Identifier, ParameterConfig] = Field(default_factory=dict)
    constraints: tuple[ConstraintConfig, ...] = ()
    effects: Annotated[tuple[EffectConfig, ...], Field(min_length=1)]


class PlannedAction(CustomModel):
    kind: Identifier
    parameters: dict[Identifier, CustomValue] = Field(default_factory=dict)


class DeterministicBehavior(CustomModel):
    kind: Literal["deterministic"]
    actions: tuple[PlannedAction, ...] = ()
    repeat: bool = False


class ModelBehavior(CustomModel):
    kind: Literal["model"]
    model_ref: Identifier


BehaviorConfig = Annotated[
    DeterministicBehavior | ModelBehavior, Field(discriminator="kind")
]


class EntityConfig(CustomModel):
    id: Identifier
    type: Identifier
    state: dict[Identifier, CustomValue] = Field(default_factory=dict)
    behavior: BehaviorConfig | None = None


class ActivationConfig(CustomModel):
    kind: Literal["interval"] = "interval"
    interval: PositiveInt = 1
    stagger: bool = False
    max_activations_per_tick: PositiveInt | None = None


class ObservationConfig(CustomModel):
    include_public_world: bool = True
    include_public_entities: bool = True
    include_owner_state: bool = True


class TerminationConfig(CustomModel):
    kind: Literal["ticks"] = "ticks"


class CustomSimulationDefinition(CustomModel):
    schema_version: Literal[1]
    kind: Literal["custom"]
    run: CustomRunConfig
    entity_types: dict[Identifier, EntityTypeConfig]
    entities: tuple[EntityConfig, ...] = ()
    world_fields: dict[Identifier, StateFieldConfig] = Field(default_factory=dict)
    world_state: dict[Identifier, CustomValue] = Field(default_factory=dict)
    actions: dict[Identifier, ActionDefinition] = Field(default_factory=dict)
    model_refs: tuple[Identifier, ...] = ()
    observations: ObservationConfig = Field(default_factory=ObservationConfig)
    activation: ActivationConfig = Field(default_factory=ActivationConfig)
    termination: TerminationConfig = Field(default_factory=TerminationConfig)
    observability: ObservabilityConfig = Field(default_factory=ObservabilityConfig)
    storage: StorageConfig

    @model_validator(mode="after")
    def references_and_values_are_valid(self) -> Self:
        entity_ids = [entity.id for entity in self.entities]
        if len(entity_ids) != len(set(entity_ids)):
            raise ValueError("duplicate entity identifiers")
        if len(self.model_refs) != len(set(self.model_refs)):
            raise ValueError("duplicate model references")
        _validate_state("world", self.world_fields, self.world_state)
        if any(field.visibility == "owner" for field in self.world_fields.values()):
            raise ValueError("world fields cannot use owner visibility")

        for entity in self.entities:
            entity_type = self.entity_types.get(entity.type)
            if entity_type is None:
                raise ValueError(
                    f"entity {entity.id!r} references unknown type {entity.type!r}"
                )
            _validate_state(f"entity {entity.id!r}", entity_type.fields, entity.state)
            behavior = entity.behavior
            if (
                isinstance(behavior, ModelBehavior)
                and behavior.model_ref not in self.model_refs
            ):
                raise ValueError(
                    f"entity {entity.id!r} references unknown model "
                    f"{behavior.model_ref!r}"
                )
            if isinstance(behavior, DeterministicBehavior):
                for planned in behavior.actions:
                    _validate_planned_action(
                        self.actions, planned, entity.id, entity.type
                    )

        for action_id, action in self.actions.items():
            if len(action.actor_types) != len(set(action.actor_types)):
                raise ValueError(f"action {action_id!r} has duplicate actor types")
            for actor_type in action.actor_types:
                if actor_type not in self.entity_types:
                    raise ValueError(
                        f"action {action_id!r} references unknown actor type "
                        f"{actor_type!r}"
                    )
            for constraint in action.constraints:
                _validate_reference(self, action, constraint.left, action_id)
                _validate_source(action, constraint.right, action_id)
                _validate_operation_types(
                    self,
                    action,
                    constraint.left,
                    constraint.right,
                    constraint.operator,
                    action_id,
                )
            for effect in action.effects:
                _validate_reference(self, action, effect.target, action_id)
                _validate_source(action, effect.value, action_id)
                _validate_operation_types(
                    self,
                    action,
                    effect.target,
                    effect.value,
                    effect.operation,
                    action_id,
                )
        return self

    def normalized_data(self) -> JsonObject:
        raw = json.loads(self.model_dump_json(exclude_none=True))
        if not isinstance(raw, dict):
            raise TypeError("normalized custom definition must be an object")
        return freeze_object(raw)


def load_custom_definition(path: str | Path) -> CustomSimulationDefinition:
    """Load safe YAML 1.2 or JSON and strictly validate a custom definition."""

    selected = Path(path)
    with selected.open(encoding="utf-8") as stream:
        if selected.suffix.lower() == ".json":
            raw: Any = json.load(stream)
        else:
            yaml = YAML(typ="safe", pure=True)
            yaml.version = (1, 2)
            raw = yaml.load(stream)
    if not isinstance(raw, dict):
        raise ValueError("custom definition root must be a mapping")
    return CustomSimulationDefinition.model_validate(raw)


def _validate_state(
    label: str,
    fields: dict[str, StateFieldConfig],
    state: dict[str, CustomValue],
) -> None:
    missing = set(fields) - set(state)
    unknown = set(state) - set(fields)
    if missing:
        raise ValueError(f"{label} is missing fields: {', '.join(sorted(missing))}")
    if unknown:
        raise ValueError(f"{label} has unknown fields: {', '.join(sorted(unknown))}")
    for field_name, value in state.items():
        _validate_value(f"{label}.{field_name}", fields[field_name].type, value)


def _validate_value(label: str, expected: ValueType, value: object) -> None:
    valid = {
        "integer": isinstance(value, int) and not isinstance(value, bool),
        "number": isinstance(value, (int, float)) and not isinstance(value, bool),
        "string": isinstance(value, str),
        "boolean": isinstance(value, bool),
        "array": isinstance(value, list),
        "object": isinstance(value, dict),
    }[expected]
    if not valid:
        raise ValueError(f"{label} must be {expected}")


def _validate_planned_action(
    actions: dict[str, ActionDefinition],
    planned: PlannedAction,
    entity_id: str,
    entity_type: str,
) -> None:
    action = actions.get(planned.kind)
    if action is None:
        raise ValueError(
            f"entity {entity_id!r} plans unknown action {planned.kind!r}"
        )
    if entity_type not in action.actor_types:
        raise ValueError(
            f"entity {entity_id!r} cannot perform action {planned.kind!r}"
        )
    required = {
        name for name, parameter in action.parameters.items() if parameter.required
    }
    missing = required - set(planned.parameters)
    unknown = set(planned.parameters) - set(action.parameters)
    if missing or unknown:
        raise ValueError(
            f"entity {entity_id!r} has invalid parameters for {planned.kind}"
        )
    for name, value in planned.parameters.items():
        _validate_value(
            f"entity {entity_id!r} action {planned.kind}.{name}",
            action.parameters[name].type,
            value,
        )


def _validate_reference(
    definition: CustomSimulationDefinition,
    action: ActionDefinition,
    reference: StateReference,
    action_id: str,
) -> None:
    if reference.scope == "world":
        if reference.field not in definition.world_fields:
            raise ValueError(
                f"action {action_id!r} references unknown world field "
                f"{reference.field!r}"
            )
        return
    if any(
        reference.field not in definition.entity_types[actor_type].fields
        for actor_type in action.actor_types
    ):
        raise ValueError(
            f"action {action_id!r} references unknown actor field {reference.field!r}"
        )


def _validate_source(
    action: ActionDefinition, source: ValueSource, action_id: str
) -> None:
    if source.source == "parameter" and source.parameter not in action.parameters:
        raise ValueError(
            f"action {action_id!r} references unknown parameter {source.parameter!r}"
        )
    if (
        source.source == "parameter"
        and source.parameter is not None
        and not action.parameters[source.parameter].required
    ):
        raise ValueError(
            f"action {action_id!r} transition parameter {source.parameter!r} "
            "must be required"
        )


def _validate_operation_types(
    definition: CustomSimulationDefinition,
    action: ActionDefinition,
    reference: StateReference,
    source: ValueSource,
    operation: str,
    action_id: str,
) -> None:
    target_types = _reference_types(definition, action, reference)
    if len(target_types) != 1:
        raise ValueError(
            f"action {action_id!r} actor field {reference.field!r} has "
            "inconsistent types"
        )
    target_type = next(iter(target_types))
    source_type = _source_type(action, source)
    numeric = {"integer", "number"}
    if source.multiplier != 1 and source_type not in numeric:
        raise ValueError(f"action {action_id!r} multiplies a non-numeric value")
    if (
        target_type == "integer"
        and source_type == "integer"
        and not source.multiplier.is_integer()
    ):
        raise ValueError(
            f"action {action_id!r} produces a non-integer transition value"
        )
    if operation in {"add", "gte", "lte"}:
        if target_type not in numeric or source_type not in numeric:
            raise ValueError(
                f"action {action_id!r} operation {operation!r} requires numbers"
            )
    elif not _types_compatible(target_type, source_type):
        raise ValueError(
            f"action {action_id!r} uses incompatible {target_type} and "
            f"{source_type} values"
        )


def _reference_types(
    definition: CustomSimulationDefinition,
    action: ActionDefinition,
    reference: StateReference,
) -> set[ValueType]:
    if reference.scope == "world":
        return {definition.world_fields[reference.field].type}
    return {
        definition.entity_types[actor_type].fields[reference.field].type
        for actor_type in action.actor_types
    }


def _source_type(action: ActionDefinition, source: ValueSource) -> ValueType:
    if source.source == "parameter":
        if source.parameter is None:
            raise RuntimeError("validated parameter source is incomplete")
        return action.parameters[source.parameter].type
    value = source.value
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    raise ValueError("literal transition values cannot be null")


def _types_compatible(target: ValueType, source: ValueType) -> bool:
    return target == source or (target == "number" and source == "integer")
