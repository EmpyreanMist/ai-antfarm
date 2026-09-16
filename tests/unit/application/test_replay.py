from dataclasses import replace
from pathlib import Path

import pytest

from antfarm.application import ApplicationError
from antfarm.application.replay import replay_events
from antfarm.composition import build_environment, compose
from antfarm.config import load_scenario
from antfarm.custom import load_custom_definition
from antfarm.custom.runtime import DeclarativeEnvironment, compose_custom
from antfarm.domain import EventSequence, RunLimit


@pytest.mark.asyncio
async def test_society_replay_reconstructs_checkpoint_without_a_model_call() -> None:
    config = load_scenario(Path("scenarios/examples/minimal.yaml"))
    simulation = compose(config)
    result = await simulation.engine.run(RunLimit(config.run.ticks))

    replay = replay_events(
        environment=build_environment(config),
        seed=config.run.seed,
        events=result.events,
        checkpoint=result.snapshot,
    )

    assert replay.frames[-1].world == result.snapshot.world
    assert replay.frames[-1].tick == config.run.ticks
    await simulation.close()


@pytest.mark.asyncio
async def test_custom_replay_reconstructs_checkpoint() -> None:
    definition = load_custom_definition(
        Path("scenarios/examples/custom-warehouse.yaml")
    )
    simulation = compose_custom(definition)
    result = await simulation.engine.run(RunLimit(definition.run.ticks))

    replay = replay_events(
        environment=DeclarativeEnvironment(definition),
        seed=definition.run.seed,
        events=result.events,
        checkpoint=result.snapshot,
    )

    assert replay.final_world == result.snapshot.world
    await simulation.close()


@pytest.mark.asyncio
async def test_replay_rejects_incomplete_or_checkpoint_incompatible_history() -> None:
    config = load_scenario(Path("scenarios/examples/minimal.yaml"))
    simulation = compose(config)
    result = await simulation.engine.run(RunLimit(config.run.ticks))
    broken = list(result.events)
    broken[1] = replace(broken[1], sequence=EventSequence(99))

    with pytest.raises(ApplicationError, match="sequence"):
        replay_events(
            environment=build_environment(config),
            seed=config.run.seed,
            events=broken,
            checkpoint=result.snapshot,
        )
    with pytest.raises(ApplicationError, match="final state"):
        replay_events(
            environment=build_environment(config),
            seed=config.run.seed,
            events=result.events,
            checkpoint=replace(result.snapshot, world={"value": -1}),
        )
    await simulation.close()
