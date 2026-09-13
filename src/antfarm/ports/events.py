"""Observational event publication boundary."""

from collections.abc import Callable, Sequence
from typing import Protocol

from antfarm.domain.models import Event

EventHandler = Callable[[Event], None]


class Subscription(Protocol):
    def cancel(self) -> None: ...


class EventBus(Protocol):
    def publish(self, events: Sequence[Event]) -> None: ...

    def subscribe(self, kinds: set[str], handler: EventHandler) -> Subscription: ...
