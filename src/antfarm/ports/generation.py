"""Provider-neutral boundary for custom-definition generation."""

from typing import Protocol


class CustomDefinitionGenerator(Protocol):
    kind: str

    async def generate(self, description: str) -> str: ...

    async def close(self) -> None: ...
