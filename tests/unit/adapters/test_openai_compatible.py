import asyncio
import json
from collections.abc import Mapping
from dataclasses import replace

import pytest

from antfarm.adapters.models import OpenAICompatibleModelProvider
from antfarm.domain import (
    AgentId,
    AgentIdentity,
    AgentPersonality,
    AgentProfile,
    BehavioralTraits,
    CommunicationPreferences,
    MemoryItem,
    Observation,
    PrivateInformation,
    ProfileBeliefs,
    ProfileGoals,
    ProfileIdentity,
    ProfilePersonality,
    ProfileValues,
    SocialStatus,
    Tick,
)
from antfarm.ports.models import (
    MalformedModelResponseError,
    ModelRequest,
    ModelResponse,
)


def _request() -> ModelRequest:
    agent_id = AgentId("alice")
    return ModelRequest(
        identity=AgentIdentity(id=agent_id),
        personality=AgentPersonality(
            description="A patient steward.",
            traits={"patience": "high"},
        ),
        observation=Observation(
            agent_id=agent_id,
            tick=Tick(3),
            state={"value": 7},
        ),
        memories=(MemoryItem(kind="action_result", content={"value": 6}),),
        available_actions=(
            {
                "kind": "increment",
                "description": "Increase the counter.",
                "parameters": {"amount": "A positive integer."},
            },
        ),
    )


def test_structured_request_and_response_use_provider_neutral_values() -> None:
    captured: dict[str, object] = {}

    async def transport(
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
    assert body["response_format"]["json_schema"]["schema"]["properties"][
        "action_kind"
    ]["enum"] == ["increment", None]
    system_prompt = body["messages"][0]["content"]
    assert '"additionalProperties":false' in system_prompt
    assert '"action_kind"' in system_prompt
    context = json.loads(body["messages"][1]["content"])
    assert context == {
        "available_actions": [
            {
                "description": "Increase the counter.",
                "kind": "increment",
                "parameters": {"amount": "A positive integer."},
            }
        ],
        "identity": {"id": "alice"},
        "observation": {"state": {"value": 7}, "tick": 3},
        "private_context": {
            "memories": [
                {"content": {"value": 6}, "kind": "action_result"}
            ],
            "personality": {
                "description": "A patient steward.",
                "traits": {"patience": "high"},
            },
        },
    }


def test_rich_profile_context_is_compact_and_social_guidance_is_behavioral() -> None:
    profile = AgentProfile(
        identity=ProfileIdentity(display_name="Alice"),
        personality=ProfilePersonality(
            description="Warm and competitive.", qualities=("direct",)
        ),
        goals=ProfileGoals(("Secure resources",)),
        beliefs=ProfileBeliefs(("Cooperation can help",)),
        values=ProfileValues(("Fairness", "Achievement")),
        communication=CommunicationPreferences(style="concise"),
        traits=BehavioralTraits(generosity=0.8, greed=0.7, patience=0.2),
        social_status=SocialStatus(roles=("merchant",), standing=0.6),
        private_information=PrivateInformation(("Has a private debt",)),
    )
    provider = OpenAICompatibleModelProvider(
        base_url="https://models.example/v1",
        model="test",
        timeout_seconds=1,
    )

    body = json.loads(
        provider._request_body(  # noqa: SLF001
            replace(_request(), personality=None, profile=profile)
        )
    )
    context = json.loads(body["messages"][1]["content"])
    rich_context = context["private_context"]["profile"]

    assert rich_context["identity"] == {"display_name": "Alice"}
    assert rich_context["behavioral_traits"] == {
        "generosity": 0.8,
        "greed": 0.7,
        "patience": 0.2,
    }
    assert rich_context["private_information"] == ["Has a private debt"]
    assert "description" not in rich_context["identity"]
    system_prompt = body["messages"][0]["content"]
    assert "not as rules that mechanically select an action" in system_prompt
    assert "Do not seek consensus or conflict for its own sake" in system_prompt
    assert "Do not repeat earlier messages or points" in system_prompt
    assert "Do not invent facts" in system_prompt


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
    async def transport(
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


@pytest.mark.parametrize("fence", ["```json", "```"])
def test_markdown_fenced_json_response_is_accepted(fence: str) -> None:
    decision = '{"action_kind":"increment","parameters":{"amount":2}}'

    async def transport(
        url: str,
        headers: Mapping[str, str],
        body: bytes,
        timeout_seconds: float,
    ) -> bytes:
        del url, headers, body, timeout_seconds
        content = f"{fence}\n{decision}\n```"
        return json.dumps(
            {"choices": [{"message": {"content": content}}]}
        ).encode()

    provider = OpenAICompatibleModelProvider(
        base_url="https://models.example/v1",
        model="test",
        timeout_seconds=1,
        transport=transport,
    )

    response = asyncio.run(provider.generate(_request()))

    assert response == ModelResponse(
        action_kind="increment", parameters={"amount": 2}
    )


def test_malformed_error_does_not_expose_response_content() -> None:
    sensitive_content = "private-model-output-that-is-not-json"

    async def transport(
        url: str,
        headers: Mapping[str, str],
        body: bytes,
        timeout_seconds: float,
    ) -> bytes:
        del url, headers, body, timeout_seconds
        return json.dumps(
            {"choices": [{"message": {"content": sensitive_content}}]}
        ).encode()

    provider = OpenAICompatibleModelProvider(
        base_url="https://models.example/v1",
        model="test",
        timeout_seconds=1,
        transport=transport,
    )

    with pytest.raises(MalformedModelResponseError) as raised:
        asyncio.run(provider.generate(_request()))

    assert sensitive_content not in str(raised.value)


def test_timeout_is_enforced_around_the_transport() -> None:
    async def slow_transport(
        url: str,
        headers: Mapping[str, str],
        body: bytes,
        timeout_seconds: float,
    ) -> bytes:
        del url, headers, body, timeout_seconds
        await asyncio.sleep(0.05)
        return b"{}"

    provider = OpenAICompatibleModelProvider(
        base_url="https://models.example/v1",
        model="test",
        timeout_seconds=0.01,
        transport=slow_transport,
    )

    with pytest.raises(TimeoutError):
        asyncio.run(provider.generate(_request()))


def test_cancelling_real_transport_closes_the_in_flight_connection() -> None:
    async def exercise() -> None:
        request_received = asyncio.Event()
        connection_closed = asyncio.Event()

        async def handle(
            reader: asyncio.StreamReader, writer: asyncio.StreamWriter
        ) -> None:
            try:
                await reader.readuntil(b"\r\n\r\n")
                request_received.set()
                await reader.read()
                connection_closed.set()
            finally:
                writer.close()
                await writer.wait_closed()

        server = await asyncio.start_server(handle, "127.0.0.1", 0)
        socket = server.sockets[0]
        port = socket.getsockname()[1]
        provider = OpenAICompatibleModelProvider(
            base_url=f"http://127.0.0.1:{port}/v1",
            model="test",
            timeout_seconds=5,
        )
        task = asyncio.create_task(provider.generate(_request()))
        await asyncio.wait_for(request_received.wait(), 1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        await asyncio.wait_for(connection_closed.wait(), 1)
        server.close()
        await server.wait_closed()

    asyncio.run(exercise())


def test_real_async_transport_reads_a_content_length_response() -> None:
    async def exercise() -> ModelResponse:
        async def handle(
            reader: asyncio.StreamReader, writer: asyncio.StreamWriter
        ) -> None:
            await reader.readuntil(b"\r\n\r\n")
            content = json.dumps(
                {"action_kind": "increment", "parameters": {"amount": 2}}
            )
            body = json.dumps(
                {"choices": [{"message": {"content": content}}]}
            ).encode()
            writer.write(
                b"HTTP/1.1 200 OK\r\nContent-Length: "
                + str(len(body)).encode()
                + b"\r\nConnection: close\r\n\r\n"
                + body
            )
            await writer.drain()
            writer.close()
            await writer.wait_closed()

        server = await asyncio.start_server(handle, "127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        provider = OpenAICompatibleModelProvider(
            base_url=f"http://127.0.0.1:{port}/v1",
            model="test",
            timeout_seconds=1,
        )
        try:
            return await provider.generate(_request())
        finally:
            server.close()
            await server.wait_closed()

    assert asyncio.run(exercise()) == ModelResponse(
        action_kind="increment", parameters={"amount": 2}
    )


@pytest.mark.parametrize("base_url", ["", "models.example/v1", "file:///tmp/v1"])
def test_base_url_must_be_http_or_https(base_url: str) -> None:
    with pytest.raises(ValueError, match="HTTP or HTTPS"):
        OpenAICompatibleModelProvider(
            base_url=base_url,
            model="test",
            timeout_seconds=1,
        )
