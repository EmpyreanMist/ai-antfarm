# AntFarm AI

[![CI](https://github.com/EmpyreanMist/ai-antfarm/actions/workflows/ci.yml/badge.svg)](https://github.com/EmpyreanMist/ai-antfarm/actions/workflows/ci.yml)

AntFarm AI is a local-first Python framework for reproducible artificial-society simulations. The domain owns agents, environments, actions, state, time, and events; external model providers and persistence systems integrate through ports and adapters.

## Current Status

The foundation currently includes:

- An installable Python 3.12+ package with a locked `uv` environment
- Strict, safe YAML 1.2 scenario validation and canonical normalization
- Deterministic agent-pool expansion and reference validation
- Immutable domain values and provider-independent protocols
- A deterministic mock model, counter environment, and validated-action engine
- Ordered failure, timeout, rejection, no-op, and applied-action events
- An offline example scenario with unit and end-to-end tests

The repository bootstrap, strict scenario schema, core contracts, and deterministic
engine lifecycle are complete. SQLite recovery, richer scheduling and memory
behavior, a real OpenAI-compatible provider, and the complete CLI inspection surface
remain planned M0 work. See [the roadmap](docs/ROADMAP.md) for current progress.

## Quick Start

Requirements: Python 3.12+ and `uv`.

```console
uv sync --dev
uv run antfarm validate scenarios/examples/minimal.yaml
uv run antfarm run scenarios/examples/minimal.yaml
```

The example runs entirely offline and produces:

```text
run=minimal ticks=1 events=10 final_state={"value":3}
```

## Development Checks

```console
uv run pytest
uv run ruff check .
uv run mypy src tests
```

Architecture and accepted decisions are documented under [`docs/`](docs/).
