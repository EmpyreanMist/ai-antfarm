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
    def __init__(self) -> None:
        self.published: list[Event] = []
        self._subscriptions: list[_InMemorySubscription] = []

    def publish(self, events: Sequence[Event]) -> None:
        self.published.extend(events)
        for event in events:
            for subscription in tuple(self._subscriptions):
                if subscription.active and event.kind in subscription.kinds:
                    subscription.handler(event)

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
