# Repository Guidelines

## Project Structure & Module Organization

Read this file and every document under `docs/` before making changes. AntFarm AI is currently implementing M0. Architecture decisions live in `docs/ARCHITECTURE.md`, milestone progress lives in `docs/ROADMAP.md`, and accepted decisions live in `docs/adr/`.

M0 will use a `src` layout: domain types in `src/antfarm/domain/`, orchestration in `application/`, stable dependency interfaces in `ports/`, and provider, memory, and persistence implementations in `adapters/`. Put example configurations in `scenarios/examples/` and mirror package areas under `tests/unit/` and `tests/integration/`.

## Build, Test, and Development Commands

The standard development commands are:

- `uv sync --dev` — create the locked development environment.
- `uv run antfarm validate scenarios/examples/minimal.yaml` — validate a scenario.
- `uv run antfarm run scenarios/examples/minimal.yaml` — run the offline deterministic example.
- `uv run pytest` — run all automated tests.
- `uv run ruff check .` — run lint checks.
- `uv run mypy src tests` — run strict type checks.

Do not document a command as available before its tooling exists.

## Coding Style & Naming Conventions

Target Python 3.12+, use four-space indentation, full type annotations, and immutable domain values where practical. Use `snake_case` for modules, functions, and variables; `PascalCase` for classes and protocols; and `UPPER_SNAKE_CASE` for constants. Keep provider-specific types inside their adapters. Ruff is the formatter/linter authority; avoid manual style exceptions.

## Testing Guidelines

Use pytest. Name files `test_<subject>.py` and tests `test_<behavior>`. Core tests must run without network access, API credentials, a GPU, or external model runtimes. Use deterministic mock providers and fixed seeds. Separate tests that exercise SQLite or HTTP adapters under `tests/integration/`.

## Commit & Pull Request Guidelines

Use Conventional Commits, for example `feat(engine): add deterministic step ordering`. Keep commits focused. Pull requests must explain scope, link the relevant roadmap issue, list verification commands, and call out architecture or schema changes. Include screenshots only when a future UI change affects rendered behavior.

## Architecture & Security

The engine alone mutates world state. LLMs propose actions; environments validate them before application. Keep OASIS, CAMEL, Ollama, and other vendors behind adapters. Never place secrets in scenarios, fixtures, logs, events, or commits; configuration should reference environment-variable names instead.
