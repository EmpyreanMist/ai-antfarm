"""Paced, non-accumulating execution around the sequential engine."""

import asyncio
import math
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Protocol

from antfarm.application.engine import SimulationEngine
from antfarm.domain.models import Event, SimulationSnapshot, Tick

type EventBatchHandler = Callable[[Sequence[Event]], None]


class PacingClock(Protocol):
    def monotonic(self) -> float: ...

    async def sleep(self, delay: float) -> None: ...


class AsyncioPacingClock:
    def monotonic(self) -> float:
        return time.monotonic()

    async def sleep(self, delay: float) -> None:
        await asyncio.sleep(delay)


@dataclass(frozen=True, slots=True)
class ContinuousRunResult:
    snapshot: SimulationSnapshot
    stopped: bool


class ContinuousRunner:
    """Run atomic steps sequentially with a minimum interval between starts."""

    def __init__(
        self,
        engine: SimulationEngine,
        *,
        tick_seconds: float,
        clock: PacingClock | None = None,
        on_batch: EventBatchHandler | None = None,
        should_stop: Callable[[], bool] | None = None,
        on_waiting: Callable[[Tick, float], None] | None = None,
    ) -> None:
        if not math.isfinite(tick_seconds) or tick_seconds <= 0:
            raise ValueError("tick interval must be a finite positive number")
        self._engine = engine
        self._tick_seconds = tick_seconds
        self._clock = clock or AsyncioPacingClock()
        self._on_batch = on_batch
        self._should_stop = should_stop or (lambda: False)
        self._on_waiting = on_waiting

    async def run(self) -> ContinuousRunResult:
        next_start: float | None = None
        while not self._should_stop():
            try:
                now = self._clock.monotonic()
                if next_start is not None and now < next_start:
                    delay = next_start - now
                    if self._on_waiting is not None:
                        next_tick = Tick(int(self._engine.snapshot().tick) + 1)
                        self._on_waiting(next_tick, delay)
                    await self._clock.sleep(delay)
                started = self._clock.monotonic()
                result = await self._engine.step()
            except asyncio.CancelledError:
                return ContinuousRunResult(
                    snapshot=self._engine.snapshot(), stopped=True
                )
            if self._on_batch is not None:
                self._on_batch(result.events)
            # Anchor pacing to the actual start. An overrun never creates debt,
            # so there are no skipped ticks or catch-up bursts.
            next_start = max(started + self._tick_seconds, self._clock.monotonic())
        return ContinuousRunResult(snapshot=self._engine.snapshot(), stopped=True)
