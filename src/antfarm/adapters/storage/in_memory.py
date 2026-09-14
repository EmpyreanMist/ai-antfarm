"""Process-local implementation of the storage boundary."""

from collections.abc import Iterable, Mapping, Sequence
from itertools import islice

from antfarm.domain.json_values import freeze_object
from antfarm.domain.models import (
    Event,
    RunId,
    RunMetadata,
    SimulationSnapshot,
    StoredCheckpoint,
    StoredRun,
)


class InMemoryStorage:
    def __init__(self) -> None:
        self.scenarios: dict[RunId, Mapping[str, object]] = {}
        self.metadata: dict[RunId, RunMetadata] = {}
        self.snapshots: dict[RunId, SimulationSnapshot] = {}
        self.events: dict[RunId, list[Event]] = {}

    def close(self) -> None:
        """The process-local adapter owns no external resources."""

    def create_run(self, metadata: RunMetadata, scenario: Mapping[str, object]) -> None:
        self.metadata[metadata.run_id] = metadata
        self.scenarios[metadata.run_id] = dict(scenario)
        self.events[metadata.run_id] = []

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

    def load_latest(self, run_id: RunId) -> StoredCheckpoint | None:
        snapshot = self.snapshots.get(run_id)
        if snapshot is None:
            return None
        return StoredCheckpoint(run_id=run_id, snapshot=snapshot)

    def read_run(self, run_id: RunId) -> StoredRun | None:
        metadata = self.metadata.get(run_id)
        scenario = self.scenarios.get(run_id)
        if metadata is None or scenario is None:
            return None
        return StoredRun(metadata=metadata, scenario=freeze_object(scenario))

    def read_events(
        self,
        run_id: RunId,
        after: int = 0,
        *,
        limit: int | None = None,
        kinds: frozenset[str] = frozenset(),
        actor_id: str | None = None,
        from_tick: int | None = None,
        to_tick: int | None = None,
    ) -> Iterable[Event]:
        events = (
            event
            for event in self.events.get(run_id, ())
            if event.sequence > after
            and (not kinds or event.kind in kinds)
            and (actor_id is None or event.actor_id == actor_id)
            and (from_tick is None or event.tick >= from_tick)
            and (to_tick is None or event.tick <= to_tick)
        )
        if limit is None:
            return tuple(events)
        return tuple(islice(events, limit))
