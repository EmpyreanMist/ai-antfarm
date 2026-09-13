"""Explicit JSON serialization for persisted M0 domain values."""

from collections.abc import Mapping
from typing import cast

from antfarm.domain.json_values import JsonObject, freeze_object, thaw_json
from antfarm.domain.models import (
    ActionProposal,
    ActionResult,
    AgentId,
    Event,
    EventSequence,
    RunId,
    SimulationSnapshot,
    Tick,
    ValidatedAction,
)


def action_proposal_to_data(value: ActionProposal) -> dict[str, object]:
    return {
        "actor_id": str(value.actor_id),
        "kind": value.kind,
        "parameters": thaw_json(value.parameters),
    }


def action_proposal_from_data(data: Mapping[str, object]) -> ActionProposal:
    return ActionProposal(
        actor_id=AgentId(_string(data, "actor_id")),
        kind=_string(data, "kind"),
        parameters=_object(data, "parameters"),
    )


def validated_action_to_data(value: ValidatedAction) -> dict[str, object]:
    return {
        "actor_id": str(value.actor_id),
        "kind": value.kind,
        "parameters": thaw_json(value.parameters),
    }


def validated_action_from_data(data: Mapping[str, object]) -> ValidatedAction:
    return ValidatedAction(
        actor_id=AgentId(_string(data, "actor_id")),
        kind=_string(data, "kind"),
        parameters=_object(data, "parameters"),
    )


def action_result_to_data(value: ActionResult) -> dict[str, object]:
    return {"success": value.success, "payload": thaw_json(value.payload)}


def action_result_from_data(data: Mapping[str, object]) -> ActionResult:
    success = data.get("success")
    if not isinstance(success, bool):
        raise TypeError("success must be a boolean")
    return ActionResult(success=success, payload=_object(data, "payload"))


def event_to_data(value: Event) -> dict[str, object]:
    return {
        "schema_version": value.schema_version,
        "event_id": value.event_id,
        "run_id": str(value.run_id),
        "sequence": int(value.sequence),
        "tick": int(value.tick),
        "kind": value.kind,
        "actor_id": None if value.actor_id is None else str(value.actor_id),
        "causation_id": value.causation_id,
        "payload": thaw_json(value.payload),
    }


def event_from_data(data: Mapping[str, object]) -> Event:
    actor = data.get("actor_id")
    causation = data.get("causation_id")
    if actor is not None and not isinstance(actor, str):
        raise TypeError("actor_id must be a string or null")
    if causation is not None and not isinstance(causation, str):
        raise TypeError("causation_id must be a string or null")
    return Event(
        schema_version=_integer(data, "schema_version"),
        event_id=_string(data, "event_id"),
        run_id=RunId(_string(data, "run_id")),
        sequence=EventSequence(_integer(data, "sequence")),
        tick=Tick(_integer(data, "tick")),
        kind=_string(data, "kind"),
        actor_id=None if actor is None else AgentId(actor),
        causation_id=causation,
        payload=_object(data, "payload"),
    )


def snapshot_to_data(value: SimulationSnapshot) -> dict[str, object]:
    return {
        "tick": int(value.tick),
        "world": thaw_json(value.world),
        "memory": thaw_json(value.memory),
        "scheduler": thaw_json(value.scheduler),
        "engine": thaw_json(value.engine),
    }


def snapshot_from_data(data: Mapping[str, object]) -> SimulationSnapshot:
    return SimulationSnapshot(
        tick=Tick(_integer(data, "tick")),
        world=_object(data, "world"),
        memory=_object(data, "memory"),
        scheduler=_object(data, "scheduler"),
        engine=_object(data, "engine"),
    )


def _string(data: Mapping[str, object], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str):
        raise TypeError(f"{key} must be a string")
    return value


def _integer(data: Mapping[str, object], key: str) -> int:
    value = data.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{key} must be an integer")
    return value


def _object(data: Mapping[str, object], key: str) -> JsonObject:
    value = data.get(key)
    if not isinstance(value, Mapping):
        raise TypeError(f"{key} must be an object")
    return freeze_object(cast(Mapping[str, object], value))
