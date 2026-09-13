import sqlite3
from pathlib import Path
from random import Random

import pytest

from antfarm.adapters.storage import SQLiteStorage
from antfarm.domain import (
    Event,
    EventSequence,
    RunId,
    RunMetadata,
    SimulationSnapshot,
    Tick,
)


def _event(run_id: RunId, sequence: int, *, event_id: str | None = None) -> Event:
    return Event(
        schema_version=1,
        event_id=event_id or f"{run_id}:{sequence}",
        run_id=run_id,
        sequence=EventSequence(sequence),
        tick=Tick(sequence),
        kind="test.event",
        actor_id=None,
        causation_id=None,
        payload={"sequence": sequence},
    )


def _snapshot(sequence: int) -> SimulationSnapshot:
    random_state = Random(sequence).getstate()
    return SimulationSnapshot(
        tick=Tick(sequence),
        world={"value": sequence},
        memory={"alice": ({"kind": "result", "content": {"value": sequence}},)},
        scheduler={"last_tick": sequence},
        metrics={"action_count": {"total": sequence}},
        engine={"event_sequence": sequence, "random_state": random_state},
    )


def test_reopen_restores_latest_checkpoint_and_ordered_events(
    tmp_path: Path,
) -> None:
    database = tmp_path / "runs.db"
    run_id = RunId("persistent-run")
    expected_events = (_event(run_id, 1), _event(run_id, 2))
    expected_snapshot = _snapshot(2)

    with SQLiteStorage(database) as storage:
        storage.create_run(RunMetadata(run_id=run_id, seed=17), {"schema_version": 1})
        storage.commit_step(run_id, expected_snapshot, expected_events)

    with SQLiteStorage(database) as reopened:
        checkpoint = reopened.load_latest(run_id)
        assert checkpoint is not None
        assert checkpoint.snapshot == expected_snapshot
        assert tuple(reopened.read_events(run_id)) == expected_events
        assert tuple(reopened.read_events(run_id, after=1)) == expected_events[1:]


def test_failed_batch_rolls_back_events_and_checkpoint(tmp_path: Path) -> None:
    database = tmp_path / "rollback.db"
    run_id = RunId("rollback-run")

    with SQLiteStorage(database) as storage:
        storage.create_run(RunMetadata(run_id=run_id, seed=9), {})
        storage.commit_step(run_id, _snapshot(1), (_event(run_id, 1),))
        duplicate_id_batch = (
            _event(run_id, 2, event_id="duplicate"),
            _event(run_id, 3, event_id="duplicate"),
        )

        with pytest.raises(sqlite3.IntegrityError):
            storage.commit_step(run_id, _snapshot(3), duplicate_id_batch)

        assert tuple(storage.read_events(run_id)) == (_event(run_id, 1),)
        checkpoint = storage.load_latest(run_id)
        assert checkpoint is not None
        assert checkpoint.snapshot == _snapshot(1)


def test_non_monotonic_event_batch_is_rejected(tmp_path: Path) -> None:
    database = tmp_path / "sequence.db"
    run_id = RunId("sequence-run")

    with SQLiteStorage(database) as storage:
        storage.create_run(RunMetadata(run_id=run_id, seed=3), {})
        with pytest.raises(ValueError, match="contiguous and monotonic"):
            storage.commit_step(run_id, _snapshot(2), (_event(run_id, 2),))

        assert tuple(storage.read_events(run_id)) == ()
        assert storage.load_latest(run_id) is None
