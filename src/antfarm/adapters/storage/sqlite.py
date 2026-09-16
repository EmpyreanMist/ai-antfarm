"""Single-writer SQLite storage with atomic event/checkpoint commits."""

import json
import sqlite3
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import cast

from antfarm.domain.json_values import JsonObject, freeze_object, thaw_json
from antfarm.domain.models import (
    Event,
    RunId,
    RunMetadata,
    SimulationSnapshot,
    StoredCheckpoint,
    StoredRun,
)
from antfarm.domain.serialization import (
    event_from_data,
    event_to_data,
    snapshot_from_data,
    snapshot_to_data,
)


class SQLiteStorage:
    """Persist one run writer while allowing data to survive process restarts."""

    def __init__(self, path: str | Path) -> None:
        # FastAPI may create the adapter before handing lifecycle ownership to
        # its event-loop thread. Storage remains single-writer and serialized.
        self._connection = sqlite3.connect(Path(path), check_same_thread=False)
        self._connection.execute("PRAGMA foreign_keys = ON")
        self._connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS runs (
                run_id TEXT PRIMARY KEY,
                seed INTEGER NOT NULL,
                scenario_json TEXT NOT NULL,
                runtime_overrides_json TEXT NOT NULL DEFAULT '{}'
            );
            CREATE TABLE IF NOT EXISTS events (
                run_id TEXT NOT NULL,
                sequence INTEGER NOT NULL CHECK (sequence > 0),
                event_id TEXT NOT NULL,
                event_json TEXT NOT NULL,
                PRIMARY KEY (run_id, sequence),
                UNIQUE (run_id, event_id),
                FOREIGN KEY (run_id) REFERENCES runs(run_id)
            );
            CREATE TABLE IF NOT EXISTS checkpoints (
                run_id TEXT PRIMARY KEY,
                event_sequence INTEGER NOT NULL CHECK (event_sequence >= 0),
                snapshot_json TEXT NOT NULL,
                FOREIGN KEY (run_id) REFERENCES runs(run_id)
            );
            """
        )
        columns = {
            cast(str, row[1])
            for row in self._connection.execute("PRAGMA table_info(runs)").fetchall()
        }
        if "runtime_overrides_json" not in columns:
            with self._connection:
                self._connection.execute(
                    "ALTER TABLE runs ADD COLUMN runtime_overrides_json "
                    "TEXT NOT NULL DEFAULT '{}'"
                )

    def close(self) -> None:
        self._connection.close()

    def __enter__(self) -> "SQLiteStorage":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def create_run(self, metadata: RunMetadata, scenario: Mapping[str, object]) -> None:
        scenario_data = thaw_json(freeze_object(scenario))
        try:
            with self._connection:
                self._connection.execute(
                    """
                    INSERT INTO runs
                        (run_id, seed, scenario_json, runtime_overrides_json)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        str(metadata.run_id),
                        metadata.seed,
                        _encode_json(scenario_data),
                        _encode_json(thaw_json(metadata.runtime_overrides)),
                    ),
                )
        except sqlite3.IntegrityError as error:
            raise ValueError(f"run already exists: {metadata.run_id}") from error

    def commit_step(
        self,
        run_id: RunId,
        snapshot: SimulationSnapshot,
        events: Sequence[Event],
    ) -> None:
        if not events:
            raise ValueError("a step must contain at least one event")
        if any(event.run_id != run_id for event in events):
            raise ValueError("all events must belong to the committed run")

        sequences = [int(event.sequence) for event in events]
        with self._connection:
            run_exists = self._connection.execute(
                "SELECT 1 FROM runs WHERE run_id = ?", (str(run_id),)
            ).fetchone()
            if run_exists is None:
                raise ValueError(f"unknown run: {run_id}")
            row = self._connection.execute(
                "SELECT COALESCE(MAX(sequence), 0) FROM events WHERE run_id = ?",
                (str(run_id),),
            ).fetchone()
            if row is None:
                raise RuntimeError("event sequence query returned no result")
            previous_sequence = cast(int, row[0])
            expected = list(
                range(previous_sequence + 1, previous_sequence + len(events) + 1)
            )
            if sequences != expected:
                raise ValueError("event sequences must be contiguous and monotonic")
            engine_sequence = snapshot.engine.get("event_sequence")
            if engine_sequence != sequences[-1]:
                raise ValueError("checkpoint sequence must match the event batch")

            self._connection.executemany(
                """
                INSERT INTO events (run_id, sequence, event_id, event_json)
                VALUES (?, ?, ?, ?)
                """,
                (
                    (
                        str(run_id),
                        int(event.sequence),
                        event.event_id,
                        _encode_json(event_to_data(event)),
                    )
                    for event in events
                ),
            )
            self._connection.execute(
                """
                INSERT INTO checkpoints (run_id, event_sequence, snapshot_json)
                VALUES (?, ?, ?)
                ON CONFLICT(run_id) DO UPDATE SET
                    event_sequence = excluded.event_sequence,
                    snapshot_json = excluded.snapshot_json
                """,
                (
                    str(run_id),
                    sequences[-1],
                    _encode_json(snapshot_to_data(snapshot)),
                ),
            )

    def load_latest(self, run_id: RunId) -> StoredCheckpoint | None:
        row = self._connection.execute(
            "SELECT snapshot_json FROM checkpoints WHERE run_id = ?",
            (str(run_id),),
        ).fetchone()
        if row is None:
            return None
        data = _decode_object(cast(str, row[0]))
        return StoredCheckpoint(run_id=run_id, snapshot=snapshot_from_data(data))

    def read_run(self, run_id: RunId) -> StoredRun | None:
        row = self._connection.execute(
            """
            SELECT seed, scenario_json, runtime_overrides_json
            FROM runs WHERE run_id = ?
            """,
            (str(run_id),),
        ).fetchone()
        if row is None:
            return None
        return StoredRun(
            metadata=RunMetadata(
                run_id=run_id,
                seed=cast(int, row[0]),
                runtime_overrides=_decode_object(cast(str, row[2])),
            ),
            scenario=_decode_object(cast(str, row[1])),
        )

    def list_runs(self, *, offset: int = 0, limit: int = 100) -> tuple[StoredRun, ...]:
        rows = self._connection.execute(
            """
            SELECT run_id, seed, scenario_json, runtime_overrides_json
            FROM runs ORDER BY rowid DESC LIMIT ? OFFSET ?
            """,
            (limit, offset),
        ).fetchall()
        return tuple(
            StoredRun(
                metadata=RunMetadata(
                    run_id=RunId(cast(str, row[0])),
                    seed=cast(int, row[1]),
                    runtime_overrides=_decode_object(cast(str, row[3])),
                ),
                scenario=_decode_object(cast(str, row[2])),
            )
            for row in rows
        )

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
        clauses = ["run_id = ?", "sequence > ?"]
        parameters: list[object] = [str(run_id), after]
        if kinds:
            placeholders = ", ".join("?" for _ in kinds)
            clauses.append(f"json_extract(event_json, '$.kind') IN ({placeholders})")
            parameters.extend(sorted(kinds))
        if actor_id is not None:
            clauses.append("json_extract(event_json, '$.actor_id') = ?")
            parameters.append(actor_id)
        if from_tick is not None:
            clauses.append("json_extract(event_json, '$.tick') >= ?")
            parameters.append(from_tick)
        if to_tick is not None:
            clauses.append("json_extract(event_json, '$.tick') <= ?")
            parameters.append(to_tick)
        query = (
            "SELECT event_json FROM events WHERE "
            + " AND ".join(clauses)
            + " ORDER BY sequence"
        )
        if limit is not None:
            query += " LIMIT ?"
            parameters.append(limit)
        rows = self._connection.execute(query, parameters).fetchall()
        return tuple(
            event_from_data(_decode_object(cast(str, row[0]))) for row in rows
        )


def _encode_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _decode_object(value: str) -> JsonObject:
    decoded = json.loads(value)
    if not isinstance(decoded, dict):
        raise TypeError("stored JSON value must be an object")
    return freeze_object(cast(dict[str, object], decoded))
