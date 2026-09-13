from antfarm.application.scheduler import ScheduleContext, StableScheduler
from antfarm.domain import AgentId, Tick


def test_agents_are_selected_in_stable_order() -> None:
    selected = StableScheduler().select(
        ScheduleContext(
            tick=Tick(1),
            agent_ids=(AgentId("charlie"), AgentId("alice"), AgentId("bob")),
        )
    )

    assert selected == (AgentId("alice"), AgentId("bob"), AgentId("charlie"))
