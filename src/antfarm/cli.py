"""Minimal non-interactive AntFarm command line interface."""

import argparse
import asyncio
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from pydantic import ValidationError
from ruamel.yaml.error import YAMLError

from antfarm.config import load_scenario
from antfarm.domain.json_values import thaw_json
from antfarm.runner import run_scenario


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="antfarm")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("validate", "run", "inspect"):
        command = commands.add_parser(name)
        command.add_argument("scenario", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "validate":
            config = load_scenario(args.scenario)
            print(f"valid scenario: {config.run.id}")
            return 0
        if args.command == "inspect":
            config = load_scenario(args.scenario)
            print(config.normalized_json())
            return 0
        summary = asyncio.run(run_scenario(args.scenario))
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
