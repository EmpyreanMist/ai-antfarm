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
- **M0-08 — Next:** complete the CLI and minimal end-to-end scenario surface.

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

## Later Milestone Themes

- **M1 — Experimentation:** multiple environment/action implementations, richer built-in metrics, run comparison, and recorded-action replay.
- **M2 — Observation:** REST control/query API and, only when demanded by a live client, WebSocket event streaming.
- **M3 — Integrations:** concrete provider adapters and an evidence-led OASIS/CAMEL compatibility spike.
- **M4 — Scale:** profiling-led parallel cognition, Postgres, workers, retention policies, and larger simulations.

Dates and detailed scope are intentionally unset until M0 establishes measured constraints.
