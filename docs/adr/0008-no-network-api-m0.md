# ADR-0008: No Network API in M0

- **Status:** Accepted
- **Context:** A transport contract before the simulation lifecycle stabilizes would enlarge M0 and risk exposing internal state and unstable operations.
- **Decision:** M0 provides a library and CLI only. A later control/query API should begin with REST. WebSockets are added only when a concrete live client requires event streaming.
- **Consequences:** M0 focuses on correctness and durable contracts. Remote control, authentication, browser clients, and real-time delivery are postponed.
