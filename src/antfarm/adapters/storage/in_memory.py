"""M0.1 storage adapter; durable SQLite is deliberately deferred."""

from collections.abc import Mapping, Sequence

from antfarm.domain.models import Event, RunId, SimulationSnapshot


class InMemoryStorage:
    def __init__(self) -> None:
        self.scenarios: dict[RunId, Mapping[str, object]] = {}
        self.snapshots: dict[RunId, SimulationSnapshot] = {}
        self.events: dict[RunId, list[Event]] = {}

    def create_run(self, run_id: RunId, scenario: Mapping[str, object]) -> None:
        self.scenarios[run_id] = dict(scenario)
        self.events[run_id] = []

    def commit_step(
        self,
        run_id: RunId,
        snapshot: SimulationSnapshot,
        events: Sequence[Event],
    ) -> None:
        if run_id not in self.scenarios:
            raise ValueError(f"unknown run: {run_id}")
        self.snapshots[run_id] = snapshot
        self.events[run_id].extend(events)
