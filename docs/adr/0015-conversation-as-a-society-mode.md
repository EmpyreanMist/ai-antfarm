# ADR-0015: Conversation as a Society Mode

- **Status:** Accepted
- **Context:** The primary local-model experience should let a user create
  characters and start an autonomous conversation without configuring economic
  actions, while preserving memory, privacy, event, replay, and model boundaries.
- **Decision:** Implement Conversation as a registered Game Mode that resolves a
  social-commons scenario with validated topic, situation, turn, and memory
  settings. Restrict resolved actions to `say` and schedule one cognition per
  tick. Reuse Agent Builder profiles, per-agent model assignment, ordinary model
  requests, committed public messages, and the standard run lifecycle.
- **Consequences:** There is no special chat loop or browser-to-model connection.
  Presets stay editable, private motives remain private model context, and runs
  remain inspectable, stoppable, replayable, and comparable. Voice, direct
  messages, and private chain-of-thought remain out of scope.
