import sqlite3
from pathlib import Path
from random import Random

import pytest

from antfarm.adapters.storage import SQLiteStorage
from antfarm.domain import (
    AgentId,
    Event,
    EventSequence,
    RunId,
    RunMetadata,
    SimulationSnapshot,
    Tick,
)


def _event(
    run_id: RunId,
    sequence: int,
    *,
    event_id: str | None = None,
    kind: str = "test.event",
    actor_id: AgentId | None = None,
) -> Event:
    return Event(
        schema_version=1,
        event_id=event_id or f"{run_id}:{sequence}",
        run_id=run_id,
        sequence=EventSequence(sequence),
        tick=Tick(sequence),
        kind=kind,
        actor_id=actor_id,
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


def test_run_record_preserves_resolved_scenario_and_runtime_overrides(
    tmp_path: Path,
) -> None:
    database = tmp_path / "inspection.db"
    run_id = RunId("inspectable-run")
    scenario = {
        "schema_version": 1,
        "run": {"id": str(run_id), "seed": 23},
        "profiles": {"resolved-alice": {"economics": {"money": 77}}},
    }
    metadata = RunMetadata(
        run_id=run_id,
        seed=23,
        runtime_overrides={"seed": 23, "model": "local-model"},
    )

    with SQLiteStorage(database) as storage:
        storage.create_run(metadata, scenario)

    with SQLiteStorage(database) as reopened:
        stored = reopened.read_run(run_id)

    assert stored is not None
    assert stored.metadata == metadata
    assert stored.scenario == scenario


def test_existing_database_is_migrated_for_runtime_override_provenance(
    tmp_path: Path,
) -> None:
    database = tmp_path / "legacy.db"
    connection = sqlite3.connect(database)
    connection.execute(
        "CREATE TABLE runs (run_id TEXT PRIMARY KEY, seed INTEGER NOT NULL, "
        "scenario_json TEXT NOT NULL)"
    )
    connection.execute(
        "INSERT INTO runs VALUES (?, ?, ?)",
        ("legacy-run", 7, '{"schema_version":1}'),
    )
    connection.commit()
    connection.close()

    with SQLiteStorage(database) as storage:
        stored = storage.read_run(RunId("legacy-run"))

    assert stored is not None
    assert stored.metadata.runtime_overrides == {}


def test_event_query_filters_and_limits_are_applied_in_sqlite(
    tmp_path: Path,
) -> None:
    database = tmp_path / "filtered.db"
    run_id = RunId("filtered-run")
    events = (
        _event(run_id, 1, kind="action.applied", actor_id=AgentId("alice")),
        _event(run_id, 2, kind="action.rejected", actor_id=AgentId("bob")),
        _event(run_id, 3, kind="action.applied", actor_id=AgentId("alice")),
    )

    with SQLiteStorage(database) as storage:
        storage.create_run(RunMetadata(run_id=run_id, seed=5), {})
        storage.commit_step(run_id, _snapshot(3), events)

        selected = tuple(
            storage.read_events(
                run_id,
                kinds=frozenset({"action.applied"}),
                actor_id="alice",
                from_tick=2,
                to_tick=3,
                limit=1,
            )
        )

    assert selected == events[2:]


def test_sqlite_lists_runs_in_reverse_creation_order(tmp_path: Path) -> None:
    database = tmp_path / "history.db"
    with SQLiteStorage(database) as storage:
        storage.create_run(RunMetadata(run_id=RunId("first"), seed=1), {})
        storage.create_run(RunMetadata(run_id=RunId("second"), seed=2), {})

        page = storage.list_runs(limit=1)

    assert [str(run.metadata.run_id) for run in page] == ["second"]
