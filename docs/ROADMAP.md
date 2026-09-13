# AntFarm AI Roadmap

## Milestone M0: Foundation

M0 proves a deterministic, local-first vertical slice. Each item below is issue-ready; sequencing follows the numbered order unless an item explicitly depends only on an earlier contract.

## Progress

- **M0-01 — Complete:** package bootstrap, lockfile, local quality tooling, CLI entry point, and GitHub Actions CI are implemented.
- **M0-02 — Complete:** the strict versioned scenario schema, deterministic pool expansion, reference validation, and normalized JSON are implemented.
- **M0-03 — Complete:** immutable domain values, approved protocols, inward-import checks, and serialization round trips are implemented.
- **M0-04 — Complete:** deterministic ticks, seeded action ordering, validated-only
  mutation, and explicit malformed, timeout, rejected, and no-op outcomes are
  implemented.
- **M0-05 — Complete:** interval, cooldown, event-triggered, and idle scheduling,
  bounded agent-scoped recall, and memory/scheduler snapshot state are implemented.
- **M0-06 — Complete:** versioned ordered events, atomic SQLite event/checkpoint
  commits, rollback coverage, and deterministic checkpoint recovery are implemented.
- **M0-07 — Complete:** the deterministic mock provider and generic
  OpenAI-compatible chat-completions adapter support structured responses,
  model configuration, API-key environment variables, safe malformed-response
  handling, and enforced timeouts.
- **M0-08 — Complete:** validate, inspect, and run operate on documented
  examples; CLI failures use clear stderr messages and non-zero exit codes; and
  end-to-end tests prove matching seeded mock events and final state.

**M0 Foundation is complete.**

### M0-01: Repository and Python Bootstrap

**Acceptance criteria**

- An installable Python 3.12+ package uses the `src` layout, Hatchling, and a locked `uv` development environment.
- Ruff, mypy, pytest, pytest-asyncio, and GitHub Actions run through documented commands.
- CI completes without network model calls, credentials, a GPU, or external runtimes.

**Non-goals:** simulation behavior, packaging releases, containers, or production deployment.

### M0-02: Versioned Scenario Schema and Loader

**Acceptance criteria**

- YAML 1.2 is loaded safely and validated with a strict typed schema.
- Named providers/models, explicit agents, pools, personalities, actions, memory, scheduling, rules, metrics, storage, seed, and run limits are representable.
- Pool expansion and reference resolution are deterministic; unknown fields and invalid references fail clearly.
- Validation produces normalized JSON for persistence.

**Non-goals:** arbitrary Python imports, dynamic plugins, remote configuration, or a general rules language.

### M0-03: Core Domain Contracts and Values

**Acceptance criteria**

- The contracts in `docs/ARCHITECTURE.md` and their immutable supporting values exist with full type annotations.
- Domain and port modules import no adapter, SDK, transport, or database package.
- Scenario, action, event, and snapshot values pass serialization round-trip tests.

**Non-goals:** OASIS/CAMEL integration or broad framework base classes.

### M0-04: Deterministic Engine and Action Lifecycle

**Acceptance criteria**

- The engine advances ticks, uses one seeded random source, and processes due agents in stable order.
- Only environment-validated actions can mutate state.
- Malformed, timed-out, rejected, and no-op decisions emit ordered events without partial mutation.
- Repeated mock runs with the same scenario and seed produce identical logical results.

**Non-goals:** concurrent cognition, distributed workers, or high-volume optimization.

### M0-05: Scheduler and Baseline Memory

**Acceptance criteria**

- Interval, cooldown, event-triggered, and never-due/no-op behavior are covered by tests.
- Recall is bounded and scoped to an agent.
- In-memory memory and scheduler state survive snapshot/restore.

**Non-goals:** embeddings, semantic search, shared vector stores, or learned scheduling.

### M0-06: Events, Checkpoints, and SQLite

**Acceptance criteria**

- Events use a versioned envelope and monotonic per-run sequence.
- Each step atomically commits its event batch and latest checkpoint.
- A process can reopen SQLite and restore the latest complete state.
- Failure and rollback behavior is tested.

**Non-goals:** event sourcing, branching replay, Postgres, retention jobs, or multiple writers.

### M0-07: Model Provider Adapters

**Acceptance criteria**

- A deterministic mock provider supports all core and end-to-end tests.
- A generic OpenAI-compatible adapter supports configurable base URL, model, structured response, and timeout.
- Malformed responses fail safely, and provider-specific types do not enter domain contracts.

**Non-goals:** streaming, vendor parity, automatic provider discovery, Ollama-specific features, OASIS, or CAMEL.

### M0-08: CLI and Minimal End-to-End Scenario

**Acceptance criteria**

- `antfarm validate`, `antfarm run`, and `antfarm inspect` operate on a documented example scenario.
- The CLI reports validation and runtime failures clearly and returns non-zero exit codes.
- Two seeded mock runs have matching event order and final state.

**Non-goals:** REST, WebSockets, dashboards, interactive editing, or full replay tooling.

## Milestone M1: Experimentation

M1 turns the foundation into a small experiment workbench while preserving the
deterministic engine and provider-independent core.

## M1 Progress

- **M1-01 — Complete:** the finite shared-resource commons environment,
  harvest/contribute action family, compatibility validation, snapshot recovery,
  and deterministic end-to-end example are implemented.
- **M1-02 — Next:** add richer built-in event-derived metrics and persist their
  summaries without allowing collectors to mutate simulation state.
- **M1-03 — Planned:** compare completed runs using normalized scenario metadata,
  final state, event outcomes, and metric summaries.
- **M1-04 — Planned:** replay recorded accepted actions and outcomes without
  invoking model providers.

### M1-01: Multiple Built-in Environments and Actions

**Acceptance criteria**

- A finite shared-resource environment adds agent-scoped holdings and a common
  resource alongside the existing counter environment.
- Harvest and contribute actions are validated by the environment and applied in
  deterministic engine order.
- Scenario validation rejects environment/action mismatches before composition.
- The environment supports snapshot/restore and a documented deterministic
  example runs end to end.

**Non-goals:** dynamic plugins, user-imported Python, economic realism, markets,
or changing the engine-owned mutation lifecycle.

### M1-02: Built-in Metrics

**Acceptance criteria**

- Built-in metrics consume committed events observationally.
- Action, rejection, failure, and per-agent outcome summaries are deterministic.
- Metric state can be persisted and inspected without changing world state.

**Non-goals:** arbitrary metric plugins, dashboards, or external telemetry.

### M1-03: Run Comparison

**Acceptance criteria**

- Completed durable runs can be compared from the CLI.
- Comparisons identify scenario, final-state, outcome, and metric differences in
  a stable machine-readable format.
- Missing and incompatible runs fail clearly.

**Non-goals:** statistical inference, experiment scheduling, or a web UI.

### M1-04: Recorded-Action Replay

**Acceptance criteria**

- Replay uses recorded accepted actions and outcomes and never invokes a model.
- Replayed logical events and final state match the source run where compatible.
- Schema or environment incompatibility fails before partial replay mutation.

**Non-goals:** branching histories, editing event logs, or reproducing provider
text generation.

## Later Milestone Themes

- **M2 — Observation:** REST control/query API and, only when demanded by a live client, WebSocket event streaming.
- **M3 — Integrations:** concrete provider adapters and an evidence-led OASIS/CAMEL compatibility spike.
- **M4 — Scale:** profiling-led parallel cognition, Postgres, workers, retention policies, and larger simulations.

Dates and detailed scope are intentionally unset until M0 establishes measured constraints.
