"""Process-local observational event bus."""

from collections.abc import Sequence
from dataclasses import dataclass

from antfarm.domain.models import Event
from antfarm.ports.events import EventHandler


@dataclass(slots=True)
class _InMemorySubscription:
    bus: "InMemoryEventBus"
    kinds: frozenset[str]
    handler: EventHandler
    active: bool = True

    def cancel(self) -> None:
        self.active = False


class InMemoryEventBus:
    def __init__(self, *, max_retained_events: int = 1_000) -> None:
        if max_retained_events < 0:
            raise ValueError("event retention limit must not be negative")
        self._max_retained_events = max_retained_events
        self.published: list[Event] = []
        self.observer_errors: list[str] = []
        self._subscriptions: list[_InMemorySubscription] = []

    def publish(self, events: Sequence[Event]) -> None:
        self.published.extend(events)
        if len(self.published) > self._max_retained_events:
            del self.published[: len(self.published) - self._max_retained_events]
        for event in events:
            for subscription in tuple(self._subscriptions):
                if subscription.active and event.kind in subscription.kinds:
                    try:
                        subscription.handler(event)
                    except Exception as error:
                        self.observer_errors.append(type(error).__name__)
                        del self.observer_errors[:-100]

    def subscribe(
        self, kinds: set[str], handler: EventHandler
    ) -> _InMemorySubscription:
        subscription = _InMemorySubscription(
            bus=self,
            kinds=frozenset(kinds),
            handler=handler,
        )
        self._subscriptions.append(subscription)
        return subscription
