"""Server-owned catalog of scenarios exposed to the web control plane."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from antfarm.config.schema import ScenarioConfig, SqliteStorageConfig
from antfarm.facade import AntFarmApplication


@dataclass(frozen=True, slots=True)
class CatalogDefinition:
    id: str
    filename: str
    name: str
    description: str
    runtime: str
    featured: bool = False


@dataclass(frozen=True, slots=True)
class CatalogScenario:
    definition: CatalogDefinition
    path: Path
    config: ScenarioConfig

    def view(self) -> dict[str, object]:
        agents = self.config.expand_agents()
        return {
            "id": self.definition.id,
            "mode": "society",
            "name": self.definition.name,
            "description": self.definition.description,
            "runtime": self.definition.runtime,
            "featured": self.definition.featured,
            "agent_count": len(agents),
            "default_active_agents": self.config.run.active_agents or len(agents),
            "seed": self.config.run.seed,
            "ticks": self.config.run.ticks,
            "environment": self.config.environment.kind,
            "models": sorted(model.model for model in self.config.models.values()),
            "durable": isinstance(self.config.storage, SqliteStorageConfig),
        }


CATALOG_DEFINITIONS = (
    CatalogDefinition(
        id="live-society-mock",
        filename="live-social-mock.yaml",
        name="Live Society · Mock",
        description="A deterministic ten-person commons with speech and actions.",
        runtime="mock",
        featured=True,
    ),
    CatalogDefinition(
        id="society-manual",
        filename="society-manual.yaml",
        name="Authored Society",
        description="Two richly configured agents with visible inequality.",
        runtime="mock",
    ),
    CatalogDefinition(
        id="society-randomized",
        filename="society-randomized.yaml",
        name="Generated Society",
        description="A seeded population generated from trait and economic ranges.",
        runtime="mock",
    ),
    CatalogDefinition(
        id="society-mixed",
        filename="society-mixed.yaml",
        name="Mixed Society",
        description="Authored and generated agents resolved into one population.",
        runtime="mock",
    ),
    CatalogDefinition(
        id="live-society-ollama",
        filename="live-social-ollama.yaml",
        name="Live Society · Ollama",
        description="The interactive Society scenario backed by a local model.",
        runtime="ollama",
    ),
)


class ScenarioCatalog:
    """Closed scenario catalog; identifiers never become filesystem paths."""

    def __init__(
        self,
        scenario_directory: Path,
        application: AntFarmApplication,
    ) -> None:
        self._items: dict[str, CatalogScenario] = {}
        root = scenario_directory.resolve()
        for definition in CATALOG_DEFINITIONS:
            path = (root / definition.filename).resolve()
            if path.parent != root or not path.is_file():
                continue
            self._items[definition.id] = CatalogScenario(
                definition=definition,
                path=path,
                config=application.load_scenario(path),
            )

    def list(self) -> tuple[CatalogScenario, ...]:
        return tuple(self._items.values())

    def get(self, scenario_id: str) -> CatalogScenario | None:
        return self._items.get(scenario_id)
