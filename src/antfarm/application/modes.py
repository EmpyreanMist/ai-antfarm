"""Closed built-in game-mode registry and transport-neutral discovery views."""

from __future__ import annotations

from dataclasses import dataclass

from antfarm.application.contracts import (
    ApplicationError,
    ErrorCode,
    ModeView,
    ScenarioTemplateView,
)


@dataclass(frozen=True, slots=True)
class ModeTemplateDefinition:
    view: ScenarioTemplateView
    source: str


@dataclass(frozen=True, slots=True)
class BuiltInModeDefinition:
    view: ModeView
    templates: tuple[ModeTemplateDefinition, ...]


SOCIETY_TEMPLATES = (
    ModeTemplateDefinition(
        ScenarioTemplateView(
            "live-society-mock",
            "Live Society · Mock",
            "A deterministic ten-person commons with speech and actions.",
            "mock",
            True,
        ),
        "live-social-mock.yaml",
    ),
    ModeTemplateDefinition(
        ScenarioTemplateView(
            "society-manual",
            "Authored Society",
            "Two richly configured agents with visible inequality.",
            "mock",
        ),
        "society-manual.yaml",
    ),
    ModeTemplateDefinition(
        ScenarioTemplateView(
            "society-randomized",
            "Generated Society",
            "A seeded population generated from trait and economic ranges.",
            "mock",
        ),
        "society-randomized.yaml",
    ),
    ModeTemplateDefinition(
        ScenarioTemplateView(
            "society-mixed",
            "Mixed Society",
            "Authored and generated agents resolved into one population.",
            "mock",
        ),
        "society-mixed.yaml",
    ),
    ModeTemplateDefinition(
        ScenarioTemplateView(
            "live-society-ollama",
            "Live Society · Ollama",
            "The interactive Society scenario backed by a local model.",
            "ollama",
        ),
        "live-social-ollama.yaml",
    ),
)


SOCIETY_MODE = BuiltInModeDefinition(
    view=ModeView(
        id="society",
        name="Society",
        description=(
            "Agents communicate and act in a shared commons with optional rich "
            "profiles, economic state, and visibility boundaries."
        ),
        capabilities=(
            "agents",
            "cognition",
            "commons",
            "economics",
            "profiles",
            "public_speech",
            "relationships",
            "reputation",
        ),
        configuration_hints={
            "runtime_options": (
                "seed",
                "active_agents",
                "run_id",
                "model",
                "model_assignments",
                "population",
                "profiles",
                "run_mode",
                "tick_seconds",
            ),
            "optional_profile_sections": (
                "identity",
                "personality",
                "goals",
                "beliefs",
                "values",
                "communication",
                "traits",
                "economics",
                "social_status",
                "reputation",
                "relationships",
                "private",
                "visibility",
            ),
        },
        visualization_hints={
            "primary": "activity_feed",
            "inspectors": ("agents", "world_state", "metrics"),
            "optional": ("relationships", "economics"),
        },
        templates=tuple(template.view for template in SOCIETY_TEMPLATES),
    ),
    templates=SOCIETY_TEMPLATES,
)

BUILT_IN_MODES = (SOCIETY_MODE,)


class BuiltInModeRegistry:
    """Explicit built-in registry; no imports or third-party discovery."""

    def __init__(
        self, definitions: tuple[BuiltInModeDefinition, ...] = BUILT_IN_MODES
    ) -> None:
        self._definitions = {
            definition.view.id: definition for definition in definitions
        }

    def list(self) -> tuple[ModeView, ...]:
        return tuple(definition.view for definition in self._definitions.values())

    def get(self, mode_id: str) -> ModeView:
        return self._require(mode_id).view

    def template_source(self, mode_id: str, template_id: str) -> str:
        definition = self._require(mode_id)
        for template in definition.templates:
            if template.view.id == template_id:
                return template.source
        raise ApplicationError(
            ErrorCode.NOT_FOUND,
            f"scenario template was not found: {template_id}",
            details={"mode_id": mode_id, "template_id": template_id},
        )

    def _require(self, mode_id: str) -> BuiltInModeDefinition:
        try:
            return self._definitions[mode_id]
        except KeyError as error:
            raise ApplicationError(
                ErrorCode.NOT_FOUND,
                f"game mode was not found: {mode_id}",
                details={"mode_id": mode_id},
            ) from error
