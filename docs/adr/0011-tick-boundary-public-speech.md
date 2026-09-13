# ADR-0011: Validated Public Speech at Tick Boundaries

- **Status:** Accepted
- **Context:** Social simulations need model-generated dialogue without allowing
  text to bypass environment validation, leak private agent context, or become
  visible to agents earlier in a step because of sequential action ordering.
- **Decision:** The social commons mode owns a single public room and a validated
  `say` action. The engine supplies the authenticated actor and authoritative tick.
  Accepted messages receive deterministic IDs and are persisted as action outcomes.
  Messages from tick T enter every configured agent's bounded memory after all
  cognition for T and become observable in T+1. Live message history, public
  rosters, and per-agent memory are bounded by scenario configuration.
- **Consequences:** Speech follows the same auditable proposal, validation,
  application, checkpoint, and event path as physical actions. Same-tick replies
  are intentionally impossible, older dialogue eventually leaves live context,
  and the SQLite event log remains the durable record. Private channels, human
  input, semantic memory, and live rendering remain deferred.
