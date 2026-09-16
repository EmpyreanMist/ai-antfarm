# ADR-0014: Web Agent Drafts and Provider-Neutral Model Inventory

- **Status:** Accepted
- **Context:** Normal browser use needs installed local-model selection and fully
  editable manual, random, or mixed populations without requiring YAML or model
  tag memorization.
- **Decision:** Discover models behind `ModelInventory`, with Ollama as the first
  adapter. Represent browser authoring as temporary agent drafts containing the
  standard profile data and optional concrete model tag. At preview time,
  normalize drafts into ordinary versioned `ScenarioConfig` agents, profiles, and
  provider-backed model configurations before any durable run is created.
- **Consequences:** Browser, CLI, and YAML runs share validation, inspection,
  preflight, persistence, and execution. Generated agents remain editable normal
  agents. Inventory access stays server-side. Model download/lifecycle management
  and an unbounded population editor remain deferred.
