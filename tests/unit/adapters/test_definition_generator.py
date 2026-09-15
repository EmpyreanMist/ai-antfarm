import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from antfarm.adapters.generation import OpenAICompatibleDefinitionGenerator
from antfarm.custom import load_custom_definition


@pytest.mark.asyncio
async def test_openai_compatible_generator_requests_strict_definition_json() -> None:
    definition = load_custom_definition(
        Path("scenarios/examples/custom-warehouse.yaml")
    )
    captured: dict[str, Any] = {}

    async def transport(
        url: str, headers: Mapping[str, str], body: bytes, timeout: float
    ) -> bytes:
        captured.update(
            url=url,
            headers=headers,
            body=json.loads(body),
            timeout=timeout,
        )
        return json.dumps(
            {
                "choices": [
                    {"message": {"content": definition.model_dump_json()}}
                ]
            }
        ).encode()

    generator = OpenAICompatibleDefinitionGenerator(
        base_url="http://localhost:11434/v1",
        model="local-model",
        transport=transport,
    )

    generated = await generator.generate("A warehouse")

    assert json.loads(generated)["kind"] == "custom"
    assert captured["url"] == "http://localhost:11434/v1/chat/completions"
    body: dict[str, Any] = captured["body"]
    assert body["response_format"]["type"] == "json_schema"


@pytest.mark.asyncio
async def test_openai_compatible_generator_rejects_malformed_envelopes() -> None:
    async def transport(
        _: str, __: Mapping[str, str], ___: bytes, ____: float
    ) -> bytes:
        return b'{"choices": []}'

    generator = OpenAICompatibleDefinitionGenerator(
        base_url="http://localhost:11434/v1",
        model="local-model",
        transport=transport,
    )

    with pytest.raises(ValueError, match="malformed"):
        await generator.generate("anything")


def test_openai_compatible_generator_rejects_invalid_configuration() -> None:
    with pytest.raises(ValueError, match="HTTP or HTTPS"):
        OpenAICompatibleDefinitionGenerator(base_url="file:///tmp", model="model")
    with pytest.raises(ValueError, match="model"):
        OpenAICompatibleDefinitionGenerator(base_url="http://localhost", model="")
    with pytest.raises(ValueError, match="timeout"):
        OpenAICompatibleDefinitionGenerator(
            base_url="http://localhost", model="model", timeout_seconds=0
        )
