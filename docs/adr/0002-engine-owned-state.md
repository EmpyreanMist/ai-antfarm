# ADR-0002: Engine-Owned State and Validated Actions

- **Status:** Accepted
- **Context:** Allowing agents, models, or event consumers to mutate state would make simulation behavior unsafe and difficult to reproduce.
- **Decision:** The engine owns simulation ordering and delegates mutations only to the active environment. Models produce immutable action proposals. The environment validates a proposal before the engine permits its application. Rejected proposals emit events without changing state.
- **Consequences:** All mutation follows one auditable path. Action execution may be sequential until a future design preserves the same ordering guarantees.
