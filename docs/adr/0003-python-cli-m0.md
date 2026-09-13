# ADR-0003: Python Library and CLI for M0

- **Status:** Accepted
- **Context:** M0 needs a small usable surface and compatibility with the Python AI and simulation ecosystem without introducing a network service.
- **Decision:** Target Python 3.12+ as an installable library with a standard-library `argparse` CLI. Run cognition asynchronously but keep one process and deterministic sequential action application.
- **Consequences:** M0 remains easy to run locally. REST, WebSockets, frontend code, and distributed workers are postponed.
