"""Minimal non-interactive AntFarm command line interface."""

import argparse
import asyncio
import json
from collections.abc import Sequence
from pathlib import Path

from pydantic import ValidationError

from antfarm.config import load_scenario
from antfarm.runner import run_scenario


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="antfarm")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("validate", "run"):
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
        summary = asyncio.run(run_scenario(args.scenario))
    except (OSError, ValueError, ValidationError) as error:
        print(f"error: {error}")
        return 2

    state = json.dumps(dict(summary.final_state), sort_keys=True, separators=(",", ":"))
    print(
        f"run={summary.run_id} ticks={summary.ticks} "
        f"events={len(summary.events)} final_state={state}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
