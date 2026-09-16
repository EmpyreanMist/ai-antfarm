from random import Random
from typing import cast

from antfarm.domain import (
    ActionProposal,
    AgentId,
    EconomicSituation,
    InformationVisibility,
    PublicAgentProfile,
    Tick,
)
from antfarm.domain.json_values import JsonObject
from antfarm.environments import CommonsEnvironment


def test_social_observation_contains_conversation_context() -> None:
    alice = AgentId("alice")
    environment = CommonsEnvironment(
        initial_resource=0,
        initial_endowment=0,
        agent_ids=(alice,),
        social=True,
        topic="What should we do?",
        situation="The group is stranded.",
    )

    state = environment.observe(alice, Tick(1)).state

    assert state["conversation_topic"] == "What should we do?"
    assert state["conversation_situation"] == "The group is stranded."


def test_harvest_and_contribute_preserve_resource_accounting() -> None:
    alice = AgentId("alice")
    bob = AgentId("bob")
    environment = CommonsEnvironment(
        initial_resource=5,
        initial_endowment=1,
        agent_ids=(alice, bob),
    )

    assert dict(environment.observe(alice, Tick(1)).state) == {
        "resource": 5,
        "own_holding": 1,
    }
    harvest = environment.validate(
        ActionProposal(actor_id=alice, kind="harvest", parameters={"amount": 3})
    )
    assert harvest.action is not None
    environment.apply(harvest.action, Random(1), Tick(1))

    unavailable = environment.validate(
        ActionProposal(actor_id=bob, kind="harvest", parameters={"amount": 3})
    )
    assert unavailable.action is None
    assert unavailable.reason == "amount exceeds available resource"

    contribute = environment.validate(
        ActionProposal(actor_id=alice, kind="contribute", parameters={"amount": 2})
    )
    assert contribute.action is not None
    environment.apply(contribute.action, Random(1), Tick(1))

    assert dict(environment.snapshot()) == {
        "resource": 4,
        "holdings": {"alice": 2, "bob": 1},
    }


def test_snapshot_restore_preserves_agent_scoped_state() -> None:
    alice = AgentId("alice")
    original = CommonsEnvironment(
        initial_resource=5,
        initial_endowment=0,
        agent_ids=(alice,),
    )
    harvest = original.validate(
        ActionProposal(actor_id=alice, kind="harvest", parameters={"amount": 2})
    )
    assert harvest.action is not None
    original.apply(harvest.action, Random(1), Tick(1))
    restored = CommonsEnvironment(
        initial_resource=0,
        initial_endowment=0,
        agent_ids=(alice,),
    )

    restored.restore(original.snapshot())

    assert restored.snapshot() == original.snapshot()
    assert restored.observe(alice, Tick(2)) == original.observe(alice, Tick(2))


def test_inequality_and_public_possessions_are_observer_scoped() -> None:
    alice = AgentId("alice")
    bob = AgentId("bob")
    environment = CommonsEnvironment(
        initial_resource=5,
        initial_endowment=1,
        initial_holdings={alice: 9},
        agent_ids=(alice, bob),
        social=True,
        public_profiles={
            alice: PublicAgentProfile(economics=EconomicSituation(money=100)),
        },
        visibility={
            alice: InformationVisibility(wealth="public", possessions="public"),
            bob: InformationVisibility(),
        },
    )

    alice_observation = environment.observe(alice, Tick(1)).state
    bob_observation = environment.observe(bob, Tick(1)).state

    assert alice_observation["own_holding"] == 9
    assert alice_observation["roster"] == ({"id": "alice"}, {"id": "bob"})
    assert bob_observation["own_holding"] == 1
    assert bob_observation["roster"] == (
        {
            "id": "alice",
            "public_profile": {
                "economics": {"money": 100, "holding": 9}
            },
        },
        {"id": "bob"},
    )

    harvest = environment.validate(
        ActionProposal(actor_id=alice, kind="harvest", parameters={"amount": 1})
    )
    assert harvest.action is not None
    environment.apply(harvest.action, Random(1), Tick(1))
    updated_roster = environment.observe(bob, Tick(2)).state["roster"]
    assert updated_roster == (
        {
            "id": "alice",
            "public_profile": {
                "economics": {"money": 100, "holding": 10}
            },
        },
        {"id": "bob"},
    )


def test_invalid_commons_proposals_do_not_change_state() -> None:
    alice = AgentId("alice")
    environment = CommonsEnvironment(
        initial_resource=2,
        initial_endowment=0,
        agent_ids=(alice,),
    )
    expected = environment.snapshot()
    proposals = (
        ActionProposal(actor_id=alice, kind="increment", parameters={"amount": 1}),
        ActionProposal(actor_id=alice, kind="harvest", parameters={"amount": 0}),
        ActionProposal(actor_id=alice, kind="contribute", parameters={"amount": 1}),
    )

    assert all(environment.validate(proposal).action is None for proposal in proposals)
    assert environment.snapshot() == expected


def test_social_messages_are_authentic_bounded_and_visible_next_tick() -> None:
    alice = AgentId("alice")
    bob = AgentId("bob")
    environment = CommonsEnvironment(
        initial_resource=2,
        initial_endowment=0,
        agent_ids=(alice, bob),
        social=True,
        message_max_length=5,
        history_limit=2,
        roster_limit=1,
    )
    speech = environment.validate(
        ActionProposal(actor_id=alice, kind="say", parameters={"text": "hello"})
    )
    assert speech.action is not None

    result = environment.apply(speech.action, Random(1), Tick(1))

    message = cast(JsonObject, result.payload["message"])
    assert dict(message) == {
        "id": "message-1",
        "sender_id": "alice",
        "tick": 1,
        "text": "hello",
    }
    assert environment.observe(bob, Tick(1)).state["recent_messages"] == ()
    assert environment.observe(bob, Tick(1)).state["roster"] == ({"id": "bob"},)
    assert environment.observe(alice, Tick(2)).state["recent_messages"] == (message,)
    deliveries = environment.memory_deliveries(speech.action, result)
    assert set(deliveries) == {alice, bob}
    assert deliveries[bob][0].content == message

    for tick, text in ((2, "two"), (3, "three")):
        next_speech = environment.validate(
            ActionProposal(actor_id=bob, kind="say", parameters={"text": text})
        )
        assert next_speech.action is not None
        environment.apply(next_speech.action, Random(1), Tick(tick))

    recent = cast(
        tuple[JsonObject, ...],
        environment.observe(alice, Tick(4)).state["recent_messages"],
    )
    assert [item["id"] for item in recent] == ["message-2", "message-3"]

    spoofed = environment.validate(
        ActionProposal(
            actor_id=alice,
            kind="say",
            parameters={"text": "hello", "sender_id": "bob"},
        )
    )
    too_long = environment.validate(
        ActionProposal(actor_id=alice, kind="say", parameters={"text": "longer"})
    )
    empty = environment.validate(
        ActionProposal(actor_id=alice, kind="say", parameters={"text": "  "})
    )
    assert not spoofed.accepted
    assert not too_long.accepted
    assert not empty.accepted


def test_social_snapshot_restore_preserves_delivery_cursor() -> None:
    alice = AgentId("alice")
    original = CommonsEnvironment(
        initial_resource=1,
        initial_endowment=0,
        agent_ids=(alice,),
        social=True,
    )
    speech = original.validate(
        ActionProposal(actor_id=alice, kind="say", parameters={"text": "first"})
    )
    assert speech.action is not None
    original.apply(speech.action, Random(1), Tick(1))
    restored = CommonsEnvironment(
        initial_resource=0,
        initial_endowment=0,
        agent_ids=(alice,),
        social=True,
    )

    restored.restore(original.snapshot())
    second = restored.validate(
        ActionProposal(actor_id=alice, kind="say", parameters={"text": "second"})
    )
    assert second.action is not None
    result = restored.apply(second.action, Random(1), Tick(2))

    message = cast(JsonObject, result.payload["message"])
    assert message["id"] == "message-2"
