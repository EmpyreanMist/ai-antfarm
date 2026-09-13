# M0 Architecture

## Context and Boundaries

AntFarm AI uses a ports-and-adapters architecture. The domain owns simulation concepts; the application layer coordinates them; adapters handle model APIs, memory implementations, persistence, and future transports. Imports point inward: domain code must not import adapters, databases, HTTP clients, OASIS, CAMEL, or provider SDKs.

The M0 execution topology is one Python 3.12+ process with one simulation engine and one SQLite writer. The public surface is an installable library plus a small CLI. REST, WebSockets, UI code, distributed workers, and dynamic plugin discovery are outside M0.

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

Malformed output, timeout, validation failure, and rejected actions produce structured failure events and leave world state unchanged. Event subscribers run after persistence and are observational; they cannot participate in state mutation.

## Core Contracts

These signatures describe boundaries, not inheritance-heavy base classes. Concrete types may use frozen dataclasses and `typing.Protocol`.

`Agent`, `Environment`, `ActionProposal`, and event values belong to `domain/`. `CognitionScheduler` and `SimulationEngine` belong to `application/`. `ModelProvider`, `MemoryStore`, `EventBus`, and `Storage` belong to `ports/`; their implementations belong to `adapters/`. The composition root resolves each agent's `model_ref` and injects the selected provider into the concrete agent without exposing adapter configuration in its public contract.

```python
class ModelProvider(Protocol):
    capabilities: ProviderCapabilities
    async def generate(self, request: ModelRequest) -> ModelResponse: ...

class Agent(Protocol):
    id: AgentId
    model_ref: str
    async def decide(self, context: AgentContext) -> ActionProposal | None: ...

class Environment(Protocol):
    def observe(self, agent_id: AgentId) -> Observation: ...
    def validate(self, proposal: ActionProposal) -> ValidationResult: ...
    def apply(self, action: ValidatedAction, rng: RandomSource) -> ActionResult: ...
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

class EventBus(Protocol):
    def publish(self, events: Sequence[Event]) -> None: ...
    def subscribe(self, kinds: set[str], handler: EventHandler) -> Subscription: ...

class SimulationEngine:
    async def step(self) -> StepResult: ...
    async def run(self, limit: RunLimit) -> RunResult: ...
    def snapshot(self) -> SimulationSnapshot: ...

class Storage(Protocol):
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
- Named provider connections and named model configurations
- Explicit agents and deterministically expanded agent pools
- Personality references and per-agent or per-pool model references
- One environment kind/configuration and enabled action kinds
- Memory strategy and cognition schedule configuration
- Simulation rules, built-in metric identifiers, observability policy, and storage settings

Provider secrets are never embedded in scenarios. Configuration refers to environment-variable names. Component kinds resolve through a closed registry in the composition root; scenario files cannot name arbitrary Python imports.

## Persistence, Events, and Replay

SQLite is the first `Storage` adapter. One short transaction per step stores the ordered event batch and latest checkpoint. Checkpoints, not an event fold, are the M0 recovery source of truth. Memory and scheduler state needed to continue a run are included in the checkpoint contract.

Events support audit and metrics now and prepare for replay later. A future replay reads recorded accepted actions and outcomes; it must not call a model again. Raw prompts and responses are not persisted by default because they may contain secrets or personal data. Full event sourcing, branching histories, retention automation, and Postgres are deferred.

## Provider and Framework Policy

M0 includes a deterministic mock provider and one generic OpenAI-compatible adapter with a configurable base URL. The AntFarm `ModelProvider` request and response types remain independent of the OpenAI wire format. Ollama, vLLM, LM Studio, and remote services are endpoint choices or later adapters, never domain dependencies.

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
