"""Ollama-specific availability checks kept outside the domain model."""

import asyncio
import json
import ssl
from collections.abc import Awaitable, Callable, Mapping, Sequence
from contextlib import suppress
from urllib.parse import urlparse, urlunparse

type OllamaTagsTransport = Callable[[str, float], Awaitable[bytes]]

_MAX_TAGS_RESPONSE_BYTES = 1024 * 1024


class OllamaPreflightError(ValueError):
    """An Ollama runtime or requested model is unavailable."""


class OllamaModelPreflight:
    """Verify concrete model tags through Ollama's local tags endpoint."""

    runtime = "ollama"

    def __init__(
        self,
        *,
        base_url: str,
        timeout_seconds: float = 5.0,
        transport: OllamaTagsTransport | None = None,
    ) -> None:
        parsed = urlparse(base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("Ollama base URL must use HTTP or HTTPS")
        self._endpoint = urlunparse(
            (parsed.scheme, parsed.netloc, "/api/tags", "", "", "")
        )
        self._timeout_seconds = timeout_seconds
        self._transport = transport or _get

    async def ensure_available(self, models: Sequence[str]) -> None:
        requested = tuple(dict.fromkeys(models))
        installed = await self.list_installed()

        missing = [model for model in requested if _canonical(model) not in installed]
        if not missing:
            return
        installed_lines = "\n".join(
            f"  {model}" for model in sorted(installed)
        ) or "  (none)"
        model = missing[0]
        raise OllamaPreflightError(
            f"Model {model!r} is not available in Ollama.\n\n"
            f"Installed models:\n{installed_lines}\n\n"
            f"Install it with:\n  ollama pull {model}"
        )

    async def list_installed(self) -> tuple[str, ...]:
        """Return canonical installed tags without exposing Ollama wire data."""

        try:
            raw = await asyncio.wait_for(
                self._transport(self._endpoint, self._timeout_seconds),
                timeout=self._timeout_seconds,
            )
            installed = _parse_installed_models(raw)
        except (OllamaPreflightError, asyncio.CancelledError):
            raise
        except Exception as error:
            raise OllamaPreflightError(
                f"Ollama is unavailable at {self._endpoint}.\n\n"
                "Start it with:\n  ollama serve"
            ) from error
        return tuple(sorted(installed))


def _parse_installed_models(raw: bytes) -> frozenset[str]:
    try:
        payload = json.loads(raw)
        models = payload["models"]
        if not isinstance(models, list):
            raise TypeError
        names: set[str] = set()
        for model in models:
            if not isinstance(model, Mapping):
                raise TypeError
            name = model.get("name", model.get("model"))
            if not isinstance(name, str) or not name:
                raise TypeError
            names.add(_canonical(name))
        return frozenset(names)
    except (KeyError, TypeError, ValueError, UnicodeDecodeError) as error:
        raise OllamaPreflightError(
            "Ollama returned an invalid model inventory"
        ) from error


def _canonical(model: str) -> str:
    return model if ":" in model else f"{model}:latest"


async def _get(url: str, timeout_seconds: float) -> bytes:
    parsed = urlparse(url)
    host = parsed.hostname
    if host is None:
        raise ValueError("Ollama endpoint has no host")
    secure = parsed.scheme == "https"
    port = parsed.port or (443 if secure else 80)
    ssl_context = ssl.create_default_context() if secure else None
    reader, writer = await asyncio.wait_for(
        asyncio.open_connection(
            host,
            port,
            ssl=ssl_context,
            server_hostname=host if secure else None,
        ),
        timeout=timeout_seconds,
    )
    try:
        target = parsed.path or "/"
        request = (
            f"GET {target} HTTP/1.1\r\n"
            f"Host: {parsed.netloc}\r\n"
            "Accept: application/json\r\n"
            "Connection: close\r\n\r\n"
        )
        writer.write(request.encode("ascii"))
        await writer.drain()
        status_line = await reader.readline()
        parts = status_line.decode("iso-8859-1").split(maxsplit=2)
        if len(parts) < 2 or not parts[1].isdigit():
            raise ConnectionError("Ollama returned an invalid HTTP response")
        headers: dict[str, str] = {}
        while True:
            line = await reader.readline()
            if line in {b"\r\n", b"\n", b""}:
                break
            name, separator, value = line.decode("iso-8859-1").partition(":")
            if not separator:
                raise ConnectionError("Ollama returned invalid HTTP headers")
            headers[name.lower()] = value.strip()
        status = int(parts[1])
        if status < 200 or status >= 300:
            raise ConnectionError(f"Ollama returned HTTP status {status}")
        if headers.get("transfer-encoding", "").lower() == "chunked":
            return await _read_chunked(reader)
        if "content-length" in headers:
            length = int(headers["content-length"])
            if length > _MAX_TAGS_RESPONSE_BYTES:
                raise ValueError("Ollama model inventory exceeded the size limit")
            return await reader.readexactly(length)
        body = await reader.read(_MAX_TAGS_RESPONSE_BYTES + 1)
        if len(body) > _MAX_TAGS_RESPONSE_BYTES:
            raise ValueError("Ollama model inventory exceeded the size limit")
        return body
    finally:
        writer.close()
        with suppress(ConnectionError, OSError):
            await writer.wait_closed()


async def _read_chunked(reader: asyncio.StreamReader) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while True:
        size_line = await reader.readline()
        size_text = size_line.split(b";", 1)[0].strip()
        size = int(size_text, 16)
        if size == 0:
            while await reader.readline() not in {b"\r\n", b"\n", b""}:
                pass
            return b"".join(chunks)
        total += size
        if total > _MAX_TAGS_RESPONSE_BYTES:
            raise ValueError("Ollama model inventory exceeded the size limit")
        chunks.append(await reader.readexactly(size))
        if await reader.readexactly(2) != b"\r\n":
            raise ConnectionError("Ollama returned an invalid chunked response")
