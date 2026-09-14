# AntFarm AI Roadmap

## Purpose

This is the active plan from the completed terminal-society baseline onward. The
detailed M0-M2 implementation history is preserved unchanged in
[`ROADMAP_old.md`](ROADMAP_old.md). Completed work is summarized here only where
it establishes a dependency or constraint for future work.

The roadmap is incremental. Only the next milestone is specified with detailed
acceptance criteria; later phases describe direction and will be refined after the
preceding contracts are implemented and tested.

## Completed Baseline

- **M0 — Foundation:** strict scenarios, deterministic engine and scheduling,
  provider ports, bounded memory, ordered events, SQLite checkpoints, mock and
  OpenAI-compatible providers, and CLI workflows.
- **M1-01/M1-02 — Environments and metrics:** counter and commons environments,
  validated action families, and checkpointed event-derived metrics.
- **M2-01 through M2-05 — Interactive terminal society:** distinct private agent
  context over shared models, validated public speech, paced continuous execution,
  safe cancellation, live committed-event rendering, runtime model selection, and
  Ollama preflight.

The current system can run several local-model agents that act and talk in a
shared society. The next constraint is behavioral sameness: profiles, incentives,
economic differences, visibility, and population generation are not yet rich
enough to sustain meaningfully distinct behavior.

## M3: Rich Agents, Economy, and Randomized Societies — Next

**Outcome:** agent differences are configurable, validated, inspectable,
reproducible, available to cognition, selectively observable by other agents, and
usable through a transport-neutral application layer. This milestone does not
build the HTTP API or Next.js frontend.

### M3-01: Rich Profiles and Behavioral Cognition

**Status: Complete.** Implemented as additive schema-version-1 profile sections;
legacy personality-only scenarios remain supported.

- Add validated first-class profiles for identity, personality, goals, beliefs,
  values, communication preferences, broad numeric behavioral traits, social
  status, and optional private information.
- Use typed, composable profile sections so future dimensions do not become a
  collection of special cases in cognition code. Existing scenarios without rich
  sections remain valid where reasonably possible.
- Support enough independent traits to express generosity, greed, selfishness,
  empathy, assertiveness, agreeableness, honesty, conformity, patience,
  impulsiveness, risk tolerance, competitiveness, envy, aggression, trust,
  ambition, materialism, fairness, forgiveness, and sociability. Opposing or
  conflicting values are valid; profiles are not fixed archetypes.
- Deliver the active agent's relevant profile to cognition in a compact,
  provider-neutral representation. Traits influence a model's choice rather than
  directly selecting actions through simplistic thresholds.
- Strengthen the generic social instruction so an agent follows its own goals and
  incentives, advances a discussion with a proposal or action, neither seeks
  consensus nor conflict artificially, and does not invent unobserved facts.
- Cover profile validation, context construction, distinct mock-agent contexts,
  anti-repetition guidance, and compatibility with existing finite, continuous,
  and live paths using offline tests.

### M3-02: Economic State and Information Boundaries

**Status: Complete.** Implemented additively in schema version 1 with private-by-
default visibility and per-agent commons endowment overrides; recurring income is
descriptive state only and does not imply automatic accrual or market policy.

- Represent simple economic differences including money, reusable holdings or
  resources, optional recurring income, and economic/social status. Reuse the
  existing resource model where its semantics fit rather than duplicating it.
- Make meaningful initial inequality possible without embedding policy or market
  behavior that belongs to a future environment.
- Define explicit, validated visibility metadata that can grow beyond wealth to
  possessions, occupation, status, reputation, relationships, health, and group
  membership.
- Keep public profile data, observable runtime state, private profile data,
  private memory, and internal/system state as separate concepts. An observer sees
  another agent's economic information only when its visibility permits it.
- Include the active agent's own economic situation and permitted observations of
  others in cognition without exposing another agent's private beliefs, wealth,
  profile fields, or memory.
- Add dedicated context-isolation and private-data leakage tests, including public
  and private wealth and per-agent private profile data.

### M3-03: Deterministic Population and Runtime Resolution

**Status: Complete.** Implemented with validated explicit, generated, and mixed
population policies; seeded uniform trait/economic ranges; and an immutable
application resolver that materializes ephemeral population, profile, model, and
seed overrides before composition or durable run creation.

- Support fully explicit populations, fully generated populations, and mixed
  populations with selective per-agent and per-field randomization.
- Begin with deterministic local generation and seeded uniform numeric ranges for
  traits and appropriate economic fields. Validate ranges, seeds, modes, values,
  identifiers, visibility, and unsupported structures; never silently clamp.
- Apply explicit values after generated defaults so manual configuration always
  wins. The same source scenario, runtime overrides, and seed must resolve to the
  same population; different seeds should be able to produce different results.
- Leave clean extension points for deterministic template selection of goals,
  beliefs, personalities, communication styles, occupations, and socioeconomic
  backgrounds. Do not require an LLM at startup, and do not add advanced
  distributions or inequality presets until a concrete experiment needs them.
- Add an application operation that derives a resolved run configuration from a
  loaded scenario plus ephemeral population, profile, model, and seed overrides.
  It must validate before run/database creation and must never mutate the source
  object or rewrite its YAML file.
- Test full, partial, and economic randomization; same-seed reproducibility;
  different-seed variation; explicit override precedence; source immutability; and
  failure before durable run creation.

### M3-04: Inspection, Persistence, and Acceptance

- Expose resolved agents and their inspectable public/configuration fields before
  a run starts through application services used by the CLI and tests.
- Establish a small application facade for loading a scenario, resolving a
  population, inspecting resolved agents, starting and stopping a run, and reading
  run, agent, snapshot, and event data. Exact interfaces should follow existing
  contracts and remain independent of CLI or future HTTP types.
- Persist the generation seed, resolved profiles and traits, initial economic
  state, and relevant runtime overrides with each run. Historical inspection must
  not regenerate a population from a changed source scenario.
- Add static relationship and reputation value foundations only where needed to
  keep the profile model extensible. Dynamic evolution remains deferred.
- Provide three documented examples: a manually authored deterministic society, a
  randomized society, and a mixed explicit/random society. Include a contrasting
  population that exposes wealth and behavioral differences without making those
  examples built-in archetypes.
- Document traits, personality, goals, beliefs, communication, economy,
  visibility, seeded and selective randomization, resolved-population inspection,
  and runtime overrides.
- Run the full offline pytest suite, Ruff, strict mypy, and `git diff --check` at
  milestone completion. Preserve live/continuous execution, providers, SQLite,
  cancellation, cooldowns, atomic rollback, committed-event rendering, model
  override behavior, context isolation, and output sanitization.

**M3 deferred work:** full relationship dynamics, reputation propagation,
institutions, markets, advanced distributions and presets, semantic memory, a
network API, and frontend code.

## M4: Stable Application and Service Layer

Consolidate transport-neutral commands, queries, lifecycle management, error
contracts, and event subscriptions around the M3 application facade. Remove any
remaining CLI-only orchestration so CLI, tests, and future transports execute the
same behavior. Define pagination, filtering, concurrency, and long-running-run
semantics only as required by the control API. Keep persistence models and domain
objects from becoming accidental public transport contracts.

## M5: HTTP and WebSocket Control API

Add a versioned HTTP adapter for scenario/configuration workflows, population
inspection, run lifecycle commands, snapshots, agents, events, and metrics. Add
WebSocket delivery for committed live events and lifecycle updates where polling
is insufficient. The API calls M4 services directly; it never spawns the CLI or
parses terminal output. Address authentication, cancellation, backpressure,
reconnection, and bounded history before calling the transport stable.

## M6: Next.js Control Plane

Build a Next.js client over the HTTP/WebSocket API. The first slice should load a
scenario, adjust runtime population/profile/model/seed settings, generate and
inspect resolved agents, start or stop a run, and watch committed activity. The
server remains authoritative; the frontend neither embeds simulation logic nor
reads SQLite directly. Rich editors and visual polish follow a complete basic
control flow.

## M7: Visualization, Replay, and Experiment Analysis

Implement recorded-action replay without model calls and stable comparison of
completed runs, restoring the deferred M1-03/M1-04 outcomes on top of mature run
queries. Add time-series metrics, society/economic visualizations, replay views,
and experiment comparison incrementally. Statistical analysis and large-scale
experiment scheduling require separate evidence and design.

## M8: Deeper Social Systems and Environments

Advance relationships, reputation, groups, institutions, occupations, markets,
governance, and richer environments after profile visibility and replay make
their effects observable and testable. Add one validated domain need at a time;
do not hard-code an exhaustive social ontology or let new systems bypass
environment-owned mutation.

## Delivery Workflow

For each milestone, understand its scope and relevant architecture, inspect the
affected code and documentation, implement focused changes, and run proportionate
automated checks. A repository-wide reread or manual revalidation of unrelated
completed milestones is not a prerequisite. The full automated suite and static
checks protect existing behavior before changes are committed and pushed. Manual
Ollama, GPU, latency, and interactive checks remain user-run unless explicitly
requested.
