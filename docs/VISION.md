# AntFarm AI Vision

## Purpose

AntFarm AI is a long-lived, open-source, web-first platform for building and
running simulations populated by autonomous AI agents and other configurable
entities.

It should let researchers, developers, educators, and experimenters select a
purpose-built simulation mode or define a fully custom simulation, run it with
local or remote language models, observe activity and state, inspect what
happened, and compare experiments without tying the simulation to one model
provider, agent framework, transport, or social/economic ontology.

AntFarm should support both reproducible experiments and interactive simulations
where AI agents can develop distinct behavior, memories, relationships, and
social dynamics over time. It must also support simulations where those concepts
are absent: money, relationships, reputation, society, and a physical environment
are optional rather than universal.

## Product Shape

AntFarm has two complementary creation paths over one simulation runtime:

1. **Game/simulation modes** package a curated domain with suitable configuration,
   defaults, rules, capabilities, validation, UX, and visualization hints. The
   existing artificial-society functionality is the first built-in **Society**
   mode. Debate, market, survival, governance, and other modes may follow when
   concrete product needs justify them.
2. **Custom simulation definitions** let users describe simulations that do not
   fit a built-in mode. They should eventually define entities and types, state,
   actions, observations, visibility, constraints, optional model assignments,
   activation, and
   termination through the web UI without requiring source changes or hand-edited
   YAML.

Modes and custom definitions share the same authoritative domain/application
lifecycle. Modes are not separate engines, and custom definitions are validated
data rather than executable code. The web application becomes the primary
user-facing control plane over time while CLI and library use remain supported.

## Product Principles

- **Domain-owned simulation:** AntFarm defines agents, environments, actions,
  communication, state, time, and events. External frameworks and model runtimes
  integrate through adapters.

- **Local-first operation:** A complete simulation must be runnable locally,
  including with local language models, without requiring data to be sent to a
  hosted model provider.

- **Configuration over forks:** Users select or define providers, models,
  entities, state, actions, observations, visibility, schedules, rules, seeds,
  termination, and metrics through validated mode or custom definitions.

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

- **Observable simulations:** Users should be able to watch entities act,
  communicate where applicable, change state, and respond while a simulation is
  running.

- **Server-authoritative web experience:** The browser configures and observes
  simulations through shared application/API contracts. It does not call the CLI,
  parse terminal output, read persistence directly, or own simulation rules.

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

## Completed Interactive Society Target

The first interactive AntFarm experience allows a user to:

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
10. Stop the simulation safely with its latest complete state persisted.

This interactive terminal society is the first major product experience beyond
the deterministic foundation and supplies the working capability for the first
built-in Society mode.

## First Web Product Target

The first web experience is a minimum end-to-end control plane over the completed
Society and M4 application-service contracts. A user should be able to select a
Society scenario, set supported runtime options, preview resolved agents, start a
run, watch committed events live, inspect agents and state, stop the run, and
inspect its durable result. This vertical slice precedes the final generic custom
simulation builder so the browser path can be tested and improved early.

This minimum Society path is implemented in M5. M6 adds the small, closed Game
Mode architecture and serves Society through transport-neutral discovery without
prematurely designing every possible mode. The next product target is the generic
custom simulation definition shared by application, API, and future builder.

## Long-Term Direction

AntFarm's core should remain independent of any specific presentation layer even
as the web application becomes its primary user-facing experience.

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

Later capabilities may include custom simulation authoring, AI-assisted structured
definition generation, richer mode-specific visualization, improved memory,
optional relationships and economies, run comparison, replay, human-agent
interaction, voice, visual observation, parallel cognition, larger populations,
Postgres, and evidence-led integrations with frameworks such as OASIS or CAMEL.

These capabilities must reuse AntFarm contracts rather than redefine them.

## Non-Goals

AntFarm is not:

- an LLM serving system;
- a wrapper around Ollama or another model runtime;
- a social-network-only simulator;
- an economic or relationship model required of every simulation;
- a general workflow engine;
- a wrapper around one external agent framework;
- a game engine or rendering engine.

AntFarm does not require every simulated agent to have a dedicated loaded model
instance.

The core simulation should not depend on a web UI, 3D client, HTTP/WebSocket API,
specific database, model vendor, or external multi-agent framework. Likewise, the
web application must not become a second simulation engine.

Exact reproduction of nondeterministic language-model generation is not a goal.
Instead, AntFarm aims to make the surrounding simulation state, actions, events,
and outcomes inspectable and reproducible wherever possible.
