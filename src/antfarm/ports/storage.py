"""Atomic step persistence boundary."""

from collections.abc import Iterable, Mapping, Sequence
from typing import Protocol

from antfarm.domain.models import (
    Event,
    RunId,
    RunMetadata,
    SimulationSnapshot,
    StoredCheckpoint,
    StoredRun,
)


class Storage(Protocol):
    def close(self) -> None: ...

    def create_run(
        self, metadata: RunMetadata, scenario: Mapping[str, object]
    ) -> None: ...

    def commit_step(
        self,
        run_id: RunId,
        snapshot: SimulationSnapshot,
        events: Sequence[Event],
    ) -> None: ...

    def load_latest(self, run_id: RunId) -> StoredCheckpoint | None: ...

    def read_run(self, run_id: RunId) -> StoredRun | None: ...

    def read_events(self, run_id: RunId, after: int = 0) -> Iterable[Event]: ...
