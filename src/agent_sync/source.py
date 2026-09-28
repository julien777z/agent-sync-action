from agent_sync.models.output import Provider
from agent_sync.models.settings import (
    AgentModelOverride,
    CodexSettings,
    PlatformSettings,
    SourceConfig,
    Workspace,
)
from agent_sync.utils import AgentSyncError, load_json_model, validate_slug
from agent_sync.workspace import models_dir, settings_dir


def load_source_config(workspace: Workspace) -> SourceConfig:
    """Load all provider settings and agent model overrides."""

    settings: dict[Provider, PlatformSettings | CodexSettings] = {}

    if settings_dir(workspace).exists():
        for path in sorted(settings_dir(workspace).glob("*.json")):
            try:
                provider = Provider(path.stem)
            except ValueError as exc:
                raise AgentSyncError(f"Unsupported provider settings file: {path}") from exc

            model = CodexSettings if provider is Provider.CODEX else PlatformSettings
            loaded = load_json_model(path, model)

            if loaded is not None:
                settings[provider] = loaded

    overrides: dict[str, AgentModelOverride] = {}

    if models_dir(workspace).exists():
        for path in sorted(models_dir(workspace).glob("*.json")):
            slug = validate_slug(path.stem, path)
            loaded = load_json_model(path, AgentModelOverride)

            if loaded is not None:
                overrides[slug] = loaded

    return SourceConfig(settings=settings, model_overrides=overrides)


def resolve_agent_model(
    agent_slug: str,
    provider: Provider,
    source_config: SourceConfig,
) -> str | None:
    """Resolve a per-agent override before the provider default model."""

    override = source_config.model_overrides.get(agent_slug)
    resolved_override = override.for_provider(provider) if override is not None else None
    provider_settings = source_config.settings.get(provider)
    default = provider_settings.model if provider_settings is not None else None

    return resolved_override or default
