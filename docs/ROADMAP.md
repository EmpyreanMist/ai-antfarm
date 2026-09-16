# AntFarm AI Roadmap

## Purpose

This is the active plan from the completed M0-M12 baseline onward. The detailed
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

**Status: Complete.** Implemented as a bounded provider-neutral generation
service, deterministic offline adapter, optional OpenAI-compatible adapter, and
builder prompt panel. Generated text must be one complete M7 JSON object and pass
strict schema validation; errors expose no raw output. Generation returns only an
editable proposal and provenance, never a resolution or run. The user must still
edit, validate/preview, and explicitly start through M8.

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

**Status: Complete.** Recorded committed actions are reconstructed through the
original environment validation/mutation rules with a seeded random source and
no cognition/provider dependency. Ordered histories and final checkpoints are
verified before bounded replay frames are returned. The application/API expose
run history, replay, generic metrics, state/metric deltas, and explicit
compatibility results; the web control plane provides timeline and comparison
views for Society and custom runs. Configured SQLite history supports discovery
after restart.

**Outcome:** completed runs can be replayed without model calls, compared through
stable application contracts, and explored through useful web timelines and
state/metric views.

Implement recorded-action replay without model calls and stable comparison of
completed runs, restoring the deferred M1-03/M1-04 outcomes on top of mature run
queries. Evolve the web experience with timelines, state changes, conversations,
agent inspectors, current world state, replay, and run comparison. Allow modes to
provide relevant views such as relationship networks or economic charts without
making a universal visualization system a prerequisite. Add time-series metrics,
statistical analysis, and large-scale experiment scheduling incrementally when
their requirements are demonstrated.

### M10 acceptance criteria

- Reconstruct a replay from persisted committed action outcomes and checkpoints
  without invoking cognition or a model provider. Verify event ordering, run and
  schema compatibility, and deterministic final state; fail safely on incomplete
  or incompatible histories.
- Add immutable application replay/timeline and comparison DTOs with bounded
  pagination. Transport and UI consume projections rather than storage records or
  event-domain objects.
- Compare at least two completed compatible runs across final world state,
  built-in metrics, tick counts, action/rejection/failure totals, and per-agent or
  per-entity outcomes. Explicitly report incompatible fields instead of silently
  coercing them.
- Add web run-history selection for process-known and configured SQLite runs,
  timeline inspection, replay controls, state/metric deltas, and side-by-side run
  comparison. Mode-specific views may augment the generic baseline.
- Keep all result sets and rendered series bounded. Large experiment scheduling,
  advanced statistics, relationship graphs, and domain-specific charts remain
  incremental follow-up unless needed for the acceptance example.
- Cover Society and custom replay, no-model guarantees, corruption/incompatibility
  errors, pagination, comparison, API projection, and an offline Playwright
  history/replay/comparison journey.

**M10 non-goals:** branching timelines, distributed experiment workers, a generic
chart-plugin system, full event sourcing, or replay that calls an LLM.

## Product Direction After M10

The browser is the primary interactive AntFarm product. Normal local use should
not require editing YAML or invoking the CLI: users discover installed models,
author populations, configure a mode, preview the exact resolved inputs, run,
observe, stop, replay, and compare from the web UI. YAML, CLI, and Python remain
supported power-user and developer surfaces over the same application contracts.

Future work preserves server-authoritative mutation, committed-event semantics,
explicit seeds and provenance, private/public boundaries, and provider-neutral
ports. Curated presets make experiments quick and entertaining without creating
special-case engines. Each milestone below must leave an independently useful,
manually testable browser experience.

## M11: Web-First Models and Agent Builder

**Status: Complete.** The backend exposes bounded Ollama connectivity and
installed-model inventory through a provider-neutral port. The Society web flow
uses a shared Agent Builder for manual, seeded-random, and mixed populations;
generated profiles use the normal validated profile schema and remain editable.
Users can resize, randomize, clone, reset, add/remove, assign shared or per-agent
installed models, edit supported profile/economic/relationship/visibility fields,
and inspect exact public plus complete resolved configuration before starting.
Resolved web drafts normalize into ordinary `ScenarioConfig` and persist with
runtime provenance rather than introducing a second agent type.

**User-visible outcome:** a user can discover local Ollama models and construct,
randomize, edit, and preview a complete Society-compatible population in the
browser without typing a model tag or editing YAML.

**Architecture boundary:** Ollama discovery remains behind a provider-neutral
application port and backend API. One shared population/profile contract serves
manual, seeded-random, and mixed authoring; generated agents are ordinary editable
agents. Model assignment remains separate from identity.

**Core capabilities:** Ollama availability and installed-model discovery; shared
or per-agent model assignment; manual/random/mixed population authoring; seeded
whole-population and single-agent regeneration; add, remove, clone, and reset;
identity, personality, goals, beliefs, values, communication, behavioral traits,
Society profile fields, visibility, and an exact public/private resolved preview.

**Acceptance criteria:**

- Show connected/unavailable and installed/missing model states from backend data.
- Select one installed model for all agents and override selected agents without
  creating one model process per agent.
- Produce identical random populations for identical inputs and seed, using the
  same validated profile schema as manual agents.
- Support manual, random, and mixed populations up to the current safe limit while
  keeping limits contractual rather than making ten an architectural maximum.
- Persist the exact resolved population and model/runtime provenance with the run.
- Cover discovery failures, generation/editing, visibility preview, validation,
  and a browser create-preview-run journey offline where possible.

**Non-goals:** downloading arbitrary models, model lifecycle management, remote
provider marketplaces, unlimited populations, or model-generated private
reasoning. Manual acceptance: select an installed Ollama model, randomize several
agents, edit and clone one, inspect visibility, then run them from the browser.

## M12: Conversation / Social Sandbox Mode

**Status: Complete.** Conversation is a registered Ollama-first Game Mode over
the existing deterministic engine, Agent Builder, public speech, memory, event,
replay, and visibility contracts. The web app opens on a one-click social
sandbox with editable topic, situation, turn count, memory, nine curated presets,
per-agent models and profiles, secret motives, and a seeded **Random all** flow.
Conversation resolution restricts the shared scenario to speech, gives one agent
the floor per tick, and places the current topic and situation in every bounded
observation. The live feed renders profile display names while committed events
remain authoritative.

**User-visible outcome:** users can start an autonomous multi-agent conversation
in minutes by choosing models, agents, and a situation or curated preset.

**Architecture boundary:** Conversation is a registered Game Mode over the shared
engine, Agent Builder, memory, speech action, and event contracts—not a special
chat loop. Public conversation becomes later bounded observation; secrets remain
subject to configured visibility.

**Core capabilities:** initial topic/situation, optional relationships and secret
motives, memory/context limits, pacing, bounded/continuous execution, and presets
such as open conversation, dinner party, heated debate, hostile negotiation,
philosophical discussion, jury deliberation, stranded group, rival factions, and
team planning.

**Acceptance criteria:** presets resolve to editable configuration; agents react
to prior committed public speech; the live view uses actor names and supports safe
stop, history, replay, and comparison; distinct agents may share or override a
model; offline deterministic tests cover ordering and visibility.

**Non-goals:** private chain-of-thought, voice/video, unrestricted direct messages,
or economy/governance systems. Manual acceptance: choose a preset, randomize the
cast, run a bounded conversation, then replay and compare it with another seed.

## M13: Society Economy, Ownership, and Trade

**User-visible outcome:** Society experiments can model unequal wealth, scarcity,
ownership, giving, exchange, buying, selling, prices, work, wages, income, and
simple debt through inspectable authoritative state.

**Architecture boundary:** reusable economic values and transitions are optional
capabilities selected by Society scenarios. Models propose typed actions; the
environment validates ownership, balances, inventory, prices, and context before
committing effects.

**Core capabilities:** money, inventories/resources, ownership, give, trade,
buy/sell, prices, work/wages, optional recurring income, and bounded debts/loans;
templates for unequal wealth, scarce resources, free market, and employer/worker
negotiation.

**Acceptance criteria:** value is conserved where rules require it; invalid or
impossible transfers are rejected; public/private economic visibility is honored;
state, events, metrics, replay, and comparison explain every accepted transition;
at least two curated browser experiments require no YAML.

**Non-goals:** companies, securities, macroeconomic realism, tax/government, or
unvalidated natural-language balance changes.

## M14: Jobs, Production, and Companies

**User-visible outcome:** agents can found and operate simple companies, employ
others, produce goods/services, set prices, and compete in browser-run experiments.

**Architecture boundary:** companies are optional entities with authoritative
cash, inventory, ownership, products, employees, and policies. Company actions
reuse economic ownership/transfer contracts and never become LLM-owned state.

**Core capabilities:** company creation, cash and inventory, ownership shares,
products/services, hiring/firing, wages, work/production, and agent-company or
company-company buying/selling.

**Acceptance criteria:** employment and production obey configured constraints;
company and worker outcomes are inspectable and replayable; a company-competition
and an employer/worker template are independently playable in the browser.

**Non-goals:** corporate law, accounting standards, stock markets, complex supply
chains, or autonomous plugin code.

## M15: Dynamic Relationships, Reputation, and Groups

**User-visible outcome:** social behavior can build or damage trust, reputation,
relationships, alliances, and group membership over time.

**Architecture boundary:** relationship/reputation/group state is mode-selected,
typed, visibility-aware, and environment-owned. Conversation and economic events
may feed explicit configured update rules; models cannot assign scores directly.

**Core capabilities:** helping, accusations, deception/fraud attempts where a
scenario enables them, relationship changes, reputation evidence, alliances,
groups/factions, and public/private membership.

**Acceptance criteria:** updates cite committed causes, visibility is enforced,
replay reproduces the social graph, and rival-factions plus betrayal/trust presets
are usable from setup through comparison in the browser.

**Non-goals:** universal morality scores, inferred protected attributes, opaque
LLM-authored reputation changes, or requiring relationships in every mode.

## M16: Governance, Laws, and Voting

**User-visible outcome:** Society scenarios can stage councils, elections,
proposals, voting, offices, configurable laws, and simple taxation.

**Architecture boundary:** governance is an optional capability that produces
versioned authoritative rules consumed by validation. Office holders and models
may propose or vote, but cannot bypass enactment procedures or mutate law.

**Core capabilities:** proposals, ballots, voting rules, elections, offices/roles,
law lifecycle, rule-aware action validation, and optional taxes; templates for a
small democracy, council vote, authoritarian leader, and constitutional rules.

**Acceptance criteria:** every law and office transition is attributable and
replayable; rejected actions explain applicable rules; results and current laws
are visible in the live UI; at least two governance presets are browser-playable.

**Non-goals:** a universal legal language, real-world jurisdiction simulation,
campaign platforms, or mandatory governance for Society.

## M17: Crime, Detection, and Justice

**User-visible outcome:** configured scenarios can model stealing, detection,
accusation, arrest, judgment, imprisonment, and release as constrained actions and
state rather than narrative side effects.

**Architecture boundary:** crime and justice compose economy, context, governance,
and visibility capabilities. The environment decides feasibility, probabilistic
outcome from the run seed, detection, evidence, and authoritative consequences.

**Core capabilities:** theft and fraud attempts, detection/evidence, accusation,
arrest, trial/vote/rule-based judgment, sentence duration, state restrictions,
imprisonment, and release; presets for prison society and corruption experiments.

**Acceptance criteria:** impossible actions cannot mutate state; detected and
hidden outcomes expose only permitted events; restrictions are enforced by
validation; seeded non-model outcomes replay exactly; a complete justice flow is
observable in the browser.

**Non-goals:** realistic legal advice, unrestricted violence, model-selected
punishment outside scenario rules, or a mandatory justice system.

## M18: Rich Live Simulation Views

**User-visible outcome:** runs feel like living experiments rather than forms plus
raw JSON, with mode-aware conversation, action, entity, economy, relationship,
company, group, law, metric, timeline, replay, and comparison views.

**Architecture boundary:** views consume bounded application projections and
public committed state. Modes may declare relevant presentation hints; frontend
components do not interpret persistence records or own simulation rules.

**Core capabilities:** filterable live feeds with actor names, agent/entity cards,
current public resources and status, mode-specific panels, metric series, clearer
replay controls, comparison summaries, and responsive large-population handling.

**Acceptance criteria:** each implemented mode has a useful default dashboard;
private data and chain-of-thought never leak; large lists/series remain paginated
or bounded; reconnect and terminal states remain correct; offline Playwright tests
cover the primary live and analysis journeys.

**Non-goals:** a game engine, universal chart-plugin framework, 3D world, hidden
reasoning display, or frontend-owned derived truth.

## M19: Advanced Custom Simulation Builder

**User-visible outcome:** users can create and run model-backed custom simulations
entirely through structured controls, including the full strict M7 definition,
without YAML.

**Architecture boundary:** the builder remains an editor for versioned data-only
definitions. Server validation and environment-owned transitions stay canonical;
AI generation only proposes editable data and never starts a run.

**Core capabilities:** complete editors for entity types/entities, typed fields,
ownership/visibility, actions/parameters/constraints/effects, activation,
termination, deterministic and model-backed entities, installed-model assignment,
storage/run settings, reusable templates, import/export, and migration feedback.

**Acceptance criteria:** every supported M7 field is editable without raw JSON;
model assignments use backend discovery; invalid references/transitions receive
field-level feedback; generated proposals remain editable and require validation
plus explicit start; round-trip import/export preserves normalized definitions;
an offline browser journey builds a non-Society simulation from scratch.

**Non-goals:** arbitrary Python, shell or browser code; agent-written plugins;
automatic execution; collaborative editing; or bypassing schema/environment
validation.

## M20: Survival and Resource Experiments

**User-visible outcome:** users can run tense, reproducible survival experiments
about scarcity, disaster, depletion, cooperation, and selfishness from curated
browser templates.

**Architecture boundary:** survival is a mode or Society capability composition
over typed resources, needs, locations/context where required, seeded environment
processes, and validated actions. It does not make health or physical geography a
universal agent requirement.

**Core capabilities:** limited consumables, configurable needs and consequences,
resource regeneration/depletion, seeded shocks or disasters, cooperation and
allocation actions, termination conditions, and presets such as stranded group,
limited food, disaster response, and commons collapse.

**Acceptance criteria:** resource and need transitions are authoritative and
replayable; identical non-model seeds reproduce environmental outcomes; public
and private state remain distinct; at least two templates are configurable,
observable, replayable, and comparable entirely in the browser.

**Non-goals:** a physics engine, medical realism, unrestricted model-authored
hazards, mandatory health state, or a universal spatial simulation.

## Transition Constraints and Risks

- `ScenarioConfig` remains the closed Society-oriented version-1 contract while
  the separate M7 custom definition is the generic data-only path. Future shared
  builders must preserve this distinction rather than forcing Society concepts
  into every simulation.
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
