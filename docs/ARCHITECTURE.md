# AntFarm Architecture

## Context and Boundaries

AntFarm AI uses a ports-and-adapters architecture. The domain owns simulation concepts; the application layer coordinates them; adapters handle model APIs, memory implementations, persistence, and future transports. Imports point inward: domain code must not import adapters, databases, HTTP clients, OASIS, CAMEL, or provider SDKs.

The current execution topology is one Python 3.12+ process with one simulation engine and one SQLite writer. The public surface is an installable library plus a small CLI. REST, WebSockets, UI code, distributed workers, and dynamic plugin discovery remain outside the current milestone.

## Simulation Lifecycle

```text
Validated Scenario
    -> Composition Root
    -> SimulationEngine advances one tick
    -> CognitionScheduler selects due agents in stable order
    -> Engine builds bounded observations and recalls memory
    -> Agent asks its configured ModelProvider for a proposal
    -> Environment validates the proposal
    -> Engine applies only a ValidatedAction
    -> Storage commits the event batch and checkpoint atomically
    -> EventBus notifies observers and metric collectors
```

The engine owns the tick, event sequence, seeded random source, registry of agents, and mutation order. M0 awaits cognition sequentially and applies actions sequentially. Provider latency therefore affects throughput but cannot reorder state transitions. No mutable world object crosses into an agent or provider.

Each model-backed agent resolves its public identity and optional private
personality into immutable, provider-neutral request values. The request also
contains only that agent's bounded recall and current agent-scoped observation.
Agents assigned the same model reference share one provider instance, but the
provider is stateless with respect to agent identity: private personality and
memory are supplied afresh on every request and never enter another agent's
observation. Mutable holdings remain owned by the environment.

The commons environment has an explicit social mode with one public room. A
model may propose `say`, but the engine remains the source of the authenticated
actor and current tick, and the environment validates bounded non-empty text.
Accepted messages receive deterministic IDs. Messages applied during tick T are
excluded from every observation in T, delivered to each configured agent's
bounded memory after cognition finishes, and become visible in bounded public
history in T+1. Public observations contain only a bounded ID roster, shared
resources, the observer's own holding, and recent accepted messages; personality
and private recall never cross between agents. Text in observations and memory is
untrusted simulation data and cannot change the action contract.

Malformed output, timeout, validation failure, and rejected actions produce structured failure events and leave world state unchanged. Event subscribers run after persistence and are observational; they cannot participate in state mutation.

M1 includes a closed catalog of event-derived metrics: applied-action counts by
kind, rejection counts, cognition-failure counts by kind, and per-agent terminal
outcomes. A collector has no environment reference. The engine projects the next
summary without mutating the collector, stores that summary in the same atomic
checkpoint as the step, and only then publishes the committed events that advance
the live collector. Metric state therefore restores with the checkpoint and a
failed commit cannot advance it.

The scheduler combines stable intervals, per-agent or per-pool cadence overrides,
deterministic starting offsets, cooldowns, optional event triggers, capped failure
retry cooldowns, and a cognition budget. Due agents remain in a bounded set and a
checkpointed cursor rotates fairly through stable IDs. Accepted public speech
wakes its recipients, excluding its speaker, for a future eligible tick. Matching
configured actor events retain their existing actor semantics, while actor-less
events schedule all known agents. Event-only scheduling remains idle until a
matching event occurs. Due state, offsets, cooldowns, retry state, and the fairness
cursor are part of every simulation snapshot.

Finite execution remains unpaced. An explicit continuous application runner calls
one `engine.step()` at a time and uses a monotonic clock to enforce a minimum
interval between tick starts. Slow steps create no catch-up debt. It emits each
committed batch to an optional consumer without accumulating a `RunResult` event
history; the process-local bus retains only a configured bounded window while
SQLite remains the durable append-only audit.

Before each step, the engine captures its last complete state. Cancellation or a
commit failure restores world, memory, scheduler, metrics, tick, event sequence,
and random state before the error leaves the engine. Subscriber failures are
isolated after commit and cannot retry or roll back an action. The generic
OpenAI-compatible adapter uses cancellable asyncio HTTP connections, so timeout or
task cancellation closes the in-flight socket instead of leaving worker-thread
requests running.

Live terminal presentation is an adapter over that post-commit event boundary.
It subscribes only to applied, rejected, no-op, and cognition-failure events and
renders plain flushed lines without ANSI control. Model text is made single-line
and control characters are neutralized. Normal mode omits cognition-start and
waiting lines; explicit verbose mode renders those lifecycle callbacks as marked
status that is never persisted. If output fails after a commit, the observer
records the failure and the continuous runner stops after that batch without
invoking the committed step again.

A live-only model override produces a newly validated in-memory scenario for the
run and changes the concrete model on active model references without rewriting
YAML or changing provider settings. Providers marked with the `ollama` runtime are
checked through the adapter's `/api/tags` preflight before composition creates a
durable run. Domain, scheduler, event, and persistence contracts remain unaware of
Ollama.

## Core Contracts

These signatures describe boundaries, not inheritance-heavy base classes. Concrete types may use frozen dataclasses and `typing.Protocol`.

`Agent`, `AgentIdentity`, `AgentPersonality`, `Environment`, `ActionProposal`, and event values belong to `domain/`. `CognitionScheduler` and `SimulationEngine` belong to `application/`. `ModelProvider`, `MemoryStore`, `EventBus`, and `Storage` belong to `ports/`; their implementations belong to `adapters/`. The composition root resolves each agent's `model_ref` and personality reference and injects the selected provider into the concrete agent without exposing adapter configuration in its public contract.

```python
class ModelProvider(Protocol):
    capabilities: ProviderCapabilities
    async def generate(self, request: ModelRequest) -> ModelResponse: ...
    async def close(self) -> None: ...

class Agent(Protocol):
    id: AgentId
    model_ref: str
    async def decide(self, context: AgentContext) -> ActionProposal | None: ...

class Environment(Protocol):
    def observe(self, agent_id: AgentId, tick: Tick) -> Observation: ...
    def validate(self, proposal: ActionProposal) -> ValidationResult: ...
    def apply(
        self, action: ValidatedAction, rng: RandomSource, tick: Tick
    ) -> ActionResult: ...
    def memory_deliveries(
        self, action: ValidatedAction, result: ActionResult
    ) -> Mapping[AgentId, Sequence[MemoryItem]]: ...
    def snapshot(self) -> WorldState: ...
    def restore(self, state: WorldState) -> None: ...

class MemoryStore(Protocol):
    def recall(self, agent_id: AgentId, query: MemoryQuery) -> Sequence[MemoryItem]: ...
    def append(self, agent_id: AgentId, items: Sequence[MemoryItem]) -> None: ...
    def snapshot(self) -> MemoryState: ...
    def restore(self, state: MemoryState) -> None: ...

class CognitionScheduler(Protocol):
    def select(self, context: ScheduleContext) -> Sequence[AgentId]: ...
    def record(self, outcomes: Sequence[CognitionOutcome]) -> None: ...
    def notify(self, events: Sequence[Event]) -> None: ...
    def snapshot(self) -> JsonObject: ...
    def restore(self, state: JsonObject) -> None: ...

class EventBus(Protocol):
    def publish(self, events: Sequence[Event]) -> None: ...
    def subscribe(self, kinds: set[str], handler: EventHandler) -> Subscription: ...

class SimulationEngine:
    async def step(self) -> StepResult: ...
    async def run(self, limit: RunLimit) -> RunResult: ...
    def snapshot(self) -> SimulationSnapshot: ...

class Storage(Protocol):
    def close(self) -> None: ...
    def create_run(self, metadata: RunMetadata, scenario: JsonObject) -> None: ...
    def commit_step(
        self,
        run_id: RunId,
        snapshot: SimulationSnapshot,
        events: Sequence[Event],
    ) -> None: ...
    def load_latest(self, run_id: RunId) -> StoredCheckpoint | None: ...
    def read_events(self, run_id: RunId, after: int = 0) -> Iterable[Event]: ...
```

`ActionProposal`, `ValidatedAction`, `ActionResult`, and `Event` are immutable values. Actions carry a kind, actor ID, and JSON-compatible parameters; they do not execute themselves. Only an environment can turn a proposal into a validated action and apply it.

An event envelope contains `schema_version`, `event_id`, `run_id`, monotonic `sequence`, `tick`, `kind`, optional `actor_id`, optional `causation_id`, and a JSON-compatible payload. Logical sequence and tick determine simulation order; wall-clock timestamps are observational metadata only.

## Scenario Configuration

Scenarios are authored as YAML 1.2, loaded without executable tags, and validated strictly before composition. Unknown fields, duplicate identifiers, invalid references, and unsupported component kinds are errors. A normalized JSON representation is stored with each run.

The versioned `ScenarioConfig` contains:

- A master seed, run limits, and engine settings
- An optional validated active-agent prefix, bounded to 1–10 for M2-04
- Named provider connections and named model configurations
- Explicit agents and deterministically expanded agent pools
- Personality references and per-agent or per-pool model references
- One environment kind/configuration and enabled action kinds
- Memory strategy and cognition schedule configuration
- Simulation rules, built-in metric identifiers, observability policy, and storage settings

Provider secrets are never embedded in scenarios. Configuration refers to environment-variable names. Component kinds resolve through a closed registry in the composition root; scenario files cannot name arbitrary Python imports.

The built-in environment catalog currently contains the deterministic `counter`
environment with `increment`, and the finite shared-resource `commons`
environment with `harvest` and `contribute`. Explicit commons social configuration
also enables `say`, bounded message history, and a bounded public roster. Scenario
validation rejects action kinds that are incompatible with the selected mode. The
composition root also supplies provider-neutral action descriptions to
model-backed agents; environments remain the authority for validation, mutation,
and recipient selection.

## Persistence, Events, and Replay

SQLite is the first `Storage` adapter. One short transaction per step stores the ordered event batch and latest checkpoint. Checkpoints, not an event fold, are the M0 recovery source of truth. Memory, scheduler, metric-summary, event-sequence, and pseudorandom-generator state needed to continue a run are included in the checkpoint contract.

Events support audit and metrics now and prepare for replay later. A future replay reads recorded accepted actions and outcomes; it must not call a model again. Raw prompts and responses are not persisted by default because they may contain secrets or personal data. Full event sourcing, branching histories, retention automation, and Postgres are deferred.

## Provider and Framework Policy

M0 includes a deterministic mock provider and one generic OpenAI-compatible adapter with a configurable base URL. The AntFarm `ModelProvider` request and response types remain independent of the OpenAI wire format. Ollama, vLLM, LM Studio, and remote services are endpoint choices or later adapters, never domain dependencies.

Structured-output compatibility stays inside that generic adapter. It sends the
closed response schema through the OpenAI-compatible `response_format` field and
repeats the exact schema in the system instruction for endpoints that do not fully
enforce the wire-level constraint. It accepts a bare JSON object or one complete
Markdown JSON fence, but does not extract JSON from arbitrary prose or reasoning.
Malformed-response errors expose bounded diagnostics without including raw prompts
or model output. Scenario parameters must follow the selected endpoint contract;
for example, Ollama's OpenAI-compatible endpoint uses `reasoning_effort`, while
the native-only `think` request field is not sent.

OASIS is postponed. Its social-media simulation model and CAMEL-linked types would otherwise compete with AntFarm's ownership of environments, actions, agents, and time. A future compatibility spike may introduce an optional adapter for a concrete social-media scenario, but no OASIS or CAMEL type may cross an AntFarm port.

## Repository Shape

```text
src/antfarm/
  domain/          # Immutable simulation values and contracts
  application/     # Engine and scheduler orchestration
  ports/           # Model, memory, event, and storage boundaries
  adapters/
    models/        # Mock and OpenAI-compatible implementations
    memory/        # Initial in-memory implementation
    storage/       # SQLite implementation
  config/          # Strict schema, YAML loader, composition registry
  cli.py
scenarios/examples/
tests/{unit,integration,fixtures}/
docs/adr/
```

## Known Risks and Deferrals

- Model generation is nondeterministic; persist normalized proposals and outcomes for audit and replay.
- Large observations and unbounded recalls will dominate cost; environments expose bounded observations and memory queries require limits.
- SQLite is unsuitable for many writers; M0 explicitly supports one process and batches writes by step.
- Provider calls may stall; adapters enforce configured timeouts and emit safe failures.
- Scenario and event churn can break stored runs; both are versioned from their first persisted form.
- Custom metrics initially consume events. A dedicated metrics plugin contract waits for a concrete need.
