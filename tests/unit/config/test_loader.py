from pathlib import Path

import pytest
from pydantic import ValidationError
from ruamel.yaml.constructor import ConstructorError, DuplicateKeyError

from antfarm.config import load_scenario


def test_unknown_fields_are_rejected(tmp_path: Path) -> None:
    repository = Path(__file__).parents[3]
    source = (repository / "scenarios/examples/minimal.yaml").read_text(
        encoding="utf-8"
    )
    scenario = tmp_path / "unknown.yaml"
    scenario.write_text(
        source.replace("  ticks: 1", "  ticks: 1\n  unexpected: true"),
        encoding="utf-8",
    )

    with pytest.raises(ValidationError, match="unexpected"):
        load_scenario(scenario)


def test_unsafe_yaml_tags_are_rejected(tmp_path: Path) -> None:
    scenario = tmp_path / "unsafe.yaml"
    scenario.write_text("!!python/object:builtins.object {}", encoding="utf-8")

    with pytest.raises(ConstructorError, match="could not determine a constructor"):
        load_scenario(scenario)


def test_duplicate_yaml_keys_are_rejected(tmp_path: Path) -> None:
    scenario = tmp_path / "duplicate.yaml"
    scenario.write_text("schema_version: 1\nschema_version: 1", encoding="utf-8")

    with pytest.raises(DuplicateKeyError, match="duplicate key"):
        load_scenario(scenario)


def test_yaml_uses_version_1_2_scalar_rules(tmp_path: Path) -> None:
    repository = Path(__file__).parents[3]
    source = (repository / "scenarios/examples/minimal.yaml").read_text(
        encoding="utf-8"
    )
    scenario = tmp_path / "yaml-1-2.yaml"
    scenario.write_text(
        source.replace("patience: high", "patience: yes"), encoding="utf-8"
    )

    config = load_scenario(scenario)

    assert config.personalities["patient"].traits["patience"] == "yes"
