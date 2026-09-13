from pathlib import Path

import pytest
from pydantic import ValidationError

from antfarm.config import load_scenario


def test_unknown_fields_are_rejected(tmp_path: Path) -> None:
    scenario = tmp_path / "unknown.yaml"
    scenario.write_text(
        """\
schema_version: 1
run:
  id: test
  ticks: 1
  unexpected: true
provider:
  kind: mock
  decisions: {}
agents:
  - id: alice
environment:
  kind: counter
""",
        encoding="utf-8",
    )

    with pytest.raises(ValidationError, match="unexpected"):
        load_scenario(scenario)


def test_duplicate_agent_ids_are_rejected(tmp_path: Path) -> None:
    scenario = tmp_path / "duplicates.yaml"
    scenario.write_text(
        """\
schema_version: 1
run:
  id: test
provider:
  kind: mock
  decisions: {}
agents:
  - id: alice
  - id: alice
environment:
  kind: counter
""",
        encoding="utf-8",
    )

    with pytest.raises(ValidationError, match="unique"):
        load_scenario(scenario)
