# ADR-0005: SQLite Checkpoints and Ordered Events

- **Status:** Accepted
- **Context:** M0 needs durable recovery and observability without operating a database service or committing to full event sourcing.
- **Decision:** Place persistence behind `Storage`. Use SQLite with one writer and one transaction per simulation step to commit a checkpoint and ordered event batch atomically. The latest checkpoint is the recovery source of truth.
- **Consequences:** Local operation and crash recovery remain simple. Multiple writers, Postgres, branching histories, and rebuilding all state solely from events are deferred.
