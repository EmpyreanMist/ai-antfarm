import asyncio
from collections.abc import Mapping
from pathlib import Path

from antfarm.adapters.storage import SQLiteStorage
from antfarm.config import load_scenario
from antfarm.config.schema import ScenarioConfig
from antfarm.domain import RunId
from antfarm.facade import AntFarmApplication
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
