# Repository Guidelines

## Project Structure & Module Organization

Read this file and every document under `docs/` before making changes. AntFarm AI is currently implementing M2. Architecture decisions live in `docs/ARCHITECTURE.md`, milestone progress lives in `docs/ROADMAP.md`, and accepted decisions live in `docs/adr/`.

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

## Milestone workflow

Treat the repository, ROADMAP.md, accepted ADRs, and current implementation as
the source of truth.

### Starting a milestone

When starting a new milestone:

- Read only the documentation and implementation relevant to the requested milestone.
- Inspect git status and recent history to understand the current repository state.
- Do not rerun the previous milestone's full verification if it is already marked
  complete and committed.
- Only investigate previous work if there is concrete evidence of a regression,
  inconsistency, failing test, or architectural problem.
- Do not perform manual local runtime checks, Ollama smoke tests, GPU tests, or
  other environment-specific verification unless explicitly requested.
- The user performs manual/local verification.

### During implementation

- Work only on the requested milestone.
- Follow the existing architecture and accepted ADRs.
- Prefer focused tests for the code currently being changed.
- Do not repeatedly run the full test suite after small changes.
- Do not perform unrelated refactors.
- Do not implement later roadmap milestones speculatively.
- Add or update tests only where they provide meaningful coverage for the new behavior.

### Completing a milestone

When implementation is complete:

1. Run the relevant automated tests for the changed functionality.
2. Run Ruff and mypy when Python code was changed.
3. Run the full automated test suite once at the end when appropriate.
4. Run `git diff --check`.
5. Review the final diff for accidental or unrelated changes.
6. Update ROADMAP.md and other status documentation where appropriate.
7. Commit the completed milestone with a concise conventional commit message.
8. Attempt to push the commit to `origin/main`.

If `git push` is blocked by an approval, external-data-egress guard, or other
Codex security policy:

- do not repeatedly retry;
- do not attempt to bypass the guard;
- leave the local commit intact;
- report the exact `git push` command the user should run manually.

Do not begin the next milestone unless explicitly requested.

### Manual verification

The user is responsible for:

- real Ollama smoke tests;
- local model compatibility tests;
- GPU/performance measurements;
- interactive/manual behavior checks;
- other machine-specific verification.

Provide concise manual test instructions when useful, but do not perform those
tests unless explicitly requested.

### Final report

Keep the final report concise.

Report:

- what was implemented;
- automated checks performed and their result;
- commit hash;
- push result;
- exact manual push command if push was blocked;
- anything important the user should manually test.

Do not repeat large implementation summaries already present in ROADMAP.md.
