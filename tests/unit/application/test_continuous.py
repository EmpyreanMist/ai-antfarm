import asyncio
from collections.abc import Sequence
from typing import cast

import pytest

from antfarm.application.continuous import ContinuousRunner
from antfarm.application.engine import SimulationEngine, StepResult
from antfarm.domain import Event, SimulationSnapshot, Tick


class _FakeClock:
    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def monotonic(self) -> float:
        return self.now

    async def sleep(self, delay: float) -> None:
        self.sleeps.append(delay)
        self.now += delay


class _FakeEngine:
    def __init__(self, clock: _FakeClock, step_duration: float) -> None:
        self.clock = clock
        self.step_duration = step_duration
        self.starts: list[float] = []
        self.tick = Tick(0)

    async def step(self) -> StepResult:
        self.starts.append(self.clock.monotonic())
        self.clock.now += self.step_duration
        self.tick = Tick(int(self.tick) + 1)
        return StepResult(snapshot=self.snapshot(), events=())

    def snapshot(self) -> SimulationSnapshot:
        return SimulationSnapshot(tick=self.tick, world={})


def _run_three_steps(
    clock: _FakeClock, engine: _FakeEngine, tick_seconds: float
) -> Sequence[Event]:
    batches: list[Sequence[Event]] = []
    runner = ContinuousRunner(
        cast(SimulationEngine, engine),
        tick_seconds=tick_seconds,
        clock=clock,
        on_batch=batches.append,
        should_stop=lambda: len(batches) == 3,
    )

    result = asyncio.run(runner.run())

    assert result.snapshot.tick == Tick(3)
    return tuple(event for batch in batches for event in batch)


def test_continuous_runner_paces_tick_starts_without_real_sleep() -> None:
    clock = _FakeClock()
    engine = _FakeEngine(clock, step_duration=0.25)

    events = _run_three_steps(clock, engine, tick_seconds=1.0)

    assert engine.starts == [0.0, 1.0, 2.0]
    assert clock.sleeps == [0.75, 0.75]
    assert events == ()


def test_slow_steps_do_not_overlap_or_create_catch_up_bursts() -> None:
    clock = _FakeClock()
    engine = _FakeEngine(clock, step_duration=2.0)

    _run_three_steps(clock, engine, tick_seconds=1.0)

    assert engine.starts == [0.0, 2.0, 4.0]
    assert clock.sleeps == []


@pytest.mark.parametrize("tick_seconds", [0.0, -1.0, float("nan"), float("inf")])
def test_continuous_runner_requires_a_positive_finite_interval(
    tick_seconds: float,
) -> None:
    clock = _FakeClock()

    with pytest.raises(ValueError, match="finite positive"):
        ContinuousRunner(
            cast(SimulationEngine, _FakeEngine(clock, step_duration=0.0)),
            tick_seconds=tick_seconds,
            clock=clock,
        )
