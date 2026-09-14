# AntFarm AI

[![CI](https://github.com/EmpyreanMist/ai-antfarm/actions/workflows/ci.yml/badge.svg)](https://github.com/EmpyreanMist/ai-antfarm/actions/workflows/ci.yml)

AntFarm AI is a local-first simulation platform for reproducible experiments with
autonomous AI agents. Its current major experience is an artificial society; the
roadmap evolves that capability into the first built-in Society mode alongside
future purpose-built modes and fully custom simulations. The domain owns agents,
environments, actions, state, time, and events; external model providers,
persistence, transports, and presentation integrate through ports and adapters.

## Current Status

The foundation currently includes:

- An installable Python 3.12+ package with a locked `uv` environment
- Strict, safe YAML 1.2 scenario validation and canonical normalization
- Deterministic agent-pool expansion and reference validation
- Immutable domain values and provider-independent protocols
- A deterministic mock model, counter environment, and validated-action engine
- Ordered failure, timeout, rejection, no-op, and applied-action events
- Fair budgeted scheduling with cadence overrides, staggering, wakeups, and retries
- Bounded, agent-scoped in-memory recall with snapshot/restore
- Atomic SQLite event batches and deterministic checkpoint recovery
- A generic OpenAI-compatible provider with structured responses and timeouts
- Counter and shared-commons environments with validated action families
- Deterministic event-derived metrics persisted with simulation checkpoints
- Immutable per-agent identity and private personality in model requests
- Multi-agent scenarios that share one local model backend without sharing recall
- Opt-in public speech with authenticated senders and next-tick visibility
- Bounded public rosters, message history, and per-agent retained memory
- Paced continuous execution with atomic cancellation and bounded live event buffers
- Plain live terminal rendering of committed speech, actions, rejections, and failures
- Validated live societies of 1–10 distinct agents over shared model configurations
- Ephemeral `--model` selection with Ollama availability preflight
- Quiet society-first output plus explicit `--verbose` lifecycle diagnostics
- Stable transport-neutral run lifecycle, inspection, query, error, pagination,
  and committed-event subscription contracts
- An offline example scenario with unit and end-to-end tests

M0, M1-01/M1-02, M2-01 through M2-05, M3-01 through M3-04, and M4 are complete. See
[the roadmap](docs/ROADMAP.md) for current progress.

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

`inspect` resolves the population and prints the effective generation seed plus
each resolved agent's complete configuration and explicitly public projection. It
does not compose providers, create a database, or start a run.

## Rich Profiles and Population Resolution

Three offline examples cover the supported authoring modes:

```console
uv run antfarm inspect scenarios/examples/society-manual.yaml
uv run antfarm inspect scenarios/examples/society-randomized.yaml
uv run antfarm inspect scenarios/examples/society-mixed.yaml
```

`society-manual.yaml` is fully authored and deterministic. Its two agents contrast
patient, generous cooperation with competitive, impulsive self-interest, as well
as money, income, occupation, status, reputation, and directed relationships.
These are ordinary composable values, not built-in archetypes.

`society-randomized.yaml` generates four agents from one local seed. Trait ranges
are normalized numbers from `0` to `1`; economic ranges are inclusive,
non-negative integers. `mode: all` applies the default range to every behavioral
trait. `mode: selected` generates only named traits. `society-mixed.yaml` combines
an authored manager with a generated worker: generated defaults are applied first
and explicit profile values win field by field.

Profiles can independently configure identity, personality, goals, beliefs,
values, communication preferences, behavioral traits, social status, economics,
reputation, relationships, visibility, and private information. Money, recurring
income, resources, and occupation are initial descriptive facts; they do not add
income accrual or market rules. Reputation and relationships are also static in
this milestone. Visibility is private by default and separately controls wealth,
possessions, occupation, status, reputation, and relationships.

Runtime seed, population, per-agent profile, model-assignment, active-count, run-
ID, and compatible live-model overrides are ephemeral: they never rewrite YAML.
The shared application facade resolves and inspects them before a run:

```python
from antfarm.facade import AntFarmApplication
from antfarm.population import RuntimeOverrides

application = AntFarmApplication()
source = application.load_scenario("scenarios/examples/society-mixed.yaml")
resolved = application.resolve_population(source, RuntimeOverrides(seed=29))
for agent in application.inspect_resolved_agents(resolved):
    print(agent.agent_id, dict(agent.configuration), dict(agent.public))
```

Starting through `application.start_run(...)` returns a managed handle.
`wait_run` and `stop_run` return the last atomic snapshot; `read_run`,
`read_agents`, `read_snapshot`, and `read_events` expose durable data without CLI
or HTTP types. To query a historical SQLite run after restart, construct the
facade with an open `SQLiteStorage`. The stored resolved configuration and
runtime-override provenance are used, so changing the source scenario cannot
regenerate or alter historical agents.

Transport adapters should use the stable command/query contracts instead of the
compatibility handle:

```python
from antfarm.application import EventQuery, RunStatus
from antfarm.facade import StartRunCommand

state = application.start(StartRunCommand(resolved))
snapshot = await application.wait_run(state.run_id)
assert application.read_run_state(state.run_id).status is RunStatus.COMPLETED
page = application.query_events(EventQuery(state.run_id, limit=100))
```

Event pages are ordered by sequence and expose `next_after`; optional kind,
actor, and inclusive tick filters are applied by storage. Agent pages use offsets.
Both are capped at 1,000 items. Different run IDs can execute concurrently in one
application, while duplicate IDs return a stable `conflict` error. Continuous
runs remain active until stopped and return their last complete atomic snapshot.

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
scenario remains finite and prints its summary after completion unless live and
continuous options are explicitly requested.

The checked-in Qwen configuration uses the OpenAI-compatible
`reasoning_effort: none` field, temperature `0`, a fixed seed, and a bounded
completion budget. Do not replace `reasoning_effort` with Ollama's native
`think` field on the `/v1/chat/completions` endpoint. The generic adapter sends
the exact JSON Schema in both `response_format` and the system instruction, and
accepts either bare structured JSON or a single Markdown JSON fence for compatible
endpoints that wrap an otherwise valid response.

Manual M2-02 acceptance with Ollama and `qwen3.5:0.8b` passed after fix
`24f1c1e`: three ticks produced 41 events, eight applied `say` actions, eight
persisted messages, zero malformed/failed/timed-out cognitions, one rejected
action, and no unintended world-state mutation. The small model's dialogue was
simplistic and sometimes self-referential, but that is a model-quality limitation,
not a failure of the social action or structured-output pipeline.

## Run a Live Society and Stop Safely

Live mode is explicit and requires continuous mode. Loading any existing scenario
without both options remains finite and uses `run.ticks`. The live examples define
ten distinct identities, default `run.active_agents` to three, stagger cognition,
and allow one model invocation per tick. `--agents N` revalidates and selects the
first 1–10 configured identities; 0, values above 10, or counts larger than the
configured population fail clearly.

Paced execution without live event rendering remains available independently:

```powershell
uv run antfarm run scenarios/examples/continuous-social-mock.yaml `
  --continuous `
  --tick-seconds 1
```

The mock path is the complete offline demonstration:

```powershell
Set-Location C:\Programmering\ai-antfarm
uv run antfarm validate scenarios/examples/live-social-mock.yaml
uv run antfarm inspect scenarios/examples/live-social-mock.yaml
uv run antfarm run scenarios/examples/live-social-mock.yaml `
  --live `
  --continuous `
  --agents 3 `
  --tick-seconds 1
```

Live runs allocate a fresh run ID automatically, so repeated runs append distinct
runs to the example SQLite database instead of overwriting a durable run. Startup
shows the run ID, active identities, provider/model assignments, cognition budget,
cadence, database, and Ctrl+C instruction. Normal output contains committed
`[tick N]` society activity without permanent thinking/waiting lines. Add
`--verbose` for separately marked operational status and internal configuration
references. Output is flushed plain text, works when redirected, and neutralizes
terminal control characters in model text.

### Exact Ollama workflow for Windows and VS Code PowerShell

Check whether Ollama is available and serving:

```powershell
ollama --version
Get-Process ollama -ErrorAction SilentlyContinue
Invoke-RestMethod http://localhost:11434/api/tags
```

If the request fails and the desktop application is not already serving, start it
in a dedicated VS Code PowerShell terminal and leave that terminal open:

```powershell
ollama serve
```

In a second VS Code PowerShell terminal, list and download models, then validate
and inspect the scenario. Validation and inspection do not contact Ollama:

```powershell
Set-Location C:\Programmering\ai-antfarm
ollama list
ollama pull gemma4:e2b
ollama list
uv run antfarm validate scenarios/examples/live-social-ollama.yaml
uv run antfarm inspect scenarios/examples/live-social-ollama.yaml
```

Start the default three-agent society:

```powershell
uv run antfarm run scenarios/examples/live-social-ollama.yaml `
  --live `
  --continuous `
  --agents 3 `
  --model gemma4:e2b `
  --tick-seconds 1
```

Switch the concrete model for another run without editing the scenario:

```powershell
--model qwen3.5:0.8b
--model gemma4:e4b
```

The selected tag replaces the concrete model on every model configuration used by
the active agents for that run only. Provider URL, structured-output behavior,
timeout, and generation parameters still come from the validated scenario. The
scenario file is never rewritten. Omitting `--model` uses its configured default.
Runtime override is currently global; per-agent CLI model assignment is deferred.

To include cognition and pacing diagnostics, add verbose mode:

```powershell
uv run antfarm run scenarios/examples/live-social-ollama.yaml `
  --live `
  --continuous `
  --agents 3 `
  --model gemma4:e2b `
  --tick-seconds 1 `
  --verbose
```

Start the maximum M2-04 population with the same configuration:

```powershell
uv run antfarm run scenarios/examples/live-social-ollama.yaml `
  --live `
  --continuous `
  --agents 10 `
  --model gemma4:e2b `
  --tick-seconds 1
```

Press Ctrl+C once to stop. AntFarm starts no further cognition, cancels an
in-flight HTTP request, restores any uncommitted step, closes providers and
storage, and prints the last committed tick, active count, final world, final
metrics, and database location. A slow response may make a tick exceed one second;
steps never overlap and no catch-up burst is launched.

Copy the exact value on the `Run` line in the live header, then inspect its
checkpoint:

```powershell
$env:ANTFARM_RUN_ID = "live-social-ollama-PASTE-THE-PRINTED-SUFFIX"
@'
import os
from antfarm.adapters.storage import SQLiteStorage
from antfarm.domain import RunId

with SQLiteStorage("live-social-ollama.db") as storage:
    checkpoint = storage.load_latest(RunId(os.environ["ANTFARM_RUN_ID"]))
    if checkpoint is None:
        raise SystemExit("checkpoint not found")
    print("tick", checkpoint.snapshot.tick)
    print("world", dict(checkpoint.snapshot.world))
    print("metrics", dict(checkpoint.snapshot.metrics))
'@ | uv run python -
```

The default ten-agent configuration points every agent at the role-named
`local-model` reference, so one Ollama runtime and one model configuration serve
the whole society. It does not
create a model process per agent. To test mixed assignments, first run
`ollama pull llama3.2:1b`, then change selected agents such as Heidi, Ivan, and
Judy to `model_ref: optional-second-local` in a copied scenario. Run with
`--agents 10`; the remaining agents continue using `local-model`. A model tag alone
does not guarantee compatibility with the installed runtime.

If a model is missing, compare the YAML `models.*.model` values with `ollama list`,
or compare the value passed to `--model`, run the matching `ollama pull <tag>`,
and start a fresh live run. The live command checks Ollama's `/api/tags` inventory
before creating the run and prints installed tags plus the exact pull command when
the selection is missing. If Ollama is unavailable, start `ollama serve` and retry.
There is no fallback and AntFarm never installs models automatically. Failures
after startup remain committed cognition failure events with no action effect;
retry cooldowns avoid a tight loop.

### Manual live-society smoke test

Record `ollama --version`, the exact model tags from `ollama list`, GPU/runtime
details, and the date after testing. Verify without requiring exact wording that:

- several agents act without prompts and later agents react to prior public speech;
- identities, personalities, private recall, and holdings remain distinct;
- both 3-agent and 10-agent runs involve exactly the selected identities;
- one shared model serves multiple agents, then selected agents use the optional
  second model while the remainder keep the default;
- harvest and contribute are applied only when environment validation accepts them;
- Ctrl+C reports a checkpoint matching the last complete committed tick;
- a stopped Ollama runtime and a missing model produce clean bounded failures.

Real Ollama, GPU, latency, dialogue-quality, model-compatibility, and interactive
Ctrl+C testing are manual acceptance work and are not part of the offline suite.

## Development Checks

```console
uv run pytest
uv run ruff check .
uv run mypy src tests
```

Architecture and accepted decisions are documented under [`docs/`](docs/).
