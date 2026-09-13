import asyncio
import json

import pytest

from antfarm.adapters.models.ollama import (
    OllamaModelPreflight,
    OllamaPreflightError,
)


def test_ollama_preflight_accepts_installed_models_offline() -> None:
    captured: dict[str, object] = {}

    async def transport(url: str, timeout_seconds: float) -> bytes:
        captured.update(url=url, timeout_seconds=timeout_seconds)
        return json.dumps(
            {"models": [{"name": "gemma4:e2b"}, {"name": "qwen3.5:0.8b"}]}
        ).encode()

    checker = OllamaModelPreflight(
        base_url="http://localhost:11434/v1",
        timeout_seconds=2,
        transport=transport,
    )

    asyncio.run(checker.ensure_available(["gemma4:e2b"]))

    assert captured == {
        "url": "http://localhost:11434/api/tags",
        "timeout_seconds": 2,
    }


def test_ollama_preflight_reports_missing_model_and_installed_models() -> None:
    async def transport(url: str, timeout_seconds: float) -> bytes:
        del url, timeout_seconds
        return b'{"models":[{"name":"qwen3.5:0.8b"},{"name":"gemma4:e4b"}]}'

    checker = OllamaModelPreflight(
        base_url="http://localhost:11434/v1", transport=transport
    )

    with pytest.raises(OllamaPreflightError) as raised:
        asyncio.run(checker.ensure_available(["gemma4:e2b"]))

    message = str(raised.value)
    assert "Model 'gemma4:e2b' is not available in Ollama" in message
    assert "qwen3.5:0.8b" in message
    assert "gemma4:e4b" in message
    assert "ollama pull gemma4:e2b" in message


def test_ollama_preflight_reports_unavailable_runtime_without_network() -> None:
    async def transport(url: str, timeout_seconds: float) -> bytes:
        del url, timeout_seconds
        raise ConnectionError

    checker = OllamaModelPreflight(
        base_url="http://localhost:11434/v1", transport=transport
    )

    with pytest.raises(OllamaPreflightError, match="Ollama is unavailable"):
        asyncio.run(checker.ensure_available(["gemma4:e2b"]))
