"""Safe YAML 1.2 loading for scenarios."""

from pathlib import Path
from typing import Any

from ruamel.yaml import YAML

from antfarm.config.schema import ScenarioConfig


def load_scenario(path: str | Path) -> ScenarioConfig:
    """Load and strictly validate a YAML 1.2 scenario."""

    yaml = YAML(typ="safe", pure=True)
    yaml.version = (1, 2)
    with Path(path).open(encoding="utf-8") as stream:
        raw: Any = yaml.load(stream)
    if not isinstance(raw, dict):
        raise ValueError("scenario root must be a mapping")
    return ScenarioConfig.model_validate(raw)
