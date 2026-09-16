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

    def list_runs(
        self, *, offset: int = 0, limit: int = 100
    ) -> Sequence[StoredRun]: ...

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
    ) -> Iterable[Event]: ...
