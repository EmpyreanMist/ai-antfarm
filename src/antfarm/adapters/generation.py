"""Definition-generator adapters for offline tests and compatible model APIs."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable, Mapping
from urllib.parse import urlparse

from antfarm.adapters.models.openai_compatible import async_http_transport
from antfarm.custom.schema import CustomSimulationDefinition

type HttpTransport = Callable[
    [str, Mapping[str, str], bytes, float], Awaitable[bytes]
]


class StaticCustomDefinitionGenerator:
    """Deterministic generator used by offline demos and acceptance tests."""

    kind = "offline_static"

    def __init__(self, definition: CustomSimulationDefinition) -> None:
        self._content = definition.model_dump_json(exclude_none=True)

    async def generate(self, description: str) -> str:
        del description
        return self._content

    async def close(self) -> None:
        return None


class OpenAICompatibleDefinitionGenerator:
    """Generate one M7 JSON object through a chat-completions endpoint."""

    kind = "openai_compatible"

    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        timeout_seconds: float = 60,
        api_key: str | None = None,
        transport: HttpTransport | None = None,
    ) -> None:
        parsed = urlparse(base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("generator base URL must use HTTP or HTTPS")
        if not model:
            raise ValueError("generator model must not be empty")
        if timeout_seconds <= 0:
            raise ValueError("generator timeout must be positive")
        self._endpoint = f"{base_url.rstrip('/')}/chat/completions"
        self._model = model
        self._timeout = timeout_seconds
        self._api_key = api_key
        self._transport = transport or async_http_transport

    async def generate(self, description: str) -> str:
        schema = CustomSimulationDefinition.model_json_schema()
        body = json.dumps(
            {
                "model": self._model,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "Return only one complete AntFarm custom simulation JSON "
                            "object matching the supplied schema. Never emit code, "
                            "imports, expressions, commands, Markdown, or commentary. "
                            f"Schema: {json.dumps(schema, separators=(',', ':'))}"
                        ),
                    },
                    {"role": "user", "content": description},
                ],
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "antfarm_custom_definition",
                        "strict": True,
                        "schema": schema,
                    },
                },
            },
            separators=(",", ":"),
        ).encode()
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        response = await asyncio.wait_for(
            self._transport(self._endpoint, headers, body, self._timeout),
            timeout=self._timeout,
        )
        try:
            envelope = json.loads(response)
            content = envelope["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError, ValueError) as error:
            raise ValueError(
                "generator endpoint returned a malformed response"
            ) from error
        if not isinstance(content, str):
            raise ValueError("generator endpoint returned non-text content")
        return content

    async def close(self) -> None:
        return None
