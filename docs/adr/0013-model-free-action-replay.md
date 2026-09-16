# ADR-0013: Model-Free Recorded-Action Replay

- **Status:** Accepted
- **Context:** Completed Society and custom runs need trustworthy exploration and
  comparison without repeating cognition, requiring a model runtime, or claiming
  that the event log is a complete source for every internal engine component.
- **Decision:** Rebuild the initial authoritative environment from the stored
  versioned scenario and reapply only committed `action.applied` records through
  normal validation and mutation with the stored seed. Verify ordered tick/event
  boundaries, validated-action causation, action results, and the final checkpoint.
  Expose bounded application replay/comparison projections.
- **Consequences:** World timelines, generic metrics, and comparisons are
  deterministic and provider-free. Memory, scheduler internals, branching,
  mid-run resume, and full event sourcing are not implied.
