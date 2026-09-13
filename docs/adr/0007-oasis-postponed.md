# ADR-0007: Postpone OASIS and CAMEL Integration

- **Status:** Accepted
- **Context:** [OASIS](https://docs.oasis.camel-ai.org/overview) is oriented toward social-media simulation and exposes its own platform, action, clock, agent, and CAMEL model concepts. Its [package configuration](https://github.com/camel-ai/oasis/blob/main/pyproject.toml) also introduces a substantial dependency and version surface.
- **Decision:** OASIS and CAMEL are not M0 dependencies. A later compatibility spike may build an optional adapter for a concrete scenario, with all external types translated at AntFarm ports.
- **Consequences:** M0 cannot reuse OASIS features directly, but AntFarm retains ownership of state, validation, configuration, and replay semantics.
