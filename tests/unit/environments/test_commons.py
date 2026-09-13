from random import Random

from antfarm.domain import ActionProposal, AgentId, Tick
from antfarm.environments import CommonsEnvironment


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
    environment.apply(harvest.action, Random(1))

    unavailable = environment.validate(
        ActionProposal(actor_id=bob, kind="harvest", parameters={"amount": 3})
    )
    assert unavailable.action is None
    assert unavailable.reason == "amount exceeds available resource"

    contribute = environment.validate(
        ActionProposal(actor_id=alice, kind="contribute", parameters={"amount": 2})
    )
    assert contribute.action is not None
    environment.apply(contribute.action, Random(1))

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
    original.apply(harvest.action, Random(1))
    restored = CommonsEnvironment(
        initial_resource=0,
        initial_endowment=0,
        agent_ids=(alice,),
    )

    restored.restore(original.snapshot())

    assert restored.snapshot() == original.snapshot()
    assert restored.observe(alice, Tick(2)) == original.observe(alice, Tick(2))


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
