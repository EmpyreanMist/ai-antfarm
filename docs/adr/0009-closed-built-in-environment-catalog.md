# ADR-0009: Closed Built-in Environment and Action Catalog

- **Status:** Accepted
- **Context:** M1 needs multiple simulation domains without allowing scenario files to import arbitrary code or moving action semantics into agents and model providers.
- **Decision:** Built-in environments and their compatible action families are selected through a closed, typed configuration union. Environments remain the sole owners of validation and mutation. The composition root supplies provider-neutral action descriptions to agents, while scenario validation rejects environment/action mismatches before execution.
- **Consequences:** New built-ins require explicit schema, composition, documentation, and tests. Dynamic third-party discovery remains deferred until a concrete extension contract is justified.
