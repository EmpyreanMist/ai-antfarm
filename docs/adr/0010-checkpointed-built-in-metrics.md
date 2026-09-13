# ADR-0010: Checkpointed Built-in Event Metrics

- **Status:** Accepted
- **Context:** M1 experiments need deterministic summaries that survive recovery,
  but metric code must not observe or mutate live world state. Updating collector
  state before a failed step commit would also make summaries disagree with the
  durable event log.
- **Decision:** Select metrics from a closed built-in catalog. Collectors derive
  summaries only from ordered event envelopes. Before a step commit, the engine
  uses a side-effect-free projection to include the resulting metric state in the
  atomic checkpoint. After the commit succeeds, the event bus delivers those
  committed events to the live collector. Recovery restores the collector from
  checkpointed metric state.
- **Consequences:** Metric summaries stay aligned with checkpoints and cannot
  influence environment mutation. Adding a built-in requires explicit schema,
  composition, documentation, and tests. Arbitrary metric plugins, dashboards,
  and external telemetry remain deferred.
