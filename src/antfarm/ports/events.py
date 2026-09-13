"""Observational event publication boundary."""

from collections.abc import Sequence
from typing import Protocol

from antfarm.domain.models import Event


class EventBus(Protocol):
    def publish(self, events: Sequence[Event]) -> None: ...
