"""Generic adapter for OpenAI-compatible chat-completions endpoints."""

import asyncio
import json
from collections.abc import Callable, Mapping
from typing import cast
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from antfarm.domain.json_values import JsonObject, thaw_json
from antfarm.ports.models import (
    MalformedModelResponseError,
    ModelRequest,
    ModelResponse,
    ProviderCapabilities,
)

type HttpTransport = Callable[[str, Mapping[str, str], bytes, float], bytes]

_ACTION_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {
        "action_kind": {"type": ["string", "null"]},
        "parameters": {"type": "object"},
    },
    "required": ["action_kind", "parameters"],
    "additionalProperties": False,
}


class OpenAICompatibleModelProvider:
    """Generate provider-neutral decisions through `/chat/completions`."""

    capabilities = ProviderCapabilities(
        structured_output=True,
        network_required=True,
    )

    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        timeout_seconds: float,
        parameters: JsonObject | None = None,
        api_key: str | None = None,
        transport: HttpTransport | None = None,
    ) -> None:
        parsed_url = urlparse(base_url)
        if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
            raise ValueError("OpenAI-compatible base URL must use HTTP or HTTPS")
        if not model:
            raise ValueError("OpenAI-compatible model must not be empty")
        if timeout_seconds <= 0:
            raise ValueError("OpenAI-compatible timeout must be positive")
        self._endpoint = f"{base_url.rstrip('/')}/chat/completions"
        self._model = model
        self._timeout_seconds = timeout_seconds
        self._parameters = parameters or {}
        self._api_key = api_key
        self._transport = transport or _urlopen_transport

    async def generate(self, request: ModelRequest) -> ModelResponse:
        body = self._request_body(request)
        headers = {"Content-Type": "application/json"}
        if self._api_key is not None:
            headers["Authorization"] = f"Bearer {self._api_key}"

        raw_response = await asyncio.wait_for(
            asyncio.to_thread(
                self._transport,
                self._endpoint,
                headers,
                body,
                self._timeout_seconds,
            ),
            timeout=self._timeout_seconds,
        )
        return _parse_response(raw_response)

    def _request_body(self, request: ModelRequest) -> bytes:
        context = {
            "actor_id": str(request.actor_id),
            "observation": {
                "tick": int(request.observation.tick),
                "state": thaw_json(request.observation.state),
            },
            "memories": [
                {"kind": item.kind, "content": thaw_json(item.content)}
                for item in request.memories
            ],
        }
        thawed_parameters = thaw_json(self._parameters)
        if not isinstance(thawed_parameters, dict):
            raise TypeError("model parameters must be a JSON object")
        payload = {
            **thawed_parameters,
            "model": self._model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Propose one simulation action. Return only the requested "
                        "structured JSON. Use null action_kind and empty parameters "
                        "to take no action."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        context, sort_keys=True, separators=(",", ":")
                    ),
                },
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "antfarm_action_proposal",
                    "strict": True,
                    "schema": _ACTION_SCHEMA,
                },
            },
        }
        return json.dumps(payload, allow_nan=False, separators=(",", ":")).encode()


def _urlopen_transport(
    url: str,
    headers: Mapping[str, str],
    body: bytes,
    timeout_seconds: float,
) -> bytes:
    request = Request(url, data=body, headers=dict(headers), method="POST")
    with urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310
        return cast(bytes, response.read())


def _parse_response(raw_response: bytes) -> ModelResponse:
    try:
        envelope = json.loads(raw_response)
        choices = envelope["choices"]
        if not isinstance(choices, list) or not choices:
            raise TypeError
        content = choices[0]["message"]["content"]
        if not isinstance(content, str):
            raise TypeError
        decision = json.loads(content)
        if not isinstance(decision, dict) or set(decision) != {
            "action_kind",
            "parameters",
        }:
            raise TypeError
        action_kind = decision["action_kind"]
        parameters = decision["parameters"]
        if action_kind is not None and not isinstance(action_kind, str):
            raise TypeError
        if not isinstance(parameters, dict):
            raise TypeError
        return ModelResponse(action_kind=action_kind, parameters=parameters)
    except (KeyError, TypeError, ValueError, UnicodeDecodeError) as error:
        raise MalformedModelResponseError(
            "OpenAI-compatible endpoint returned a malformed structured response"
        ) from error
