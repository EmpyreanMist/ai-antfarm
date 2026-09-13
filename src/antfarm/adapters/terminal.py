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

    def thinking(self, tick: Tick, agent_id: AgentId, model_ref: str) -> None:
        self.status(
            f"[tick {int(tick)}] {_display_name(agent_id)} thinking "
            f"via {model_ref}..."
        )

    def waiting(self, tick: Tick, delay: float) -> None:
        self.status(f"[tick {int(tick)}] waiting {delay:g}s for next tick...")

    def header(self, config: ScenarioConfig, *, tick_seconds: float) -> None:
        agents = config.active_agents()
        checkpoint = checkpoint_location(config)
        self._line("AntFarm Live Society")
        self.status(f"run={config.run.id}")
        self.status(
            f"agents={len(agents)}: "
            + ", ".join(_display_name(agent.id) for agent in agents)
        )
        budget = config.scheduling.max_cognitions_per_tick
        self.status(f"cognition_budget={budget if budget is not None else 'unbounded'}")
        self.status(
            f"cadence=interval {config.scheduling.interval}; "
            f"tick_interval>={tick_seconds:g}s"
        )
        self.status(f"checkpoint={checkpoint}")
        for agent in agents:
            model = config.models[agent.model_ref]
            self.status(
                f"{_display_name(agent.id)} -> {model.provider_ref} / {model.model}"
            )
        self.status("Ctrl+C to stop.")

    def final(
        self,
        *,
        tick: int,
        active_agents: int,
        world: JsonObject,
        metrics: JsonObject,
        checkpoint: str,
    ) -> None:
        self.status("Stopping...")
        self.status(f"last_committed_tick={tick}")
        self.status(f"agents={active_agents}")
        self.status(f"final_world={_encoded(world)}")
        self.status(f"final_metrics={_encoded(metrics)}")
        self.status(f"checkpoint={checkpoint}")

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
    prefix = f"[event tick {int(event.tick)}] {actor}"
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
                details.append(f"{name}={payload[name]}")
        suffix = "; ".join(details)
        action = _sanitize(str(kind or "action"))
        return f"{prefix} {action}s{(' ' + suffix) if suffix else ''}"
    if event.kind == "action.rejected":
        kind = _sanitize(str(payload.get("kind", "action")))
        reason = _sanitize(str(payload.get("reason", "rejected")))
        return f"{prefix} {kind} rejected: {reason}"
    if event.kind == "action.noop":
        return f"{prefix} takes no action"
    reason = _sanitize(str(payload.get("reason", "unknown")))
    label = event.kind.removeprefix("cognition.").replace("_", " ")
    return f"{prefix} cognition {label}: {reason}"


def _display_name(agent_id: str) -> str:
    return "-".join(part.capitalize() for part in str(agent_id).split("-"))


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
