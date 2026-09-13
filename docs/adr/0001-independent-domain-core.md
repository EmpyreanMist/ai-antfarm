# ADR-0001: Independent Domain Core

- **Status:** Accepted
- **Context:** AntFarm must support interchangeable model providers, local runtimes, and optional simulation frameworks without adopting their domain models.
- **Decision:** AntFarm owns its agent, environment, action, event, memory, scheduling, and scenario types. External SDKs and frameworks are used only inside adapters. Dependencies point inward toward domain contracts.
- **Consequences:** Integrations require translation code, but the core remains testable, portable, and independently evolvable.
