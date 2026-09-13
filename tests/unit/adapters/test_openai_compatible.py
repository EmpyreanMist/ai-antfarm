import asyncio
import json
import time
from collections.abc import Mapping

import pytest

from antfarm.adapters.models import OpenAICompatibleModelProvider
from antfarm.domain import AgentId, MemoryItem, Observation, Tick
from antfarm.ports.models import (
    MalformedModelResponseError,
    ModelRequest,
    ModelResponse,
)


def _request() -> ModelRequest:
    agent_id = AgentId("alice")
    return ModelRequest(
        actor_id=agent_id,
        observation=Observation(
            agent_id=agent_id,
            tick=Tick(3),
            state={"value": 7},
        ),
        memories=(MemoryItem(kind="action_result", content={"value": 6}),),
    )


def test_structured_request_and_response_use_provider_neutral_values() -> None:
    captured: dict[str, object] = {}

    def transport(
        url: str,
        headers: Mapping[str, str],
        body: bytes,
        timeout_seconds: float,
    ) -> bytes:
        captured.update(
            url=url,
            headers=dict(headers),
            body=json.loads(body),
            timeout_seconds=timeout_seconds,
        )
        return json.dumps(
            {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "action_kind": "increment",
                                    "parameters": {"amount": 2},
                                }
                            )
                        }
                    }
                ]
            }
        ).encode()

    provider = OpenAICompatibleModelProvider(
        base_url="http://localhost:11434/v1/",
        model="example/model",
        timeout_seconds=12.0,
        parameters={"temperature": 0},
        api_key="secret",
        transport=transport,
    )

    response = asyncio.run(provider.generate(_request()))

    assert response == ModelResponse(
        action_kind="increment", parameters={"amount": 2}
    )
    assert provider.capabilities.structured_output is True
    assert provider.capabilities.network_required is True
    assert captured["url"] == "http://localhost:11434/v1/chat/completions"
    assert captured["timeout_seconds"] == 12.0
    assert captured["headers"] == {
        "Content-Type": "application/json",
        "Authorization": "Bearer secret",
    }
    body = captured["body"]
    assert isinstance(body, dict)
    assert body["model"] == "example/model"
    assert body["temperature"] == 0
    assert body["response_format"]["type"] == "json_schema"
    context = json.loads(body["messages"][1]["content"])
    assert context == {
        "actor_id": "alice",
        "memories": [{"content": {"value": 6}, "kind": "action_result"}],
        "observation": {"state": {"value": 7}, "tick": 3},
    }


@pytest.mark.parametrize(
    "raw_response",
    [
        b"not json",
        b"{}",
        b'{"choices":[]}',
        b'{"choices":[{"message":{"content":"[]"}}]}',
        (
            b'{"choices":[{"message":{"content":'
            b'"{\\"action_kind\\":1,\\"parameters\\":{}}"}}]}'
        ),
        (
            b'{"choices":[{"message":{"content":'
            b'"{\\"action_kind\\":null,\\"parameters\\":[],\\"extra\\":1}"}}]}'
        ),
    ],
)
def test_malformed_structured_responses_fail_safely(raw_response: bytes) -> None:
    def transport(
        url: str,
        headers: Mapping[str, str],
        body: bytes,
        timeout_seconds: float,
    ) -> bytes:
        del url, headers, body, timeout_seconds
        return raw_response

    provider = OpenAICompatibleModelProvider(
        base_url="https://models.example/v1",
        model="test",
        timeout_seconds=1,
        transport=transport,
    )

    with pytest.raises(MalformedModelResponseError, match="malformed"):
        asyncio.run(provider.generate(_request()))


def test_timeout_is_enforced_around_the_transport() -> None:
    def slow_transport(
        url: str,
        headers: Mapping[str, str],
        body: bytes,
        timeout_seconds: float,
    ) -> bytes:
        del url, headers, body, timeout_seconds
        time.sleep(0.05)
        return b"{}"

    provider = OpenAICompatibleModelProvider(
        base_url="https://models.example/v1",
        model="test",
        timeout_seconds=0.01,
        transport=slow_transport,
    )

    with pytest.raises(TimeoutError):
        asyncio.run(provider.generate(_request()))


@pytest.mark.parametrize("base_url", ["", "models.example/v1", "file:///tmp/v1"])
def test_base_url_must_be_http_or_https(base_url: str) -> None:
    with pytest.raises(ValueError, match="HTTP or HTTPS"):
        OpenAICompatibleModelProvider(
            base_url=base_url,
            model="test",
            timeout_seconds=1,
        )
