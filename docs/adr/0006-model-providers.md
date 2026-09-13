# ADR-0006: Mock and OpenAI-Compatible Providers First

- **Status:** Accepted
- **Context:** M0 must work without a network or GPU while allowing local and remote language models through one boundary.
- **Decision:** Implement a deterministic mock provider for tests and a generic OpenAI-compatible adapter with configurable base URL and model. AntFarm owns the provider request and response contracts; the adapter translates the external wire format.
- **Consequences:** Ollama, vLLM, LM Studio, and hosted endpoints can be configured where compatible without becoming core dependencies. Vendor-specific capabilities wait for concrete requirements.
