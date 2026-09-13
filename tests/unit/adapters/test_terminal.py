import io

from antfarm.adapters.terminal import LiveTerminalObserver
from antfarm.domain import AgentId, Event, EventSequence, RunId, Tick


def test_committed_failure_remains_visible_in_plain_output() -> None:
    output = io.StringIO()
    observer = LiveTerminalObserver(output)
    event = Event(
        schema_version=1,
        event_id="live:1",
        run_id=RunId("live"),
        sequence=EventSequence(1),
        tick=Tick(4),
        kind="cognition.failed",
        actor_id=AgentId("alice"),
        causation_id=None,
        payload={"reason": "ConnectionError"},
    )

    observer.observe(event)

    assert output.getvalue() == (
        "[tick 4] Alice cognition failed: ConnectionError.\n"
    )
