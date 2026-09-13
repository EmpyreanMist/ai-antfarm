"""Atomic step persistence boundary."""

from collections.abc import Mapping, Sequence
from typing import Protocol

from antfarm.domain.models import Event, RunId, SimulationSnapshot


class Storage(Protocol):
    def create_run(self, run_id: RunId, scenario: Mapping[str, object]) -> None: ...

    def commit_step(
        self,
        run_id: RunId,
        snapshot: SimulationSnapshot,
        events: Sequence[Event],
    ) -> None: ...
