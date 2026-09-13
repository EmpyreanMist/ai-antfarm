# AntFarm AI Vision

## Purpose

AntFarm AI is a long-lived, open-source framework for building reproducible artificial-society simulations. It should let researchers, developers, educators, and experimenters describe a society as configuration, run it with local or remote language models, inspect what happened, and compare runs without tying their work to one provider or agent framework.

## Product Principles

- **Domain-owned simulation:** AntFarm defines agents, environments, actions, state, time, and events. External frameworks integrate through adapters.
- **Local-first operation:** A complete simulation must be runnable with local infrastructure and without sending data to a hosted model provider.
- **Configuration over forks:** Users select providers, models, agent counts, model assignments, personalities, environments, actions, memory, schedules, rules, seeds, and metrics through validated scenarios.
- **Safe agency:** Models can propose structured actions but never mutate world state directly. Invalid proposals fail without side effects.
- **Reproducible evidence:** Seeded non-model behavior, ordered events, checkpoints, and captured action outcomes make runs auditable and prepare the system for replay.
- **Small stable boundaries:** Extension points exist only where an interchangeable implementation is already required.

## M0 Outcome

M0 establishes a Python 3.12+ library and CLI that can validate and run one small scenario using a deterministic mock model. It proves the engine lifecycle, scheduling, action validation, event ordering, memory boundary, and SQLite recovery without requiring a network, GPU, Ollama, OASIS, or CAMEL.

A successful M0 run can:

1. Load a strict, versioned YAML scenario.
2. Deterministically expand agent pools and assign named model configurations.
3. Schedule only agents that are due to think.
4. Turn model output into validated action proposals.
5. Mutate state through the environment and emit ordered events.
6. Persist a checkpoint and event batch atomically.
7. Produce the same observable result for repeated seeded mock runs.

## Long-Term Capabilities

Later milestones may add richer environments and memory strategies, user-defined metrics, replay tooling, visual observation, network APIs, parallel execution, Postgres, and adapters for frameworks such as OASIS or CAMEL. These capabilities must reuse AntFarm contracts rather than redefine them.

## Non-Goals

AntFarm is not an LLM serving system, a social-network-only simulator, a general workflow engine, or a wrapper around one external framework. M0 does not target distributed execution, thousands of concurrent agents, semantic/vector memory, a web UI, real-time streaming, or byte-for-byte reproduction of nondeterministic model generation.
