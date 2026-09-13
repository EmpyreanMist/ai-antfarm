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
- Deterministic event-derived metrics persisted with simulation checkpoints
- Immutable per-agent identity and private personality in model requests
- Multi-agent scenarios that share one local model backend without sharing recall
- Opt-in public speech with authenticated senders and next-tick visibility
- Bounded public rosters, message history, and per-agent retained memory
- An offline example scenario with unit and end-to-end tests

M0, M1-01/M1-02, and M2-01/M2-02 are complete. The next milestone adds paced
continuous execution, fair bounded cognition, recovery on failed commits, and
safe stopping. See [the roadmap](docs/ROADMAP.md) for current progress.

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
run=commons-example ticks=2 events=20 final_state={"holdings":{"alice":2,"bob":1},"resource":2} metrics={...}
```

The metrics object contains applied-action totals by kind, rejection and
cognition-failure totals, and terminal outcome counts for each agent. Metric
collectors receive events only after the step commits and never receive world
state.

The finite shared-model mock example runs three distinct personalities through
one provider instance and remains entirely offline:

```console
uv run antfarm validate scenarios/examples/shared-model-mock.yaml
uv run antfarm inspect scenarios/examples/shared-model-mock.yaml
uv run antfarm run scenarios/examples/shared-model-mock.yaml
```

It completes two ticks with six applied actions and finishes with resource `4`
and holdings `alice=1`, `bob=0`, `charlie=1`.

`inspect` prints the canonical scenario JSON, including deterministically expanded
agents, without composing providers or starting a run.

The finite social mock example adds validated `say` actions while staying fully
offline:

```console
uv run antfarm validate scenarios/examples/social-mock.yaml
uv run antfarm inspect scenarios/examples/social-mock.yaml
uv run antfarm run scenarios/examples/social-mock.yaml
```

It completes three ticks with nine applied actions, including four public
messages. Speech accepted in one tick is not visible to any later agent in that
same tick; it enters every agent's bounded memory and public observation on the
next tick. The sender ID and tick come from the engine rather than model-supplied
message metadata. Public history and rosters are bounded by `environment.social`,
and retained private memory is bounded by `memory.retention_limit`. Older messages
leave live context but remain in the SQLite event log when SQLite storage is used.

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

For a finite three-agent commons run using the same Ollama model and provider
instance for every agent:

```console
ollama serve
ollama pull qwen3.5:0.8b
uv run antfarm validate scenarios/examples/shared-model-ollama.yaml
uv run antfarm inspect scenarios/examples/shared-model-ollama.yaml
uv run antfarm run scenarios/examples/shared-model-ollama.yaml
```

Run `ollama serve` in its own VS Code PowerShell terminal if the Ollama desktop
service is not already listening. The scenario allows 180 seconds per request for
a cold model start. Its exact actions and final state can vary because real model
generation is not deterministic. A successful run reports one completed tick;
each of Alice, Bob, and Charlie receives its own identity, personality, observation,
and private recall while sharing the `qwen-local` model configuration.

The three-agent path was smoke-tested with Ollama 0.34.0 and
`qwen3.5:0.8b`. One complete run took about 10 seconds on the test machine and
produced three validated actions with no failures or rejections. Model-selected
actions and timing are observational and can differ on other machines.

For a finite conversation using the same backend and three distinct private
personalities:

```console
uv run antfarm validate scenarios/examples/social-ollama.yaml
uv run antfarm inspect scenarios/examples/social-ollama.yaml
uv run antfarm run scenarios/examples/social-ollama.yaml
```

The social run allows each cognition to choose one `say`, `harvest`,
`contribute`, or no-op decision. Accepted speech is included in later requests as
untrusted simulation data; it cannot add tools, forge its sender, or bypass action
validation. Exact dialogue and physical actions vary with the model. This M2-02
scenario is finite and prints its summary after completion; continuous execution
and live per-event rendering are later roadmap milestones.

To route only Charlie to a second local model, first pull that model, then copy the
`qwen-local` entry under `models` to a new key, change its `model` tag, and set
Charlie's `model_ref` to the new key. This creates one provider adapter per used
model reference; it does not create a process per agent. Ollama controls loading
and memory residency, and multiple models need not stay resident at once.

If the configured model name does not match `ollama list`, Ollama is stopped, or a
request exceeds `timeout_seconds`, the run exits non-zero after recording bounded
`cognition.failed` or `cognition.timed_out` events. No proposed action from that
failed decision changes the world. Increase `timeout_seconds` for slower cold
starts. Validation and inspection remain offline and do not contact Ollama.

To inspect durable speech, copy either social scenario, change its storage block
to a unique local database path, run it once, and then use this PowerShell snippet
from the repository root:

```powershell
@'
from antfarm.adapters.storage import SQLiteStorage
from antfarm.domain import RunId

with SQLiteStorage("social-runs.db") as storage:
    for event in storage.read_events(RunId("social-mock")):
        if event.kind == "action.applied" and event.payload.get("kind") == "say":
            print(event.payload["message"])
'@ | uv run python -
```

Set the `RunId` and database filename to the values in the copied scenario. Expect
one line per accepted message, including its stable ID, authenticated sender,
tick, and text. Use a fresh run ID or database path for another run because run
IDs are unique within a database.

## Development Checks

```console
uv run pytest
uv run ruff check .
uv run mypy src tests
```

Architecture and accepted decisions are documented under [`docs/`](docs/).
