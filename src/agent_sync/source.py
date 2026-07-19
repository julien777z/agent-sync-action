import json
from pathlib import Path

from pydantic import BaseModel, ValidationError

from agent_sync.configuration import (
    AgentModelOverride,
    CanonicalConfiguration,
    CodexSettings,
    PlatformSettings,
)
from agent_sync.errors import AgentSyncError
from agent_sync.models.output import Provider
from agent_sync.slug import validate_slug
from agent_sync.workspace import Workspace


def load_json_model[T: BaseModel](
    workspace: Workspace,
    path: Path,
    model: type[T],
) -> T | None:
    """Load a typed JSON source when it exists."""

    raw = workspace.read_text(path)
    if raw is None:
        return None

    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise AgentSyncError(f"Invalid JSON in {path}: {exc}") from exc

    try:
        return model.model_validate(value)
    except ValidationError as exc:
        raise AgentSyncError(f"Invalid canonical source at {path}: {exc}") from exc


def load_configuration(workspace: Workspace) -> CanonicalConfiguration:
    """Load all provider settings and agent model overrides."""

    settings: dict[Provider, PlatformSettings | CodexSettings] = {}
    if workspace.settings_dir.exists():
        for path in sorted(workspace.settings_dir.glob("*.json")):
            try:
                provider = Provider(path.stem)
            except ValueError as exc:
                raise AgentSyncError(f"Unsupported provider settings file: {path}") from exc

            model = CodexSettings if provider is Provider.CODEX else PlatformSettings
            loaded = load_json_model(workspace, path, model)
            if loaded is not None:
                settings[provider] = loaded

    overrides: dict[str, AgentModelOverride] = {}
    if workspace.models_dir.exists():
        for path in sorted(workspace.models_dir.glob("*.json")):
            slug = validate_slug(path.stem, path)
            loaded = load_json_model(workspace, path, AgentModelOverride)
            if loaded is not None:
                overrides[slug] = loaded

    return CanonicalConfiguration(settings=settings, model_overrides=overrides)


def resolve_agent_model(
    agent_slug: str,
    provider: Provider,
    configuration: CanonicalConfiguration,
) -> str | None:
    """Resolve a per-agent override before the provider default model."""

    override = configuration.model_overrides.get(agent_slug)
    resolved_override = override.for_provider(provider) if override is not None else None
    provider_settings = configuration.settings.get(provider)
    default = provider_settings.model if provider_settings is not None else None

    return resolved_override or default
