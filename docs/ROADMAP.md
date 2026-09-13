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

- **M1-02 — Complete:** deterministic built-in action, rejection, failure, and

  per-agent outcome metrics consume committed events and persist in checkpoints.

- **M1-03 — Deferred until after the interactive target:** compare completed runs using normalized scenario metadata,

  final state, event outcomes, and metric summaries.

- **M1-04 — Deferred until after the interactive target:** replay recorded accepted actions and outcomes without

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

## Current-State Review and Planning Boundary

This plan reflects the repository through M2-03, including accepted ADRs 0010 and

11. Completed milestone text above is retained. AGENTS.md's introductory

reference to implementing M0 is historical; the implementation and progress

entries establish the current baseline.

The provider adapter already supports configurable OpenAI-compatible endpoints,

structured decisions, and timeouts. `scenarios/examples/ollama.yaml` and README.md

already describe a single-agent local-model smoke test. M2-01 now resolves public

identity and private personality into provider-neutral requests. Composition

creates one provider instance per used model reference and shares it among assigned

agents; tests verify that private recall remains isolated.

M2-02 adds opt-in public speech to the commons environment. Accepted messages are

authenticated, identified, checkpointed, delivered to bounded per-agent memory

after the originating tick's cognition, and exposed through bounded public

history starting on the next tick. SQLite tests prove that older messages remain

in the durable event log after falling out of live context.

M2-03 adds explicit paced continuous execution, deterministic staggered cadence,

a fair cognition budget, recipient wakeups, capped provider-failure retries, and

checkpointed scheduler state. Failed or cancelled commits restore the preceding

complete state, observer failures are isolated after commit, the live event window

is bounded, and cancellable asyncio HTTP transport closes in-flight connections.

The remaining interactive gap is M2-04's terminal rendering of committed actions

and speech. Continuous M2-03 runs intentionally report lifecycle and final

checkpoint status without presenting dialogue as it occurs.

M1-03 comparison and M1-04 replay move later, retaining their identifiers and scope

above. Neither is needed to generate, validate, deliver, or display speech.

Checkpoint recovery is required; rebuilding a run from recorded actions is not.

Their implementation is outside this plan's endpoint.

## Milestone M2: Interactive Local-AI Simulation in the Terminal

This replaces the former unimplemented M2 observation/API theme. No accepted ADR

requires a network API for terminal observation. ADRs 0001–0011 remain in force;

new contracts should be documented when implemented, without reopening completed

milestones. Complete each sub-milestone before starting its successor.

The implementing session performs relevant automated verification only. Manual,

local-runtime, Ollama, GPU, and interactive verification is performed by the user

unless explicitly requested otherwise.

## M2 Progress

- **M2-01 — Complete:** immutable public identity and private personality values

  reach provider-neutral requests; bounded recall stays agent-scoped; three-agent

  mock and Ollama examples share one configured model; offline tests cover shared

  provider composition and safe backend failure.

- **M2-02 — Complete:** validated public speech, shared bounded social observations,

  next-tick recipient delivery, retention limits, and durable audit coverage are

  implemented without exposing private context.

- **M2-03 — Complete:** paced continuous execution, fair bounded cognition,

  recipient wakeups, failed-commit recovery, bounded event retention, and safe

  cancellable stopping are implemented.

- **M2-04 — Next:** stream committed society events in the terminal and verify

  the complete local-AI experience.

### M2-01: Distinct Agents Using Shared Local Model Backends — Complete

**Purpose:** make the existing local-provider path represent distinct agents with

their own context, and establish a reliable finite local-model experiment.

**Dependencies:** the current M0/M1-01 baseline and verification of the existing

M1-02 working-tree changes before proceeding.

**Acceptance criteria**

- Resolve identity, personality description, and traits into immutable,

  provider-neutral request context. Distinguish public identity from private

  personality/memory. Mutable holdings remain environment-owned state.

- Preserve agent-scoped recall and supply it with the agent's identity and current

  observation on each request. Sharing a backend must not share private histories.

- Provide finite mock and Ollama examples with at least three distinct agents

  sharing one model reference; document assigning a second named model to a subset.

  No runtime or loaded model per agent is created. Ollama owns loading and memory

  residency; multiple configured models need not remain resident simultaneously.

- Use the existing generic provider boundary and OpenAI-compatible endpoint.

  Document starting Ollama, pulling the configured model, matching YAML model names,

  and adjusting timeouts for cold starts. Do not add a native Ollama SDK unless a

  demonstrated endpoint incompatibility requires a thin adapter change.

- Missing models, connection failures, malformed responses, and timeouts produce

  bounded, useful errors without exposing credentials, raw responses, or changing

  world state for the failed decision. Validation/inspection remain offline.

- Mock/captured-request tests prove identity and memory isolation, shared provider

  composition, configuration rejection, and safe unavailable-model behavior.

  Real speech style or exact model wording is not an automated assertion.

**Non-goals:** model installation by AntFarm, runtime management, conversational

speech, new environments, continuous execution, automatic backend discovery.

**Manual test after this step:** run the existing single-agent Ollama example,

then the new finite three-agent example. Inspect resolved identities/model

references, observe validated world changes, and try a nonexistent model name or

stopped backend. Reassign one agent to a second locally available model. Automated

tests must still pass with Ollama stopped.

### M2-02: Validated Speech and Shared Social Observations — Complete

**Purpose:** let agents freely choose what to say and respond to one another

through the same controlled lifecycle as physical world actions.

**Dependencies:** M2-01.

**Acceptance criteria**

- Extend the built-in commons environment with an explicit opt-in social mode and

  a `say` action alongside harvest/contribute. Keep existing counter and commons

  defaults compatible. The closed schema rejects incompatible action selections.

- Speech is an ActionProposal with bounded non-empty text. The authenticated actor

  comes from the engine, not model-supplied sender metadata. Environment validation

  precedes application; accepted messages receive stable IDs, sender IDs, and ticks

  and appear in ordered committed action outcomes. Rejections create no message.

- Use one public room: every agent can hear every accepted message, including its

  own. Free communication means model-generated text, not a fixed script, with

  configurable length/history limits. Each cognition chooses one world action,

  speech action, or no-op; simultaneous action bundles are unnecessary.

- Other agents see a bounded public roster, shared resources, their own holdings,

  and recent public messages. Public identity is visible; private personality and

  private recall are not copied into other agents' observations.

- Define delivery at tick boundaries: speech accepted in tick T becomes observable

  in T+1, after T commits, for all agents regardless of their position in action

  order. Existing sequential physical-action visibility remains unchanged. A

  staged message must not reach another model before its step commits.

- The engine prepares bounded recipient memory entries and delivery cursors as

  part of the next checkpoint transaction, using environment-defined recipients.

  Observation/history and recent recall can overlap, but stable message IDs prevent

  duplicate memory insertion. Restore does not redeliver already recorded messages.

- Retain only configurable recent message and per-agent memory windows in live

  state; disclose that older conversation falls out of context. The durable event

  log retains accepted speech. Agents that have not thought recently receive a

  bounded recent window, not an unlimited inbox.

- Message text remains simulation data in prompts. It cannot invoke tools or

  bypass action validation. Validated speech is intentionally persisted as world

  content; this does not enable raw model prompt/response logging.

- Offline tests prove next-tick delivery, sender authenticity, rejection, bounded

  retention, no private-memory leakage, and deterministic snapshot continuation.

**Non-goals:** private messages, multiple channels, human chat input, voice/audio,

  semantic memory, OASIS/CAMEL, a general messaging service.

**Manual test after this step:** run finite mock and local-model social scenarios;

inspect their persisted speech/action events using a documented library snippet.

Verify that later decisions receive earlier messages, and that harvest/contribute

still work. Live terminal rendering arrives in M2-04.

**Manual acceptance (2026-09-13):** the first real
`social-ollama.yaml` run with `qwen3.5:0.8b` produced nine malformed
cognitions. Investigation exposed two OpenAI-compatibility gaps rather than a
social engine defect: the scenario used Ollama's native `think` field on the
`/v1/chat/completions` endpoint, while the adapter assumed the endpoint would
always return bare schema-conforming JSON. Fix `24f1c1e` changed the scenario to
use OpenAI-compatible `reasoning_effort: none` with deterministic, bounded generation;
the generic adapter now repeats the exact schema in the system instruction and
accepts one complete Markdown JSON fence while preserving strict validation and
redacted normal errors.

The post-fix manual run passed three ticks with 41 events, eight applied `say`
actions, eight persisted messages, zero malformed, failed, or timed-out
cognitions, one rejected action, and no unintended world-state mutation. The
small model produced simplistic and self-referential dialogue; this is accepted
as model quality variation because the structured-output and validated social
action pipeline behaved correctly. M2-02 is therefore manually verified; no
M2-03 work was included in the compatibility fix.

### M2-03: Paced Autonomous Execution and Safe Stop — Complete

**Purpose:** run a shared backend indefinitely at a sensible cadence while

preserving deterministic tick ordering and consistent committed state.

**Dependencies:** M2-02.

**Acceptance criteria**

- Add an application-level continuous runner around `engine.step()`. Keep the

  finite, unpaced runner for tests and existing examples. An explicit continuous

  option runs until Ctrl+C; merely loading an old scenario stays finite.

- Use a monotonic clock for a configurable minimum interval between tick starts.

  If a step exceeds that interval, advance once when ready; never overlap steps,

  skip logical ticks, or launch catch-up bursts. Wall time changes pacing only,

  not action order or RNG state. Real model generation remains nondeterministic.

- Extend the existing scheduler with per-agent/per-pool cadence overrides,

  deterministic staggered starting offsets, cooldowns, and a maximum number of

  cognitions per tick. Default the interactive example to one invocation per tick.

  Keep sequential cognition and application, limiting backend load without workers.

- Retain due agents in a bounded set and rotate fairly through stable agent IDs;

  no starvation under sustained load. Checkpoint the fairness cursor, due state,

  offsets, and cooldowns. Idle ticks do not call providers.

- Accepted public speech wakes its recipients, excluding the speaker, for a future

  tick. Preserve existing actor-trigger semantics for other events. Recipient

  wakeups coalesce and obey cadence cooldowns and the invocation budget; they never

  force every listener to invoke a model immediately. Periodic cognition provides

  an autonomous starting point when no messages exist.

- Apply capped deterministic retry cooldowns after provider failures. Avoid tight

  retry loops when Ollama is down; healthy agents can continue. A failed decision

  has no action effect, though its failure event and scheduling outcome commit.

- On failure before commit, restore world, memory, scheduler, metrics, tick, and

  RNG/sequence to the preceding complete checkpoint. A storage failure stops the

  runner clearly rather than continuing with divergent state. Post-commit observer

  failure must never retry an already committed action or roll it back.

- Ctrl+C stops scheduling new cognition, cancels or bounds the outstanding request,

  and either completes an atomic step or discards its uncommitted changes. Close

  storage and provider resources and report the last committed tick. Late worker

  responses cannot apply actions. Test the actual transport shutdown behavior;

  replace the thread-based transport only if needed to meet a documented bounded

  stop time. Do not accumulate orphan requests across timeouts.

- Continuous execution streams batches without retaining all events in RunResult

  or the event bus. Bound live buffers; keep SQLite's append-only audit on disk.

  No disk retention service is required; full-disk errors stop safely.

- Tests use fake clocks, deterministic providers, failure injection, and temporary

  SQLite databases to prove fairness, cadence, cancellation, commit recovery, and

  bounded in-memory retention. No real sleeps or Ollama dependency are required.

**Non-goals:** hard real-time guarantees, parallel cognition, performance targets

  for large populations, hot configuration reload, replay or comparison tooling.

**Manual test after this step:** start continuous mock and Ollama scenarios from

the terminal, let several agents share a backend, stop during a slow request with

Ctrl+C, and inspect the final checkpoint via a documented library snippet. Stop

Ollama during a run and confirm bounded retries and safe termination. This step

provides lifecycle/status output; full dialogue display follows in M2-04.

### M2-04: Live Terminal Society and Local-AI Acceptance — Planned

**Purpose:** complete the first interactive experience: watch several local agents

autonomously act and converse in a shared world until stopped.

**Dependencies:** M2-03.

**Acceptance criteria**

- Add a thin terminal observer subscribed to committed events. Flush readable

  speech, world-action results, rejection/failure notices, tick and actor identity

  while running. Do not wait for the final summary or display an unvalidated

  proposal as accepted speech. Live means after each completed atomic tick; the

  one-cognition-per-tick default prevents long multi-agent display batches.

- Distinguish waiting/model-busy lifecycle status from committed simulation events.

  No token streaming is needed. Escape terminal control sequences in model text

  and support plain redirected output. A broken output stream stops cleanly without

  duplicating committed actions.

- Expose documented live and continuous CLI options with pacing configuration;

  preserve existing finite CLI behavior. At startup print run identity, backend

  assignments, cadence, and stop instructions. At stop print last committed tick,

  final world/metric summary, and checkpoint location. Avoid overwriting existing

  durable runs: assign a fresh run ID or reject an explicit duplicate clearly.

- Supply matching offline mock and Ollama social examples with at least three

  identities, contrasting personalities, initial holdings, recent memory, speech,

  and physical actions. One named local model is the default for all three; a

  documented edit routes selected agents to an optional second model/backend.

- Provide exact Windows/VS Code terminal instructions and manual smoke checks for

  backend startup, model download, scenario validation, live execution, Ctrl+C,

  and unavailable model/runtime handling. The user records tested model/runtime

  versions after manual verification rather than assuming a model tag guarantees

  compatibility.

- An offline end-to-end test proves dialogue is emitted before run completion,

  messages influence later observations, actions remain validated, and stopping

  leaves a consistent SQLite checkpoint.

- Provide a manual Ollama smoke-test procedure for the user to verify coherent

  responses to prior speech, distinct agent context, and model compatibility

  without expecting exact wording. Real Ollama execution is not required as part

  of automated milestone verification.

- At milestone completion, run the relevant automated tests once, plus Ruff and

  strict mypy for changed Python code. Avoid redundant re-verification of completed

  milestones unless there is concrete evidence of a regression. The user measures

  real Ollama latency and manual stop behavior; do not claim hard real-time timing.

**Non-goals:** human participation in the conversation, web UI, REST, WebSockets,

  React, Postgres, distributed workers, automatic model tuning, or new frameworks.

**Manual test after this step:** watch three agents sharing one local model talk,

respond to one another, harvest, and contribute live. Let the simulation continue

without prompts from the user, then press Ctrl+C and verify its saved checkpoint.

Repeat with another model assignment and with Ollama unavailable.

## Recommended Sequence and Exact Terminal Target

1. Start from the completed M2-02 baseline. Do not re-verify completed milestones

unless there is concrete evidence of a regression or inconsistency.

2. M2-01 connects distinct agent context to the already working shared provider.

3. M2-02 makes speech a validated part of the world with explicit delivery rules.

4. M2-03 adds bounded cognition cadence, wall-clock pacing, and safe stopping.

5. M2-04 displays committed dialogue/actions live and verifies the full local path.

This is the shortest safe path because it reuses the existing provider, commons

world, scheduler, event bus, and SQLite checkpoint boundary. Comparison and replay

provide later analysis, not a prerequisite for talking agents. Safety and bounded

state precede an indefinite run; a terminal observer requires no server or UI stack.

**First real Ollama test:** available now through M0-07/M0-08 and the existing

`scenarios/examples/ollama.yaml`; M2-01 extends that to distinct shared-backend

agents. **First finite multi-agent conversation:** M2-02 through the social mock

and Ollama scenarios. **First live multi-agent conversation:** M2-04. No

additional infrastructure is scheduled beyond this target.

The following is the **proposed final interface**, not a claim that the new file

or CLI options already exist. Real Ollama compatibility is verified manually by

the user against the installed Ollama release; the tag below matches the existing

repository example.

In a VS Code PowerShell terminal, start Ollama if its app/service is not already

serving; leave this terminal open:

```powershell

ollama serve

```

In a second PowerShell terminal:

```powershell

Set-Location C:\Programmering\ai-antfarm

uv sync --dev

ollama pull qwen3.5:0.8b

uv run antfarm validate scenarios/examples/social-ollama.yaml

uv run antfarm inspect scenarios/examples/social-ollama.yaml

uv run antfarm run scenarios/examples/social-ollama.yaml --live --continuous --tick-seconds 1

```

The proposed scenario assigns Alice, Bob, and Charlie different personalities but

the same model reference and `http://localhost:11434/v1` provider. It selects the

social commons mode, SQLite storage, bounded conversation/memory, staggered cadence,

and one cognition per tick. A second local model is an optional YAML assignment,

not a second agent process. Requests cause the backend to load the chosen models.

Illustrative output (wording, decisions, and timing vary with the model):

```text

run=social-<unique-id> agents=3 backend=local-ollama model=qwen3.5:0.8b

continuous; tick interval >= 1s; cognition budget=1; Ctrl+C to stop

[tick 1] Alice says: "Let's leave some resources for everyone."

[tick 2] Bob says: "Agreed. I'll take one and contribute later."

[tick 3] Charlie harvests 1; resource=4

...

Stopping... last committed tick=27 checkpoint=<local database path>

```

The simulation runs autonomously without entering text. A tick can take longer

than one second while a model responds. Speech is displayed only after validation

and commit, reaches other agents on subsequent ticks, and can influence their next

scheduled decisions. Ctrl+C ends the run with a consistent checkpoint.

**Roadmap endpoint:** I can run AntFarm from a terminal with several Ollama-backed

local AI agents that autonomously act and talk to each other live in a shared

simulation.
