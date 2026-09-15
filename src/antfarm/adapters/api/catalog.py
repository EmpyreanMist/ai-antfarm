"""Server-owned loading of application-registered scenario templates."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from antfarm.application.contracts import ModeView, ScenarioTemplateView
from antfarm.config.schema import ScenarioConfig, SqliteStorageConfig
from antfarm.facade import AntFarmApplication


@dataclass(frozen=True, slots=True)
class CatalogScenario:
    mode: ModeView
    template: ScenarioTemplateView
    path: Path
    config: ScenarioConfig

    def view(self) -> dict[str, object]:
        agents = self.config.expand_agents()
        return {
            "id": self.template.id,
            "mode": self.mode.id,
            "name": self.template.name,
            "description": self.template.description,
            "runtime": self.template.runtime,
            "featured": self.template.featured,
            "agent_count": len(agents),
            "default_active_agents": self.config.run.active_agents or len(agents),
            "seed": self.config.run.seed,
            "ticks": self.config.run.ticks,
            "environment": self.config.environment.kind,
            "models": sorted(model.model for model in self.config.models.values()),
            "durable": isinstance(self.config.storage, SqliteStorageConfig),
        }


class ScenarioCatalog:
    """Loaded templates from the closed application mode registry."""

    def __init__(
        self,
        scenario_directory: Path,
        application: AntFarmApplication,
    ) -> None:
        self._items: dict[str, CatalogScenario] = {}
        root = scenario_directory.resolve()
        for mode in application.list_modes():
            for template in mode.templates:
                source = application.mode_template_source(mode.id, template.id)
                path = (root / source).resolve()
                if path.parent != root or not path.is_file():
                    continue
                self._items[template.id] = CatalogScenario(
                    mode=mode,
                    template=template,
                    path=path,
                    config=application.load_scenario(path),
                )

    def list(self, mode_id: str | None = None) -> tuple[CatalogScenario, ...]:
        return tuple(
            item
            for item in self._items.values()
            if mode_id is None or item.mode.id == mode_id
        )

    def get(self, scenario_id: str) -> CatalogScenario | None:
        return self._items.get(scenario_id)
