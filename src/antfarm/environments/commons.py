"""Finite shared-resource environment with agent-owned holdings."""

from collections.abc import Iterable, Mapping, Sequence

from antfarm.domain.json_values import JsonObject, freeze_object
from antfarm.domain.models import (
    ActionProposal,
    ActionResult,
    AgentId,
    InformationVisibility,
    MemoryItem,
    Observation,
    PublicAgentProfile,
    Tick,
    ValidatedAction,
    ValidationResult,
)
from antfarm.domain.protocols import RandomSource


class CommonsEnvironment:
    """Let agents harvest from and contribute to a shared resource."""

    def __init__(
        self,
        *,
        initial_resource: int,
        initial_endowment: int,
        agent_ids: Iterable[AgentId],
        initial_holdings: Mapping[AgentId, int] | None = None,
        public_profiles: Mapping[AgentId, PublicAgentProfile] | None = None,
        visibility: Mapping[AgentId, InformationVisibility] | None = None,
        social: bool = False,
        message_max_length: int = 500,
        history_limit: int = 20,
        roster_limit: int = 100,
        topic: str | None = None,
        situation: str | None = None,
    ) -> None:
        if initial_resource < 0 or initial_endowment < 0:
            raise ValueError("commons initial values must not be negative")
        if message_max_length < 1 or history_limit < 1 or roster_limit < 1:
            raise ValueError("social message limits must be positive")
        self._resource = initial_resource
        configured_holdings = initial_holdings or {}
        self._holdings = {
            agent_id: initial_endowment for agent_id in sorted(agent_ids, key=str)
        }
        if set(configured_holdings).difference(self._holdings):
            raise ValueError("initial holdings contain an unknown agent")
        if any(
            isinstance(amount, bool) or not isinstance(amount, int) or amount < 0
            for amount in configured_holdings.values()
        ):
            raise ValueError("initial holdings must be non-negative integers")
        self._holdings.update(configured_holdings)
        self._public_profiles = dict(public_profiles or {})
        self._visibility = dict(visibility or {})
        if set(self._public_profiles).difference(self._holdings) or set(
            self._visibility
        ).difference(self._holdings):
            raise ValueError("observable profile metadata contains an unknown agent")
        self._social = social
        self._message_max_length = message_max_length
        self._history_limit = history_limit
        self._roster_limit = roster_limit
        self._topic = topic
        self._situation = situation
        self._messages: list[JsonObject] = []
        self._next_message_sequence = 1

    def observe(self, agent_id: AgentId, tick: Tick) -> Observation:
        if agent_id not in self._holdings:
            raise ValueError(f"unknown agent: {agent_id}")
        state: dict[str, object] = {
            "resource": self._resource,
            "own_holding": self._holdings[agent_id],
        }
        if self._social:
            visible_agents = list(self._holdings)[: self._roster_limit]
            if agent_id not in visible_agents:
                visible_agents[-1] = agent_id
            state.update(
                roster=tuple(
                    self._roster_entry(member_id, observer_id=agent_id)
                    for member_id in visible_agents
                ),
                recent_messages=tuple(
                    message
                    for message in self._messages
                    if _message_tick(message) < int(tick)
                ),
            )
            if self._topic is not None:
                state["conversation_topic"] = self._topic
            if self._situation is not None:
                state["conversation_situation"] = self._situation
        return Observation(
            agent_id=agent_id,
            tick=tick,
            state=freeze_object(state),
        )

    def _roster_entry(
        self, member_id: AgentId, *, observer_id: AgentId
    ) -> dict[str, object]:
        entry: dict[str, object] = {"id": str(member_id)}
        if member_id == observer_id:
            return entry
        profile: dict[str, object] = {}
        public_profile = self._public_profiles.get(member_id)
        if public_profile is not None and public_profile.economics is not None:
            public_economics = public_profile.economics
            economics: dict[str, object] = {}
            if public_economics.money is not None:
                economics["money"] = public_economics.money
            if public_economics.recurring_income is not None:
                economics["recurring_income"] = public_economics.recurring_income
            if public_economics.resources:
                economics["resources"] = dict(public_economics.resources)
            if public_economics.occupation is not None:
                economics["occupation"] = public_economics.occupation
            profile["economics"] = economics
        if public_profile is not None and public_profile.social_status is not None:
            public_status = public_profile.social_status
            status: dict[str, object] = {}
            if public_status.label is not None:
                status["label"] = public_status.label
            if public_status.roles:
                status["roles"] = list(public_status.roles)
            if public_status.standing is not None:
                status["standing"] = public_status.standing
            profile["social_status"] = status
        if public_profile is not None and public_profile.reputation is not None:
            public_reputation = public_profile.reputation
            reputation: dict[str, object] = {}
            if public_reputation.score is not None:
                reputation["score"] = public_reputation.score
            if public_reputation.labels:
                reputation["labels"] = tuple(public_reputation.labels)
            profile["reputation"] = reputation
        if public_profile is not None and public_profile.relationships:
            profile["relationships"] = {
                str(agent_id): {
                    "kind": relationship.kind,
                    **(
                        {"strength": relationship.strength}
                        if relationship.strength is not None
                        else {}
                    ),
                }
                for agent_id, relationship in public_profile.relationships.items()
            }
        member_visibility = self._visibility.get(member_id, InformationVisibility())
        if member_visibility.possessions == "public":
            existing_economics = profile.get("economics")
            economics = (
                dict(existing_economics)
                if isinstance(existing_economics, Mapping)
                else {}
            )
            economics["holding"] = self._holdings[member_id]
            profile["economics"] = economics
        if profile:
            entry["public_profile"] = profile
        return entry

    def validate(self, proposal: ActionProposal) -> ValidationResult:
        if proposal.actor_id not in self._holdings:
            return ValidationResult(action=None, reason="unknown actor")
        if proposal.kind == "say":
            return self._validate_speech(proposal)
        if proposal.kind not in {"harvest", "contribute"}:
            return ValidationResult(action=None, reason="unsupported action kind")
        if set(proposal.parameters) != {"amount"}:
            return ValidationResult(action=None, reason="amount is required")
        amount = proposal.parameters["amount"]
        if isinstance(amount, bool) or not isinstance(amount, int) or amount < 1:
            return ValidationResult(
                action=None, reason="amount must be a positive integer"
            )
        available = (
            self._resource
            if proposal.kind == "harvest"
            else self._holdings[proposal.actor_id]
        )
        if amount > available:
            source = "resource" if proposal.kind == "harvest" else "holding"
            return ValidationResult(
                action=None,
                reason=f"amount exceeds available {source}",
            )
        return ValidationResult(
            action=ValidatedAction(
                actor_id=proposal.actor_id,
                kind=proposal.kind,
                parameters=proposal.parameters,
            )
        )

    def apply(
        self, action: ValidatedAction, rng: RandomSource, tick: Tick
    ) -> ActionResult:
        del rng
        if action.kind == "say":
            text = action.parameters.get("text")
            if not self._social or not isinstance(text, str):
                raise ValueError("validated speech is invalid")
            message: JsonObject = {
                "id": f"message-{self._next_message_sequence}",
                "sender_id": str(action.actor_id),
                "tick": int(tick),
                "text": text,
            }
            self._next_message_sequence += 1
            self._messages.append(message)
            self._messages = self._messages[-self._history_limit :]
            return ActionResult(success=True, payload={"message": message})
        amount = action.parameters.get("amount")
        if isinstance(amount, bool) or not isinstance(amount, int) or amount < 1:
            raise ValueError("validated commons amount must be a positive integer")
        if action.actor_id not in self._holdings:
            raise ValueError("validated commons actor is unknown")
        if action.kind == "harvest":
            if amount > self._resource:
                raise ValueError("validated harvest exceeds available resource")
            self._resource -= amount
            self._holdings[action.actor_id] += amount
        elif action.kind == "contribute":
            if amount > self._holdings[action.actor_id]:
                raise ValueError("validated contribution exceeds actor holding")
            self._holdings[action.actor_id] -= amount
            self._resource += amount
        else:
            raise ValueError("environment cannot apply this action kind")
        return ActionResult(
            success=True,
            payload={
                "resource": self._resource,
                "actor_holding": self._holdings[action.actor_id],
            },
        )

    def memory_deliveries(
        self, action: ValidatedAction, result: ActionResult
    ) -> Mapping[AgentId, Sequence[MemoryItem]]:
        if action.kind != "say":
            return {}
        message = result.payload.get("message")
        if not isinstance(message, Mapping):
            raise TypeError("speech result must contain a message")
        item = MemoryItem(kind="public_message", content=message)
        return {agent_id: (item,) for agent_id in self._holdings}

    def snapshot(self) -> JsonObject:
        state: dict[str, object] = {
            "resource": self._resource,
            "holdings": {
                str(agent_id): amount for agent_id, amount in self._holdings.items()
            },
        }
        if self._social:
            state.update(
                messages=tuple(self._messages),
                next_message_sequence=self._next_message_sequence,
            )
        return freeze_object(state)

    def restore(self, state: JsonObject) -> None:
        expected_keys = {"resource", "holdings"}
        if self._social:
            expected_keys.update({"messages", "next_message_sequence"})
        if set(state) != expected_keys:
            raise ValueError("commons state does not match its configured mode")
        resource = state["resource"]
        holdings = state["holdings"]
        if isinstance(resource, bool) or not isinstance(resource, int) or resource < 0:
            raise TypeError("commons resource must be a non-negative integer")
        if not isinstance(holdings, Mapping):
            raise TypeError("commons holdings must be an object")
        expected_agents = {str(agent_id) for agent_id in self._holdings}
        if set(holdings) != expected_agents:
            raise ValueError("commons holdings must contain every configured agent")
        restored: dict[AgentId, int] = {}
        for raw_agent_id, amount in holdings.items():
            if isinstance(amount, bool) or not isinstance(amount, int) or amount < 0:
                raise TypeError("commons holdings must be non-negative integers")
            restored[AgentId(raw_agent_id)] = amount
        self._resource = resource
        self._holdings = restored
        if self._social:
            messages = state["messages"]
            next_sequence = state["next_message_sequence"]
            if not isinstance(messages, tuple):
                raise TypeError("commons messages must be an array")
            if (
                isinstance(next_sequence, bool)
                or not isinstance(next_sequence, int)
                or next_sequence < 1
            ):
                raise TypeError("next message sequence must be a positive integer")
            restored_messages = [
                _validated_message(
                    message,
                    agent_ids=frozenset(str(agent_id) for agent_id in self._holdings),
                    message_max_length=self._message_max_length,
                )
                for message in messages
            ]
            if len(restored_messages) > self._history_limit:
                raise ValueError("commons message history exceeds configured limit")
            message_sequences = [
                _message_sequence(message) for message in restored_messages
            ]
            if len(set(message_sequences)) != len(message_sequences):
                raise ValueError("commons message ids must be unique")
            if message_sequences and next_sequence <= max(message_sequences):
                raise ValueError("next message sequence must follow retained messages")
            self._messages = restored_messages
            self._next_message_sequence = next_sequence

    def _validate_speech(self, proposal: ActionProposal) -> ValidationResult:
        if not self._social:
            return ValidationResult(action=None, reason="social mode is disabled")
        if set(proposal.parameters) != {"text"}:
            return ValidationResult(action=None, reason="text is required")
        text = proposal.parameters["text"]
        if not isinstance(text, str) or not text.strip():
            return ValidationResult(action=None, reason="text must not be empty")
        if len(text) > self._message_max_length:
            return ValidationResult(
                action=None,
                reason=f"text exceeds maximum length of {self._message_max_length}",
            )
        return ValidationResult(
            action=ValidatedAction(
                actor_id=proposal.actor_id,
                kind="say",
                parameters={"text": text},
            )
        )


def _message_tick(message: Mapping[str, object]) -> int:
    tick = message.get("tick")
    if isinstance(tick, bool) or not isinstance(tick, int):
        raise TypeError("message tick must be an integer")
    return tick


def _message_sequence(message: Mapping[str, object]) -> int:
    message_id = message.get("id")
    if not isinstance(message_id, str) or not message_id.startswith("message-"):
        raise ValueError("commons message id is invalid")
    raw_sequence = message_id.removeprefix("message-")
    if not raw_sequence.isdigit() or int(raw_sequence) < 1:
        raise ValueError("commons message id is invalid")
    return int(raw_sequence)


def _validated_message(
    value: object, *, agent_ids: frozenset[str], message_max_length: int
) -> JsonObject:
    if not isinstance(value, Mapping) or set(value) != {
        "id",
        "sender_id",
        "tick",
        "text",
    }:
        raise TypeError("commons message is invalid")
    message_id = value["id"]
    sender_id = value["sender_id"]
    text = value["text"]
    if not all(
        isinstance(item, str) and item for item in (message_id, sender_id, text)
    ):
        raise TypeError("commons message strings must not be empty")
    if sender_id not in agent_ids:
        raise ValueError("commons message sender is not configured")
    if len(text) > message_max_length:
        raise ValueError("commons message exceeds configured length")
    if _message_tick(value) < 0:
        raise ValueError("commons message tick must not be negative")
    return dict(value)
