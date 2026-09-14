"""Minimal non-interactive AntFarm command line interface."""

import argparse
import asyncio
import json
import math
import sys
from collections.abc import Sequence
from pathlib import Path

from pydantic import ValidationError
from ruamel.yaml.error import YAMLError

from antfarm.adapters.terminal import TerminalOutputError
from antfarm.config import load_scenario
from antfarm.config.schema import M2_MAX_ACTIVE_AGENTS
from antfarm.domain.json_values import thaw_json
from antfarm.facade import AntFarmApplication
from antfarm.runner import run_continuous_scenario, run_live_scenario, run_scenario


def _positive_float(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed) or parsed <= 0:
        raise argparse.ArgumentTypeError("must be a finite positive number")
    return parsed


def _active_agent_count(value: str) -> int:
    parsed = int(value)
    if not 1 <= parsed <= M2_MAX_ACTIVE_AGENTS:
        raise argparse.ArgumentTypeError(
            f"must be between 1 and {M2_MAX_ACTIVE_AGENTS}"
        )
    return parsed


def _model_name(value: str) -> str:
    if not value or value != value.strip():
        raise argparse.ArgumentTypeError("must be a non-empty trimmed value")
    if any(ord(character) < 32 or 127 <= ord(character) <= 159 for character in value):
        raise argparse.ArgumentTypeError("must not contain control characters")
    return value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="antfarm")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("validate", "inspect"):
        command = commands.add_parser(name)
        command.add_argument("scenario", type=Path)
    run = commands.add_parser("run")
    run.add_argument("scenario", type=Path)
    run.add_argument("--continuous", action="store_true")
    run.add_argument("--live", action="store_true")
    run.add_argument("--agents", type=_active_agent_count)
    run.add_argument("--model", type=_model_name)
    run.add_argument("--verbose", action="store_true")
    run.add_argument("--tick-seconds", type=_positive_float, default=1.0)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "validate":
            config = load_scenario(args.scenario)
            print(f"valid scenario: {config.run.id}")
            return 0
        if args.command == "inspect":
            application = AntFarmApplication()
            resolved = application.resolve_population(
                application.load_scenario(args.scenario)
            )
            agents = application.inspect_resolved_agents(resolved)
            output = resolved.config.normalized_data()
            output["generation_seed"] = resolved.config.run.seed
            expanded_agents = output["expanded_agents"]
            if not isinstance(expanded_agents, list):
                raise TypeError("normalized expanded agents must be a list")
            inspections = {agent.agent_id: agent for agent in agents}
            for expanded in expanded_agents:
                if not isinstance(expanded, dict):
                    raise TypeError("normalized agent must be an object")
                agent_id = expanded.get("id")
                inspection = (
                    inspections.get(agent_id) if isinstance(agent_id, str) else None
                )
                if inspection is None:
                    continue
                profile = inspection.configuration.get("profile")
                if profile is not None:
                    expanded["profile"] = thaw_json(profile)
                expanded["public"] = thaw_json(inspection.public)
                expanded["resolved_model"] = inspection.model
            print(
                json.dumps(
                    output,
                    sort_keys=True,
                    separators=(",", ":"),
                )
            )
            return 0
        if args.live and not args.continuous:
            raise ValueError("--live requires --continuous")
        if args.agents is not None and not args.live:
            raise ValueError("--agents requires --live")
        if args.model is not None and not args.live:
            raise ValueError("--model requires --live")
        if args.verbose and not args.live:
            raise ValueError("--verbose requires --live")
        if args.live:
            asyncio.run(
                run_live_scenario(
                    args.scenario,
                    tick_seconds=args.tick_seconds,
                    active_agents=args.agents,
                    model=args.model,
                    verbose=args.verbose,
                    output=sys.stdout,
                )
            )
            return 0
        if args.continuous:
            print(
                f"continuous; tick interval >= {args.tick_seconds:g}s; "
                "Ctrl+C to stop",
                flush=True,
            )
            summary = asyncio.run(
                run_continuous_scenario(
                    args.scenario, tick_seconds=args.tick_seconds
                )
            )
            print(f"stopped; last committed tick={summary.ticks}")
        else:
            summary = asyncio.run(run_scenario(args.scenario))
    except TerminalOutputError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    except (OSError, ValueError, ValidationError, YAMLError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    except Exception as error:  # CLI boundary reports unexpected runtime failures.
        print(f"runtime error: {type(error).__name__}: {error}", file=sys.stderr)
        return 1

    state = json.dumps(
        thaw_json(summary.final_state), sort_keys=True, separators=(",", ":")
    )
    metrics = ""
    if summary.metrics:
        encoded_metrics = json.dumps(
            thaw_json(summary.metrics), sort_keys=True, separators=(",", ":")
        )
        metrics = f" metrics={encoded_metrics}"
    print(
        f"run={summary.run_id} ticks={summary.ticks} "
        f"events={len(summary.events)} final_state={state}{metrics}"
    )
    failures = [
        event
        for event in summary.events
        if event.kind
        in {"cognition.failed", "cognition.malformed", "cognition.timed_out"}
    ]
    if failures:
        details = ", ".join(
            f"{event.actor_id}:{event.kind}({event.payload.get('reason', 'unknown')})"
            for event in failures
        )
        print(
            f"error: run completed with {len(failures)} cognition failure(s): "
            f"{details}",
            file=sys.stderr,
        )
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
