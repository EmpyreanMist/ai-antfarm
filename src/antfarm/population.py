"""Deterministic population and ephemeral runtime configuration resolution."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from random import Random
from typing import Literal, Protocol, cast

from antfarm.config.schema import (
    BehavioralTraitsConfig,
    BehavioralTraitsRandomizationConfig,
    OpenAICompatibleProviderConfig,
    PopulationConfig,
    ProfileRandomizationConfig,
    ScenarioConfig,
    UniformNonNegativeIntRangeConfig,
    UniformTraitRangeConfig,
)
from antfarm.domain.json_values import JsonObject, freeze_object

TemplateCategory = Literal[
    "goals",
    "beliefs",
    "personality",
    "communication_style",
    "occupation",
    "socioeconomic_background",
]


class ProfileTemplateSelector(Protocol):
    """Extension boundary for future deterministic textual template catalogs."""

    def select(
        self, category: TemplateCategory, *, agent_id: str, rng: Random
    ) -> object:
        """Return a deterministic value for a supported template category."""


@dataclass(frozen=True, slots=True)
class RuntimeOverrides:
    """Ephemeral changes applied while deriving one resolved run configuration."""

    seed: int | None = None
    run_id: str | None = None
    active_agents: int | None = None
    population: PopulationConfig | None = None
    profiles: Mapping[str, Mapping[str, object]] = field(default_factory=dict)
    model_assignments: Mapping[str, str] = field(default_factory=dict)
    model: str | None = None
    web_agents: Sequence[WebAgentDraft] | None = None
    conversation: ConversationSettings | None = None


@dataclass(frozen=True, slots=True)
class WebAgentDraft:
    """Editable browser agent normalized into the ordinary profile schema."""

    id: str
    profile: Mapping[str, object]
    model: str | None = None
    cognition_interval: int | None = None


@dataclass(frozen=True, slots=True)
class ConversationSettings:
    """Bounded social-sandbox choices applied to an ordinary Society scenario."""

    topic: str
    situation: str
    turns: int = 12
    memory_limit: int = 20

    def __post_init__(self) -> None:
        if not self.topic.strip() or not self.situation.strip():
            raise ValueError("conversation topic and situation must not be empty")
        if not 1 <= self.turns <= 100:
            raise ValueError("conversation turns must be between 1 and 100")
        if not 1 <= self.memory_limit <= 100:
            raise ValueError("conversation memory limit must be between 1 and 100")


def runtime_overrides_data(overrides: RuntimeOverrides | None) -> JsonObject:
    """Return durable, JSON-compatible provenance for explicit runtime choices."""

    if overrides is None:
        return freeze_object({})
    data: dict[str, object] = {}
    for name in ("seed", "run_id", "active_agents", "model"):
        value = getattr(overrides, name)
        if value is not None:
            data[name] = value
    if overrides.population is not None:
        data["population"] = overrides.population.model_dump(
            mode="json", exclude_none=True
        )
    if overrides.profiles:
        data["profiles"] = {
            agent_id: dict(profile)
            for agent_id, profile in sorted(overrides.profiles.items())
        }
    if overrides.model_assignments:
        data["model_assignments"] = dict(sorted(overrides.model_assignments.items()))
    if overrides.web_agents is not None:
        data["web_agents"] = tuple(
            {
                "id": agent.id,
                **({"model": agent.model} if agent.model is not None else {}),
            }
            for agent in overrides.web_agents
        )
    if overrides.conversation is not None:
        data["conversation"] = {
            "topic": overrides.conversation.topic,
            "situation": overrides.conversation.situation,
            "turns": overrides.conversation.turns,
            "memory_limit": overrides.conversation.memory_limit,
        }
    return freeze_object(data)


def resolve_run_config(
    source: ScenarioConfig,
    overrides: RuntimeOverrides | None = None,
    *,
    template_selector: ProfileTemplateSelector | None = None,
) -> ScenarioConfig:
    """Return a fully materialized, validated config without mutating ``source``.

    Numeric generation is deliberately local and uniform. ``template_selector`` is
    reserved for deterministic textual catalogs; no template category is required
    by the current numeric-only schema.
    """

    del template_selector
    requested = overrides or RuntimeOverrides()
    data = source.model_dump(mode="json", exclude_none=True)
    if requested.web_agents is not None:
        _apply_web_agents(data, source, requested.web_agents)
    if requested.conversation is not None:
        _apply_conversation(data, requested.conversation)
    if requested.population is not None:
        data["population"] = requested.population.model_dump(
            mode="json", exclude_none=True
        )

    run = cast(dict[str, object], data["run"])
    if requested.seed is not None:
        run["seed"] = requested.seed
    if requested.run_id is not None:
        run["id"] = requested.run_id
    if requested.active_agents is not None:
        run["active_agents"] = requested.active_agents

    provisional = ScenarioConfig.model_validate(data)
    population = provisional.population
    generation_seed = (
        requested.seed
        if requested.seed is not None
        else population.seed
        if population is not None and population.seed is not None
        else provisional.run.seed
    )
    run["seed"] = generation_seed
    rng = Random(generation_seed)
    expanded = provisional.expand_agents()
    agent_ids = {agent.id for agent in expanded}
    _require_known_overrides("profile", requested.profiles, agent_ids)
    _require_known_overrides("model", requested.model_assignments, agent_ids)

    profiles = cast(dict[str, dict[str, object]], data.get("profiles", {}))
    resolved_agents: list[dict[str, object]] = []
    for agent in expanded:
        randomization = _randomization_for(agent.id, agent.pool_ref, population)
        profile_patch = requested.profiles.get(agent.id)
        needs_profile = randomization is not None or profile_patch is not None
        profile_ref = agent.profile_ref
        personality_ref = agent.personality_ref
        if needs_profile:
            if personality_ref is not None:
                raise ValueError(
                    f"agent {agent.id!r} cannot randomize or override a profile "
                    "while using a legacy personality"
                )
            generated_profile = (
                _generate_profile(randomization, rng)
                if randomization is not None
                else {}
            )
            if profile_ref is not None:
                generated_profile = _deep_merge(
                    generated_profile, profiles[profile_ref]
                )
            if profile_patch is not None:
                generated_profile = _deep_merge(generated_profile, dict(profile_patch))
            profile_ref = f"resolved-{agent.id}"
            if profile_ref in profiles and profile_ref != agent.profile_ref:
                raise ValueError(
                    f"generated profile identifier {profile_ref!r} conflicts with "
                    "an explicit profile"
                )
            profiles[profile_ref] = generated_profile

        model_ref = requested.model_assignments.get(agent.id, agent.model_ref)
        resolved: dict[str, object] = {
            "id": agent.id,
            "model_ref": model_ref,
        }
        if personality_ref is not None:
            resolved["personality_ref"] = personality_ref
        if profile_ref is not None:
            resolved["profile_ref"] = profile_ref
        if agent.cognition_interval is not None:
            resolved["cognition_interval"] = agent.cognition_interval
        resolved_agents.append(resolved)

    data["profiles"] = profiles
    data["agents"] = resolved_agents
    data["agent_pools"] = []
    data.pop("population", None)
    resolved_config = ScenarioConfig.model_validate(data)

    if requested.model is not None:
        _validate_runtime_model(requested.model)
        data = resolved_config.model_dump(mode="json", exclude_none=True)
        models = cast(dict[str, dict[str, object]], data["models"])
        for model_ref in sorted(
            {agent.model_ref for agent in resolved_config.active_agents()}
        ):
            model_config = resolved_config.models[model_ref]
            provider = resolved_config.providers[model_config.provider_ref]
            if not isinstance(provider, OpenAICompatibleProviderConfig):
                raise ValueError(
                    "runtime model override requires OpenAI-compatible active "
                    f"models; {model_ref!r} uses {provider.kind!r}"
                )
            models[model_ref]["model"] = requested.model
        resolved_config = ScenarioConfig.model_validate(data)
    return resolved_config


def _apply_conversation(
    data: dict[str, object], settings: ConversationSettings
) -> None:
    environment = cast(dict[str, object], data["environment"])
    social = environment.get("social")
    if environment.get("kind") != "commons" or not isinstance(social, dict):
        raise ValueError("conversation requires a social commons scenario")
    social["topic"] = settings.topic.strip()
    social["situation"] = settings.situation.strip()
    social["history_limit"] = settings.memory_limit
    data["actions"] = [{"kind": "say"}]
    run = cast(dict[str, object], data["run"])
    run["ticks"] = settings.turns
    memory = cast(dict[str, object], data["memory"])
    memory["recall_limit"] = settings.memory_limit
    memory["retention_limit"] = max(settings.memory_limit, settings.turns)
    scheduling = cast(dict[str, object], data["scheduling"])
    scheduling.update(
        interval=1,
        stagger=True,
        max_cognitions_per_tick=1,
        event_kinds=[],
    )
    agents = cast(list[dict[str, object]], data["agents"])
    for agent in agents:
        agent["cognition_interval"] = 1


def _apply_web_agents(
    data: dict[str, object],
    source: ScenarioConfig,
    drafts: Sequence[WebAgentDraft],
) -> None:
    if not 1 <= len(drafts) <= 10:
        raise ValueError("web population must contain between 1 and 10 agents")
    ids = [draft.id for draft in drafts]
    if len(set(ids)) != len(ids):
        raise ValueError("web population agent identifiers must be unique")
    templates = source.expand_agents()
    if not templates:
        raise ValueError("source scenario has no agent template")
    profiles = cast(dict[str, object], data.setdefault("profiles", {}))
    models = cast(dict[str, dict[str, object]], data["models"])
    generated_models: dict[tuple[str, str], str] = {}
    agents: list[dict[str, object]] = []
    for index, draft in enumerate(drafts):
        template = templates[index % len(templates)]
        profile_ref = f"web-profile-{draft.id}"
        profiles[profile_ref] = dict(draft.profile)
        model_ref = template.model_ref
        if draft.model is not None:
            _validate_runtime_model(draft.model)
            template_model = source.models[template.model_ref]
            provider = source.providers[template_model.provider_ref]
            if not isinstance(provider, OpenAICompatibleProviderConfig):
                raise ValueError(
                    "installed model assignment requires an OpenAI-compatible scenario"
                )
            key = (template.model_ref, draft.model)
            model_ref = generated_models.setdefault(
                key, f"web-model-{len(generated_models) + 1}"
            )
            if model_ref not in models:
                model_data = template_model.model_dump(mode="json", exclude_none=True)
                model_data["model"] = draft.model
                models[model_ref] = model_data
        agent: dict[str, object] = {
            "id": draft.id,
            "model_ref": model_ref,
            "profile_ref": profile_ref,
        }
        interval = draft.cognition_interval or template.cognition_interval
        if interval is not None:
            agent["cognition_interval"] = interval
        agents.append(agent)
    data["agents"] = agents
    data["agent_pools"] = []
    data.pop("population", None)
    raw_providers = data["providers"]
    if not isinstance(raw_providers, dict):
        raise TypeError("scenario providers must be an object")
    providers = cast(dict[str, object], raw_providers)
    selected_ids = set(ids)
    for raw_provider in providers.values():
        if not isinstance(raw_provider, dict):
            raise TypeError("scenario provider must be an object")
        provider_data = cast(dict[str, object], raw_provider)
        decisions = provider_data.get("decisions")
        if provider_data.get("kind") == "mock" and isinstance(decisions, dict):
            provider_data["decisions"] = {
                agent_id: value
                for agent_id, value in decisions.items()
                if agent_id in selected_ids
            }
    run = cast(dict[str, object], data["run"])
    run["active_agents"] = len(agents)


def _randomization_for(
    agent_id: str,
    pool_ref: str | None,
    population: PopulationConfig | None,
) -> ProfileRandomizationConfig | None:
    if population is None:
        return None
    parts: list[dict[str, object]] = []
    if population.randomize is not None:
        parts.append(population.randomize.model_dump(mode="json", exclude_none=True))
    generated = population.generated
    if (
        generated is not None
        and generated.id_prefix == pool_ref
        and generated.randomize is not None
    ):
        parts.append(generated.randomize.model_dump(mode="json", exclude_none=True))
    if agent_id in population.agents:
        parts.append(
            population.agents[agent_id].model_dump(mode="json", exclude_none=True)
        )
    if not parts:
        return None
    merged: dict[str, object] = {}
    for part in parts:
        merged = _deep_merge(merged, part)
    return ProfileRandomizationConfig.model_validate(merged)


def _generate_profile(
    config: ProfileRandomizationConfig, rng: Random
) -> dict[str, object]:
    profile: dict[str, object] = {}
    if config.behavioral_traits is not None:
        profile["behavioral_traits"] = _generate_traits(config.behavioral_traits, rng)
    if config.economics is not None:
        economics: dict[str, object] = {}
        if config.economics.money is not None:
            economics["money"] = _uniform_int(config.economics.money, rng)
        if config.economics.recurring_income is not None:
            economics["recurring_income"] = _uniform_int(
                config.economics.recurring_income, rng
            )
        if config.economics.resources:
            economics["resources"] = {
                name: _uniform_int(value_range, rng)
                for name, value_range in sorted(config.economics.resources.items())
            }
        profile["economics"] = economics
    return profile


def _generate_traits(
    config: BehavioralTraitsRandomizationConfig, rng: Random
) -> dict[str, float]:
    values: dict[str, float] = {}
    for name in BehavioralTraitsConfig.model_fields:
        value_range = getattr(config, name)
        if value_range is None and config.mode == "all":
            value_range = config.default
        if value_range is not None:
            values[name] = _uniform_trait(value_range, rng)
    return values


def _uniform_trait(value_range: UniformTraitRangeConfig, rng: Random) -> float:
    return rng.uniform(value_range.minimum, value_range.maximum)


def _uniform_int(value_range: UniformNonNegativeIntRangeConfig, rng: Random) -> int:
    return rng.randint(value_range.minimum, value_range.maximum)


def _deep_merge(
    defaults: dict[str, object], explicit: Mapping[str, object]
) -> dict[str, object]:
    merged = dict(defaults)
    for key, value in explicit.items():
        current = merged.get(key)
        if isinstance(current, dict) and isinstance(value, Mapping):
            merged[key] = _deep_merge(current, value)
        else:
            merged[key] = value
    return merged


def _require_known_overrides(
    kind: str, overrides: Mapping[str, object], agent_ids: set[str]
) -> None:
    unknown = set(overrides).difference(agent_ids)
    if unknown:
        names = ", ".join(sorted(unknown))
        raise ValueError(f"runtime {kind} overrides reference unknown agents: {names}")


def _validate_runtime_model(model: str) -> None:
    if not model or model != model.strip():
        raise ValueError("runtime model must be a non-empty trimmed value")
    if any(ord(character) < 32 or 127 <= ord(character) <= 159 for character in model):
        raise ValueError("runtime model must not contain control characters")
