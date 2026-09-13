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
- Interval, cooldown, and event-triggered scheduling with restorable state
- Bounded, agent-scoped in-memory recall with snapshot/restore
- Atomic SQLite event batches and deterministic checkpoint recovery
- A generic OpenAI-compatible provider with structured responses and timeouts
- Counter and shared-commons environments with validated action families
- An offline example scenario with unit and end-to-end tests

The repository bootstrap, strict scenario schema, core contracts, deterministic
engine lifecycle, baseline scheduling and memory, SQLite recovery, and model
provider adapters, CLI inspection, and the minimal end-to-end workflow are
complete. See [the roadmap](docs/ROADMAP.md) for current progress.

## Quick Start

Requirements: Python 3.12+ and `uv`.

```console
uv sync --dev
uv run antfarm validate scenarios/examples/minimal.yaml
uv run antfarm inspect scenarios/examples/minimal.yaml
uv run antfarm run scenarios/examples/minimal.yaml
```

The example runs entirely offline and produces:

```text
run=minimal ticks=1 events=10 final_state={"value":3}
```

The deterministic commons example exercises two agents, shared-resource
contention, and contributions:

```console
uv run antfarm validate scenarios/examples/commons.yaml
uv run antfarm run scenarios/examples/commons.yaml
```

It produces:

```text
run=commons-example ticks=2 events=20 final_state={"holdings":{"alice":2,"bob":1},"resource":2}
```

`inspect` prints the canonical scenario JSON, including deterministically expanded
agents, without composing providers or starting a run.

## Try a Local Model with Ollama

The included example uses Ollama's OpenAI-compatible endpoint and structured
outputs. Start Ollama, then run:

```console
ollama pull qwen3.5:0.8b
uv run antfarm validate scenarios/examples/ollama.yaml
uv run antfarm inspect scenarios/examples/ollama.yaml
uv run antfarm run scenarios/examples/ollama.yaml
```

The final command asks the local model for a validated `increment` action. A
successful response completes one tick with six events and a positive counter
value. With Ollama 0.34.0 and `qwen3.5:0.8b`, the verified output was:

```text
run=ollama-local ticks=1 events=6 final_state={"value":1}
```

The scenario disables model reasoning so the small model returns structured
content within its completion budget. It sends no API key and makes no hosted
model request.

## Development Checks

```console
uv run pytest
uv run ruff check .
uv run mypy src tests
```

Architecture and accepted decisions are documented under [`docs/`](docs/).
