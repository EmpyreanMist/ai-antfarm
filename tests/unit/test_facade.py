import asyncio
from collections.abc import Mapping
from pathlib import Path

import pytest

from antfarm.adapters.storage import SQLiteStorage
from antfarm.application import (
    AgentQuery,
    ApplicationError,
    ErrorCode,
    EventQuery,
    RunMode,
    RunStatus,
)
from antfarm.config import load_scenario
from antfarm.config.schema import ScenarioConfig
from antfarm.domain import RunId
from antfarm.facade import (
    AntFarmApplication,
    StartRunCommand,
    StopRunCommand,
)
from antfarm.population import RuntimeOverrides

EXAMPLES = Path("scenarios/examples")


def _memory_config(path: str, *, run_id: str) -> ScenarioConfig:
    source = load_scenario(EXAMPLES / path)
    data = source.model_dump(mode="json", exclude_none=True)
    run = data["run"]
    assert isinstance(run, dict)
    run["id"] = run_id
    data["storage"] = {"kind": "memory"}
    return ScenarioConfig.model_validate(data)


def test_resolved_agents_are_inspectable_without_starting_a_run() -> None:
    application = AntFarmApplication()
    source = _memory_config("society-mixed.yaml", run_id="inspect-mixed")

    resolved = application.resolve_population(source, RuntimeOverrides(seed=29))
    agents = application.inspect_resolved_agents(resolved)

    assert [agent.agent_id for agent in agents] == ["alice", "worker-001"]
    alice = agents[0]
    profile = alice.configuration["profile"]
    assert isinstance(profile, Mapping)
    assert profile["private_information"] == (
        "Needs the extra income to repay a private debt",
    )
    assert "private_information" not in alice.public
    assert alice.public["economics"] == {
        "money": 90,
        "recurring_income": 8,
        "occupation": "cooperative manager",
    }
    assert resolved.runtime_overrides == {"seed": 29}


def test_scenario_loading_uses_stable_error_contract() -> None:
    with pytest.raises(ApplicationError) as invalid:
        AntFarmApplication().load_scenario("does-not-exist.yaml")

    assert invalid.value.code is ErrorCode.INVALID_SCENARIO
    assert invalid.value.details["error_type"] == "FileNotFoundError"


def test_facade_runs_and_reads_run_agents_snapshot_and_events() -> None:
    async def exercise() -> None:
        application = AntFarmApplication()
        source = _memory_config("society-manual.yaml", run_id="facade-run")
        resolved = application.resolve_population(
            source,
            RuntimeOverrides(seed=41, model_assignments={"alice": "shared"}),
        )

        handle = application.start_run(resolved)
        snapshot = await application.wait_run(handle.run_id)

        stored = application.read_run(handle.run_id)
        assert stored is not None
        assert stored.metadata.seed == 41
        assert stored.metadata.runtime_overrides == {
            "seed": 41,
            "model_assignments": {"alice": "shared"},
        }
        assert snapshot.tick == 2
        assert application.read_snapshot(handle.run_id) == snapshot
        assert len(application.read_agents(handle.run_id)) == 2
        assert application.read_events(handle.run_id)
        assert application.read_events(handle.run_id, after=1)[0].sequence == 2

    asyncio.run(exercise())


def test_stop_run_returns_last_atomic_snapshot() -> None:
    async def exercise() -> None:
        application = AntFarmApplication()
        resolved = application.resolve_population(
            _memory_config("society-manual.yaml", run_id="stopped-run")
        )
        handle = application.start_run(
            resolved,
            continuous=True,
            tick_seconds=60,
        )
        await asyncio.sleep(0)

        snapshot = await application.stop_run(RunId("stopped-run"))

        assert snapshot.tick in {0, 1}
        assert application.read_run_state(handle.run_id).status is RunStatus.STOPPED
        persisted = application.read_snapshot(handle.run_id)
        if snapshot.tick == 0:
            assert persisted is None
        else:
            assert persisted == snapshot

    asyncio.run(exercise())


def test_historical_agents_use_persisted_resolution_not_changed_source(
    tmp_path: Path,
) -> None:
    database = tmp_path / "historical.db"

    async def create_run() -> tuple[object, ...]:
        application = AntFarmApplication()
        source = load_scenario(EXAMPLES / "society-randomized.yaml")
        data = source.model_dump(mode="json", exclude_none=True)
        data["storage"] = {"kind": "sqlite", "path": str(database)}
        resolved = application.resolve_population(
            ScenarioConfig.model_validate(data), RuntimeOverrides(seed=111)
        )
        expected = tuple(
            agent.configuration
            for agent in application.inspect_resolved_agents(resolved)
        )
        handle = application.start_run(resolved)
        await application.wait_run(handle.run_id)
        return expected

    expected = asyncio.run(create_run())
    changed_source = load_scenario(EXAMPLES / "society-randomized.yaml")
    changed = AntFarmApplication().resolve_population(
        changed_source, RuntimeOverrides(seed=222)
    )
    changed_agents = tuple(
        agent.configuration
        for agent in AntFarmApplication().inspect_resolved_agents(changed)
    )
    assert changed_agents != expected

    with SQLiteStorage(database) as storage:
        history = AntFarmApplication(storage)
        stored = history.read_run("society-randomized")
        agents = history.read_agents("society-randomized")

    assert stored is not None
    assert stored.metadata.runtime_overrides == {"seed": 111}
    assert tuple(agent.configuration for agent in agents) == expected


def test_command_lifecycle_has_stable_states_and_conflict_errors() -> None:
    async def exercise() -> None:
        application = AntFarmApplication()
        resolved = application.resolve_population(
            _memory_config("society-manual.yaml", run_id="command-run")
        )

        started = application.start(StartRunCommand(resolved))
        assert started.status is RunStatus.RUNNING
        assert started.mode is RunMode.BOUNDED

        with pytest.raises(ApplicationError) as duplicate:
            application.start(StartRunCommand(resolved))
        assert duplicate.value.code is ErrorCode.CONFLICT

        await application.wait_run(started.run_id)
        completed = application.read_run_state(started.run_id)
        assert completed.status is RunStatus.COMPLETED
        assert completed.tick == 2

        with pytest.raises(ApplicationError) as terminal_stop:
            await application.stop(StopRunCommand(started.run_id))
        assert terminal_stop.value.code is ErrorCode.INVALID_STATE

    asyncio.run(exercise())


def test_queries_are_bounded_filtered_and_transport_neutral() -> None:
    async def exercise() -> None:
        application = AntFarmApplication()
        resolved = application.resolve_population(
            _memory_config("society-manual.yaml", run_id="query-run")
        )
        handle = application.start_run(resolved)
        await application.wait_run(handle.run_id)

        first = application.query_events(EventQuery("query-run", limit=2))
        assert len(first.items) == 2
        assert first.next_after == first.items[-1].sequence
        assert isinstance(first.items[0].run_id, str)
        assert isinstance(first.items[0].tick, int)

        second = application.query_events(
            EventQuery("query-run", after=first.next_after or 0, limit=2)
        )
        assert second.items
        assert second.items[0].sequence > first.items[-1].sequence

        applied = application.query_events(
            EventQuery("query-run", limit=100, kinds=frozenset({"action.applied"}))
        )
        assert applied.items
        assert {event.kind for event in applied.items} == {"action.applied"}

        alice_tick_one = application.query_events(
            EventQuery(
                "query-run",
                limit=100,
                actor_id="alice",
                from_tick=1,
                to_tick=1,
            )
        )
        assert alice_tick_one.items
        assert all(event.actor_id == "alice" for event in alice_tick_one.items)
        assert all(event.tick == 1 for event in alice_tick_one.items)

        agents = application.query_agents(AgentQuery("query-run", limit=1))
        assert len(agents.items) == 1
        assert agents.next_offset == 1
        assert application.query_snapshot("query-run") is not None

        with pytest.raises(ApplicationError) as invalid_page:
            EventQuery("query-run", limit=0)
        assert invalid_page.value.code is ErrorCode.INVALID_ARGUMENT

        with pytest.raises(ApplicationError) as missing:
            application.query_run("missing")
        assert missing.value.code is ErrorCode.NOT_FOUND

    asyncio.run(exercise())


def test_distinct_run_ids_execute_concurrently() -> None:
    async def exercise() -> None:
        application = AntFarmApplication()
        first = application.start(
            StartRunCommand(_memory_config("society-manual.yaml", run_id="first"))
        )
        second = application.start(
            StartRunCommand(_memory_config("society-manual.yaml", run_id="second"))
        )

        await asyncio.gather(
            application.wait_run(first.run_id),
            application.wait_run(second.run_id),
        )

        assert application.read_run_state(first.run_id).status is RunStatus.COMPLETED
        assert application.read_run_state(second.run_id).status is RunStatus.COMPLETED

    asyncio.run(exercise())


def test_event_subscription_projects_committed_events_and_can_cancel() -> None:
    async def exercise() -> None:
        application = AntFarmApplication()
        resolved = application.resolve_population(
            _memory_config("society-manual.yaml", run_id="subscription-run")
        )
        handle = application.start_run(resolved)
        observed: list[tuple[str, int]] = []
        subscription = application.subscribe_events(
            handle.run_id,
            {"action.applied"},
            lambda event: observed.append((event.kind, event.sequence)),
        )

        await application.wait_run(handle.run_id)
        subscription.cancel()

        assert observed
        assert {kind for kind, _ in observed} == {"action.applied"}
        assert [sequence for _, sequence in observed] == sorted(
            sequence for _, sequence in observed
        )

    asyncio.run(exercise())
