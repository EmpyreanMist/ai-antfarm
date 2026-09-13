"""Process-local observational event bus."""

from collections.abc import Sequence

from antfarm.domain.models import Event


class InMemoryEventBus:
    def __init__(self) -> None:
        self.published: list[Event] = []

    def publish(self, events: Sequence[Event]) -> None:
        self.published.extend(events)
