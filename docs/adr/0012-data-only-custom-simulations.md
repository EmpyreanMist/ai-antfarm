# ADR-0012: Data-Only Custom Simulation Definitions

- **Status:** Accepted
- **Context:** Fully custom simulations must represent domains outside Society
  without making rich-agent fields universal or allowing authored configuration
  to execute arbitrary server code. They must retain the engine's authoritative
  validation, mutation, ordering, persistence, and observation boundaries.
- **Decision:** Custom simulations use a separate, strict, versioned data schema.
  Entity types declare typed fields and public, owner-only, or internal
  visibility. Actions declare typed parameters, constraints, and a deliberately
  small transition vocabulary over world or actor state. A declarative
  environment validates and applies those transitions, then composes with the
  existing `SimulationEngine`. Entities may follow deterministic action plans or
  use model providers injected through the existing provider port. Definitions
  cannot name imports, expressions, templates, commands, or executable hooks.
- **Consequences:** Non-Society and non-LLM simulations share the established run,
  event, checkpoint, cancellation, and query lifecycle. The initial transition
  language is intentionally limited to comparisons and set/add effects; it grows
  only when concrete simulations require more. Schema-version-1 Society files
  remain supported unchanged, and the web builder is a later adapter over this
  shared definition rather than its owner.
