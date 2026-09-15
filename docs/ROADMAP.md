# AntFarm AI Roadmap

## Purpose

This is the active plan from the completed M0-M8 baseline onward. The detailed
M0-M2 implementation history is preserved unchanged in
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

The current system can resolve, inspect, run, stop, and query several distinct
local-model agents acting and talking in a shared society. M3 added rich profiles,
economic differences, visibility, and deterministic population generation; M4
made those workflows available through stable transport-neutral service
contracts. Society is the first substantial simulation experience, not the
mandatory object model for every future AntFarm simulation.

## M3: Rich Agents, Economy, and Randomized Societies

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

**Status: Complete.** Implemented with transport-neutral application inspection,
managed run lifecycle and queries, durable resolved configurations and runtime-
override provenance, static relationship/reputation values, and three offline
society examples.

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

**Status: Complete.** Implemented as an additive service contract over the M3
facade. Existing `runner` and direct facade entry points remain compatible, while
new transports can use typed commands, lifecycle/query DTOs, bounded pages,
stable errors, and post-commit event subscriptions without receiving engine,
domain, or persistence objects.

Consolidate transport-neutral commands, queries, lifecycle management, error
contracts, and event subscriptions around the M3 application facade. Remove any
remaining CLI-only orchestration so CLI, tests, and future transports execute the
same behavior. Define pagination, filtering, concurrency, and long-running-run
semantics only as required by the control API. Keep persistence models and domain
objects from becoming accidental public transport contracts.

- Define bounded and continuous start/stop commands with explicit running,
  stopping, completed, stopped, and failed states. A facade owns at most one task
  per run ID, rejects duplicate ownership with a stable conflict error, and can
  run different IDs concurrently in the same event loop.
- Expose immutable run, snapshot, agent, event, page, and error DTOs. Stable error
  codes distinguish invalid arguments, invalid scenarios, missing resources,
  conflicts, invalid lifecycle transitions, and execution failures.
- Bound agent and event pages to at most 1,000 items. Event queries use an ordered
  sequence cursor and support kind, actor, and inclusive tick filtering in both
  memory and SQLite storage; agent queries use a deterministic offset.
- Deliver selected committed events as transport-neutral event views through
  cancellable subscriptions. Durable event queries remain the recovery path for
  consumers that subscribe late or reconnect.
- Centralize finite and continuous composition, execution, pacing, cancellation,
  cleanup, and post-commit batch handling in `AntFarmApplication`. The legacy
  runner keeps only scenario/live presentation compatibility and delegates run
  ownership to that service.
- Keep the continuous runner non-accumulating and explicitly stoppable. Stop and
  cancellation return the last complete atomic snapshot; terminal states reject
  repeated stop commands.
- Cover lifecycle transitions, conflicts, validation, pagination, filtering,
  subscriptions, SQLite parity, CLI compatibility, and live output behavior with
  offline automated tests.

## M5: Minimum Web Control Plane

**Status: Complete.** Implemented as a versioned FastAPI adapter, bounded
committed-event WebSocket stream, server-owned Society scenario catalog, and
Next.js control plane. The browser supports runtime configuration, resolved-agent
preview, bounded and continuous starts, live activity, agent/world inspection,
safe stop, and completed-run inspection over M4 services. The initial topology is
an explicitly local, trusted-operator deployment; distributed ownership and the
generic simulation builder remain deferred.

**Outcome:** a user can complete the existing Society workflow in a browser: open
AntFarm, choose an available Society scenario, configure supported runtime
options, preview resolved agents, start a run, watch committed activity live,
inspect basic state, stop the run, and inspect its durable result. This is a real
end-to-end vertical slice over M4, not a mock interface or the final custom
simulation editor.

Build the smallest versioned HTTP/WebSocket adapter and Next.js client that prove
this path together. Do not split transport and frontend into separate milestones
if that postpones a usable browser experience. Scope the first release to the
implemented Society scenarios and M3/M4 configuration surface; do not generalize
all simulation concepts first.

### M5 acceptance criteria

- Provide a small server-owned catalog of supported example scenarios and their
  presentation metadata. The browser can list and select them without receiving
  arbitrary filesystem access.
- Map versioned HTTP commands and queries onto `AntFarmApplication` for scenario
  loading, population resolution, resolved-agent inspection, run start/stop,
  lifecycle state, latest snapshot, ordered event pages, and completed-run
  inspection. Preserve M4 error codes and bounded pagination rather than exposing
  engine, domain, persistence, or provider objects as wire contracts.
- Let the Society form edit the important runtime choices already supported by
  M3/M4: run mode, tick pacing where applicable, active population, seed, model
  selection/assignment, and supported profile overrides. Validate and resolve on
  the server, then show the resulting agents before a run is created.
- Stream committed event views and lifecycle changes to the browser through a
  WebSocket adapter justified by the M4 subscription boundary. Define bounded
  per-connection buffering and a sequence cursor/reconnect path that recovers gaps
  through durable event queries. Slow or disconnected clients must not block,
  mutate, or roll back the simulation.
- Provide modest but usable Next.js screens for scenario selection, configuration
  and preview, active-run control, a live activity feed, basic agent/snapshot
  inspection, and completed-run inspection. The UI need not include a generic
  schema editor, node editor, replay engine, or polished visualization system.
- Keep the server authoritative. The frontend must not call the CLI, parse
  terminal output, read SQLite, apply actions, implement scheduling, or derive
  authoritative simulation state.
- Keep CLI and library workflows compatible and routed through the same
  application behavior. Scenario resolution must remain deterministic and
  non-LLM-dependent, and the exact resolved configuration must remain durable.
- Establish only the deployment, origin, authentication, and run-ownership
  assumptions required for the first supported local web topology. Document
  limitations explicitly; distributed workers and multi-node ownership remain
  out of scope.
- Cover the API mappings, serialization, lifecycle/error mapping, reconnect/gap
  recovery, slow-subscriber policy, and the browser's critical start-live-stop-
  inspect flow with offline automated tests. Real Ollama and interactive browser
  acceptance remain user-run unless explicitly requested.

**M5 non-goals:** generic custom simulation authoring, arbitrary YAML editing in
the browser, dynamic mode/plugin discovery, a general visualization engine,
replay, run comparison, production multi-tenant hosting, or moving simulation
logic into TypeScript.

## M6: Game Mode Architecture

**Status: Complete.** Implemented as a closed application-owned registry with
immutable mode and scenario-template views. Society supplies its presentation,
capability, configuration, and visualization hints through that registry; the
FastAPI catalog and Next.js selector now consume the shared mode query. Existing
schema-version-1 resolution and execution remain unchanged.

**Outcome:** AntFarm has an explicit, transport-neutral representation for curated
simulation/game modes, and the M5 Society experience is served through it without
changing simulation results or making Society fields universal.

### M6 acceptance criteria

- Define the smallest immutable mode descriptor and application query needed to
  identify a mode, expose presentation metadata, enumerate its scenario templates,
  and describe supported configuration/capability hints to clients.
- Make Society the first built-in mode and route the existing catalog and web
  selection experience through the shared mode query rather than hard-coded web or
  HTTP-only metadata.
- Keep the mode boundary transport-neutral. FastAPI serializes application views;
  Next.js consumes them; neither owns the authoritative registry or validation.
- Keep engine ordering, action validation, transitions, persistence, and event
  publication unchanged. A mode selects and constrains composition; it is not an
  alternate engine or a place for mutable run state.
- Preserve schema-version-1 scenarios, CLI/library behavior, deterministic
  resolution, stored-run compatibility, and the Society UI delivered in M5.
- Distinguish mode metadata and applicable fields from universal core state.
  Wealth, personality, relationships, reputation, occupation, speech, and a
  commons environment remain Society capabilities rather than required mode
  fields.
- Keep registration closed and explicit. Do not add entry-point discovery,
  arbitrary Python imports, third-party mode loading, or a broad hook interface.
- Add focused offline tests proving Society discovery, template enumeration,
  transport projection, unknown-mode errors, and unchanged resolution/run
  behavior.

**M6 non-goals:** implementing several speculative modes, generic custom
definitions, dynamic plugins, rewriting M3/M4 values, or moving validation and
mutation into the frontend.

## M7: Generic Custom Simulation Definition

**Status: Complete.** Implemented as a separate strict data schema and a
declarative environment composed into the existing engine. Custom definitions
support typed scalar/collection state, public/owner/internal visibility,
deterministic or injected-model entity behavior, typed actions, constraints,
set/add transitions, interval activation, tick termination, in-memory or SQLite
storage, resolution overrides, and application inspection. The offline warehouse
example proves a non-Society workflow without an LLM.

**Outcome:** users and adapters can construct, validate, resolve, and execute a
versioned custom simulation definition made only from data, without inheriting
Society-specific fields or importing executable server code.

Define a versioned, transport-independent representation for simulations that do
not fit a built-in mode. Generalize only the domain/application seams required to
represent typed state values, scope and ownership, visibility, actions,
observations, validation constraints, scheduling/activation, termination, and
environment-owned transitions. A valid custom simulation need not contain money,
relationships, society, a physical environment, or an LLM-backed entity.

Retain the M3 rich profile, population, economic, visibility, and social behavior
as working capability. Move or adapt those concepts toward reusable schemas,
capabilities, or the Society mode where evidence supports it; do not replace the
engine, persistence lifecycle, application facade, or resolved-configuration
model wholesale. Custom definitions remain data, not arbitrary imported or
generated server code, and loading/resolution must not require an LLM.

### M7 acceptance criteria

- Define a strict versioned custom-definition schema with named entity types,
  entities, typed initial state fields, action definitions, observation rules,
  transition rules, activation/scheduling, termination, and storage/runtime
  settings. Unknown fields, duplicate identifiers, invalid references, invalid
  types, and contradictory rules fail before composition.
- Support JSON-compatible scalar and collection state with explicit scope and
  ownership. Visibility distinguishes public, owner-only, and internal values;
  observations expose only permitted projections.
- Provide a small declarative transition vocabulary sufficient to prove a useful
  non-Society simulation. Transitions remain environment-owned and validated;
  definitions cannot name Python imports, expressions, templates, shell commands,
  or arbitrary executable code.
- Permit deterministic entities that do not call an LLM as well as optional
  model-backed entities through existing provider ports. A valid definition need
  not contain agents, profiles, money, relationships, speech, or a physical map.
- Resolve a custom definition into immutable application inputs and execute it
  through the existing engine lifecycle, ordered events, atomic persistence,
  cancellation, and query contracts. Preserve schema-version-1 Society scenarios
  and stored-run compatibility.
- Add one documented offline custom example outside the Society domain and cover
  validation, deterministic replay of the same seed/input, visibility isolation,
  rejected actions, persistence, and application-level inspection with focused
  tests.

**M7 non-goals:** the web builder, natural-language generation, arbitrary code,
dynamic plugins, a universal visual editor, or rewriting working Society schema
and execution paths.

## M8: Web Custom Simulation Builder

**Status: Complete.** Implemented with versioned custom validate/resolve/entity
API operations and a separate browser workspace. The builder renders structured
controls across every M7 definition section, saves a versioned local draft,
imports/exports the shared JSON format, requires server validation and preview
before launch, streams committed events, and inspects final custom state. Web
authoring is restricted to deterministic, in-memory definitions so model-provider
credentials and arbitrary server paths cannot enter through the browser.

**Outcome:** a user can author, validate, preview, save locally in the browser,
and run an M7 custom definition through structured web controls without editing
YAML or bypassing server validation.

Expose the M7 definition through structured browser forms/editors. Users can
define and edit entities and types, state, actions, observations, visibility,
rules/constraints, model assignments, activation, and termination without writing
YAML. Provide server-backed validation, clear errors, and resolved previews before
execution. The same definition remains usable through non-web application/library
entry points. A visual node editor is not required for the first builder.

### M8 acceptance criteria

- Add versioned API operations to validate a complete custom definition, resolve
  ephemeral run choices, preview entities and visibility projections, and start
  it through the M7 application path. Return stable M4-style errors and never
  persist a run for invalid input.
- Add a Custom mode entry alongside built-in modes without pretending it is a
  built-in scenario template. Preserve the M6 Society selection and all M5 run,
  stream, stop, and inspection behavior.
- Provide structured editors for run settings, entity types and fields, entities
  and initial state, actions/parameters, constraints/effects, activation,
  termination, and storage. JSON editing may supplement complex subsections but
  cannot be the only authoring experience.
- Show server validation errors at the relevant section and provide a resolved
  preview before launch. Public projections must not expose owner-only or internal
  values, while the configuring user can review the complete authored definition.
- Keep browser drafts locally and support import/export of the same versioned data
  format used by Python callers. Do not introduce server-side arbitrary file paths
  or executable extensions.
- Cover a complete non-Society builder journey with Playwright: edit the provided
  starter, validate, preview, run, observe committed events/state, and inspect the
  completed result. Keep all automated acceptance offline and deterministic.

**M8 non-goals:** a node editor, AI generation, accounts/cloud persistence,
collaborative editing, dynamic plugins, or a generic visualization engine.

## M9: AI-Assisted Simulation Generation

**Outcome:** a user can describe a simulation in natural language and receive a
validated, editable M7 proposal in the M8 builder without granting the model an
execution or mutation path.

Translate a natural-language simulation description into a proposed structured
M7 definition. Always show the validated proposal in the M8 builder and keep it
editable before execution. Treat generation as configuration/schema generation:
the model may not create, import, or execute arbitrary server code, bypass
visibility, or bypass environment/domain-owned transition validation.

### M9 acceptance criteria

- Define a provider-neutral application command that accepts a bounded natural-
  language description and requests one complete M7 definition through the
  existing model-provider boundary. Keep prompt construction and malformed-output
  handling outside the domain.
- Validate generated output with `CustomSimulationDefinition` before returning it.
  Reject prose, partial data, unknown fields, executable-looking extensions, and
  invalid references with stable bounded errors; never start or persist a run as
  part of generation.
- Add an API operation and builder prompt panel that inserts a successful proposal
  into the existing structured editor. The user must explicitly validate/preview
  and start it through the normal M8 workflow.
- Provide a deterministic offline generation adapter/fixture for automated tests
  and an optional documented local-model path. No network, credentials, or model
  runtime is required by the core test suite.
- Preserve the submitted description and generation provenance only in client or
  explicit application result data; do not log raw prompts/model output or expose
  secrets in errors.
- Cover successful generation-to-edit-to-run, malformed output, schema-invalid
  output, provider failure, size limits, and confirmation boundaries with unit,
  API, and Playwright tests.

**M9 non-goals:** autonomous execution, arbitrary code generation, agent-written
plugins, prompt-history accounts, model training, or replacing structured editing.

## M10: Visualization, Replay, and Experiment Analysis

Implement recorded-action replay without model calls and stable comparison of
completed runs, restoring the deferred M1-03/M1-04 outcomes on top of mature run
queries. Evolve the web experience with timelines, state changes, conversations,
agent inspectors, current world state, replay, and run comparison. Allow modes to
provide relevant views such as relationship networks or economic charts without
making a universal visualization system a prerequisite. Add time-series metrics,
statistical analysis, and large-scale experiment scheduling incrementally when
their requirements are demonstrated.

## M11: Optional Advanced Simulation Systems

Advance relationships, reputation, groups, institutions, occupations, markets,
governance, survival systems, and richer environments as optional reusable
capabilities and/or mode-owned functionality. Add one validated need at a time;
none of these concepts becomes mandatory in the AntFarm object model, and no
system may bypass environment/domain-owned validation and mutation.

## Transition Constraints and Risks

- `ScenarioConfig` currently requires agents, providers/models, one environment,
  memory, scheduling, storage, and a closed union of built-in actions. That is an
  accurate version-1 contract, but not yet the generic custom definition promised
  by M7.
- Schema validation, the composition root, resolved-agent inspection, and some
  observation/profile projection contain explicit counter/commons and
  social/economic branches. M6/M7 isolated new mode/custom contracts without
  rewriting them; future capability work should migrate these seams incrementally
  rather than growing cross-engine conditionals.
- M4 live subscriptions are process-local and expose committed events only;
  M5 added bounded WebSocket buffering and durable cursor recovery, but restart
  ownership and multi-process coordination remain deferred.
- `AntFarmApplication` owns running tasks in memory while SQLite owns durable run
  data. Restart/resume and multi-process ownership are not implied by the current
  service contract and should not be accidentally promised by the first web UI.
- Version-1 resolved-agent inspection intentionally includes complete
  configuration for the configuring caller and a separate public projection.
  Future API authorization must preserve that distinction rather than assuming
  every inspection field is safe for every viewer.

## Delivery Workflow

For each milestone, understand its scope and relevant architecture, inspect the
affected code and documentation, implement focused changes, and run proportionate
automated checks. A repository-wide reread or manual revalidation of unrelated
completed milestones is not a prerequisite. The full automated suite and static
checks protect existing behavior before changes are committed and pushed. Manual
Ollama, GPU, latency, and interactive checks remain user-run unless explicitly
requested.
