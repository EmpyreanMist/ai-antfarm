"""Plain-text presentation of committed simulation events and live status."""

import json
import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass
from typing import TextIO

from antfarm.config.schema import ScenarioConfig, SqliteStorageConfig
from antfarm.domain.json_values import JsonObject, thaw_json
from antfarm.domain.models import AgentId, Event, Tick

VISIBLE_EVENT_KINDS = {
    "action.applied",
    "action.noop",
    "action.rejected",
    "cognition.failed",
    "cognition.malformed",
    "cognition.timed_out",
}


class TerminalOutputError(OSError):
    """The live output stream can no longer accept presentation data."""


@dataclass(slots=True)
class LiveTerminalObserver:
    """Render only event envelopes that have already crossed the commit boundary."""

    stream: TextIO
    verbose: bool = False
    failure: TerminalOutputError | None = None

    @property
    def event_kinds(self) -> set[str]:
        return set(VISIBLE_EVENT_KINDS)

    def observe(self, event: Event) -> None:
        if self.failure is not None:
            return
        try:
            self._line(_format_event(event))
        except TerminalOutputError as error:
            # The event bus intentionally isolates post-commit subscribers. Retain
            # the failure so the runner can stop after this committed batch.
            self.failure = error

    def raise_if_failed(self) -> None:
        if self.failure is not None:
            raise self.failure

    def status(self, message: str) -> None:
        self._line(f"[status] {_sanitize(message)}")

    def thinking(
        self,
        tick: Tick,
        agent_id: AgentId,
        model_ref: str,
        backend: str,
        model: str,
    ) -> None:
        self.status(
            f"[tick {int(tick)}] {_display_name(agent_id)} thinking "
            f"via {model_ref} / {backend} / {model}..."
        )

    def waiting(self, tick: Tick, delay: float) -> None:
        self.status(f"[tick {int(tick)}] waiting {delay:g}s for next tick...")

    def header(self, config: ScenarioConfig, *, tick_seconds: float) -> None:
        agents = config.active_agents()
        checkpoint = checkpoint_location(config)
        assignments = [
            (
                _backend_name(config, agent.model_ref),
                config.models[agent.model_ref].model,
            )
            for agent in agents
        ]
        self._line("AntFarm Live Society")
        self._line("")
        self._line(f"Run      {config.run.id}")
        self._line(
            f"Agents   {len(agents)}: "
            + ", ".join(_display_name(agent.id) for agent in agents)
        )
        if len(set(assignments)) == 1:
            backend, model = assignments[0]
            self._line(f"Backend  {backend}")
            self._line(f"Model    {_sanitize(model)}")
        else:
            self._line("Models")
            for agent, (backend, model) in zip(agents, assignments, strict=True):
                self._line(
                    f"  {_display_name(agent.id)} -> {backend} / {_sanitize(model)}"
                )
        budget = config.scheduling.max_cognitions_per_tick
        self._line(f"Budget   {budget if budget is not None else 'unbounded'}")
        self._line(f"Cadence  >= {tick_seconds:g}s")
        self._line(f"Database {_sanitize(checkpoint)}")
        if self.verbose:
            for agent in agents:
                model_config = config.models[agent.model_ref]
                self.status(
                    f"{_display_name(agent.id)} -> "
                    f"provider={model_config.provider_ref}; "
                    f"model_ref={agent.model_ref}; model={model_config.model}"
                )
        self._line("")
        self._line("Ctrl+C to stop.")
        self._line("")

    def final(
        self,
        *,
        tick: int,
        active_agents: int,
        world: JsonObject,
        metrics: JsonObject,
        checkpoint: str,
    ) -> None:
        self._line("")
        self._line("Stopping...")
        self._line(f"Last tick {tick}")
        self._line(f"Agents    {active_agents}")
        self._line(f"World     {_sanitize(_encoded(world))}")
        self._line(f"Metrics   {_sanitize(_encoded(metrics))}")
        self._line(f"Database  {_sanitize(checkpoint)}")

    def _line(self, value: str) -> None:
        try:
            self.stream.write(f"{value}\n")
            self.stream.flush()
        except (BrokenPipeError, OSError) as error:
            raise TerminalOutputError("live output stream failed") from error


def checkpoint_location(config: ScenarioConfig) -> str:
    if isinstance(config.storage, SqliteStorageConfig):
        return config.storage.path
    return "memory (not durable)"


def _format_event(event: Event) -> str:
    actor = _display_name(event.actor_id) if event.actor_id is not None else "System"
    prefix = f"[tick {int(event.tick)}] {actor}"
    payload = event.payload
    if event.kind == "action.applied":
        kind = payload.get("kind")
        if kind == "say":
            message = payload.get("message")
            text = message.get("text") if isinstance(message, Mapping) else None
            rendered = _quoted(text if isinstance(text, str) else "")
            return f"{prefix} says: {rendered}"
        parameters = payload.get("parameters")
        amount = parameters.get("amount") if isinstance(parameters, Mapping) else None
        details = []
        if isinstance(amount, int) and not isinstance(amount, bool):
            details.append(str(amount))
        for name in ("resource", "actor_holding", "value"):
            if name in payload:
                label = "holding" if name == "actor_holding" else name
                details.append(f"{label}={payload[name]}")
        suffix = "; ".join(details)
        action = _past_tense(_sanitize(str(kind or "action")))
        return f"{prefix} {action}{(' ' + suffix) if suffix else ''}."
    if event.kind == "action.rejected":
        kind = _sanitize(str(payload.get("kind", "action")))
        reason = _sanitize(str(payload.get("reason", "rejected")))
        return f"{prefix}'s {kind} was rejected: {reason}."
    if event.kind == "action.noop":
        return f"{prefix} took no action."
    reason = _sanitize(str(payload.get("reason", "unknown")))
    label = event.kind.removeprefix("cognition.").replace("_", " ")
    return f"{prefix} cognition {label}: {reason}."


def _past_tense(kind: str) -> str:
    return {"harvest": "harvested", "contribute": "contributed"}.get(
        kind, f"applied {kind}"
    )


def _display_name(agent_id: str) -> str:
    return "-".join(part.capitalize() for part in str(agent_id).split("-"))


def _backend_name(config: ScenarioConfig, model_ref: str) -> str:
    provider = config.providers[config.models[model_ref].provider_ref]
    runtime = getattr(provider, "runtime", None)
    if runtime == "ollama":
        return "Ollama"
    if provider.kind == "mock":
        return "Mock"
    return "OpenAI-compatible"


def _quoted(value: str) -> str:
    return json.dumps(_sanitize(value), ensure_ascii=False)


def _sanitize(value: str) -> str:
    """Make untrusted model text inert and single-line on every terminal."""

    normalized = value.replace("\r\n", " ").replace("\r", " ").replace("\n", " ")
    return "".join(
        "�" if unicodedata.category(character).startswith("C") else character
        for character in normalized
    )


def _encoded(value: JsonObject) -> str:
    return json.dumps(
        thaw_json(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
