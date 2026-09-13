# AntFarm AI Vision

## Purpose

AntFarm AI is a long-lived, open-source framework for building artificial societies
populated by autonomous AI agents.

It should let researchers, developers, educators, and experimenters describe a
society as configuration, run it with local or remote language models, observe
agents acting and communicating in a shared world, inspect what happened, and
compare experiments without tying the simulation to one model provider or agent
framework.

AntFarm should support both reproducible experiments and interactive simulations
where AI agents can develop distinct behavior, memories, relationships, and
social dynamics over time.

## Product Principles

- **Domain-owned simulation:** AntFarm defines agents, environments, actions,
  communication, state, time, and events. External frameworks and model runtimes
  integrate through adapters.

- **Local-first operation:** A complete simulation must be runnable locally,
  including with local language models, without requiring data to be sent to a
  hosted model provider.

- **Configuration over forks:** Users select providers, models, agent counts,
  model assignments, personalities, environments, actions, memory, schedules,
  rules, seeds, and metrics through validated scenarios.

- **Distinct agents, shared intelligence:** Many agents may share the same model
  backend while retaining separate identities, personalities, memories, state,
  and observations.

- **Safe agency:** Models can propose structured actions and communication but
  never mutate world state directly. The simulation validates and applies all
  effects.

- **Agent communication is simulation state:** Speech and other interaction
  between agents belong to the controlled simulation lifecycle and cannot bypass
  validation or directly alter another agent's private state.

- **Reproducible evidence:** Seeded non-model behavior, ordered events,
  checkpoints, and captured outcomes make runs auditable and support later
  comparison and replay.

- **Observable societies:** Users should be able to watch agents act,
  communicate, and respond to changes while a simulation is running.

- **Small stable boundaries:** Extension points exist only where an
  interchangeable implementation is already required. Infrastructure and
  frameworks must not leak into the simulation domain.

## Foundation Outcome

The completed foundation establishes a Python 3.12+ library and CLI with:

1. Strict, versioned scenario configuration.
2. Deterministic agent-pool expansion and model assignment.
3. Agent scheduling and bounded memory.
4. Provider-independent model requests.
5. Validated action proposals and environment-owned mutation.
6. Ordered, versioned events.
7. Atomic SQLite event and checkpoint persistence.
8. Deterministic checkpoint recovery.
9. A deterministic mock provider for offline testing.
10. A generic OpenAI-compatible provider for local and remote models.
11. CLI workflows for validating, inspecting, and running simulations.

The deterministic mock path remains the reproducible baseline. Real language
models are intentionally nondeterministic.

## Interactive Society Target

The first interactive AntFarm experience should allow a user to:

1. Start a local model runtime such as Ollama.
2. Configure several distinct agents to share one or more local models.
3. Give each agent its own identity, personality, memory, and state.
4. Start the society from a terminal.
5. Let agents autonomously observe the world, think, and choose actions.
6. Let agents communicate freely with one another through validated simulation
   actions.
7. Allow communication to influence later observations and decisions.
8. Watch committed speech and world actions appear live while the simulation runs.
9. Let cognition happen at controlled cadences rather than requiring every agent
   to invoke a model every tick.
10. Stop the simulation safely and resume from durable state.

This interactive terminal society is the first major product experience beyond
the deterministic foundation.

## Long-Term Direction

AntFarm should remain independent of any specific presentation layer.

The same simulation may eventually be observed or controlled through:

- a terminal;
- a web interface;
- visualization and experiment dashboards;
- a 2D or 3D world;
- a game client where a human can enter the simulated world and interact with
  autonomous agents;
- external APIs or research tooling.

Presentation layers should consume AntFarm state and events rather than becoming
part of the simulation core.

Later capabilities may include richer environments and social systems, improved
memory, relationships, economies, run comparison, replay, human-agent interaction,
voice, visual observation, network APIs, parallel cognition, larger populations,
Postgres, and evidence-led integrations with frameworks such as OASIS or CAMEL.

These capabilities must reuse AntFarm contracts rather than redefine them.

## Non-Goals

AntFarm is not:

- an LLM serving system;
- a wrapper around Ollama or another model runtime;
- a social-network-only simulator;
- a general workflow engine;
- a wrapper around one external agent framework;
- a game engine or rendering engine.

AntFarm does not require every simulated agent to have a dedicated loaded model
instance.

The core simulation should not depend on a web UI, 3D client, REST API, specific
database, model vendor, or external multi-agent framework.

Exact reproduction of nondeterministic language-model generation is not a goal.
Instead, AntFarm aims to make the surrounding simulation state, actions, events,
and outcomes inspectable and reproducible wherever possible.
