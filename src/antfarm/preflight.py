"""Runtime availability checks shared by outer application clients."""

from antfarm.adapters.models.ollama import OllamaModelPreflight
from antfarm.config.schema import OpenAICompatibleProviderConfig, ScenarioConfig


async def preflight_ollama(
    config: ScenarioConfig,
    *,
    checker_factory: type[OllamaModelPreflight] = OllamaModelPreflight,
) -> None:
    """Verify active Ollama model assignments before durable run creation."""

    grouped: dict[str, set[str]] = {}
    for agent in config.active_agents():
        model = config.models[agent.model_ref]
        provider = config.providers[model.provider_ref]
        if (
            isinstance(provider, OpenAICompatibleProviderConfig)
            and provider.runtime == "ollama"
        ):
            grouped.setdefault(model.provider_ref, set()).add(model.model)
    for provider_ref in sorted(grouped):
        provider = config.providers[provider_ref]
        if not isinstance(provider, OpenAICompatibleProviderConfig):
            raise TypeError("Ollama preflight requires an OpenAI-compatible provider")
        await checker_factory(base_url=provider.base_url).ensure_available(
            sorted(grouped[provider_ref])
        )
