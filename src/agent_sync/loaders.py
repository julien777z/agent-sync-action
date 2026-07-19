import json
import logging
from pathlib import Path

import yaml
from pydantic import BaseModel, ValidationError

from agent_sync.models.front_matter import AgentModelOverride, CodexSettings, PlatformSettings
from agent_sync.models.json_types import JsonObject, JsonValue
from agent_sync.models.mcp import McpConfig
from agent_sync.utils import fs
from agent_sync.utils.markdown import nonempty_str, normalize_text
from agent_sync.utils.slugs import validate_slug

logger = logging.getLogger(__name__)


class McpConfigError(ValueError):
    """Raised when .agents/mcp.json cannot be parsed or validated safely."""


def settings_dir() -> Path:
    """Return the .agents/settings directory under the configured root."""

    return fs.agents_dir() / "settings"


def models_dir() -> Path:
    """Return the .agents/models directory under the configured root."""

    return fs.agents_dir() / "models"


def validate_front_matter(
    data: JsonObject,
    model: type[BaseModel],
    source: str,
) -> JsonObject | None:
    """Validate front matter, returning None on failure so callers can skip it."""

    try:
        model.model_validate(data)
    except ValidationError as exc:
        logger.warning("Invalid front matter in %s: %s", source, exc)

        return None

    return data


def load_json_value(path: Path) -> JsonValue | None:
    """Read and decode a JSON file, returning None when it is absent."""

    raw = fs.read_text(path)
    if raw is None:
        return None

    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {path}: {exc}") from exc


def load_json_object(path: Path, model: type[BaseModel]) -> JsonObject | None:
    """Read and validate a JSON object, returning None when absent or invalid."""

    try:
        data = load_json_value(path)
    except ValueError as exc:
        logger.warning("%s", exc)

        return None

    if data is None:
        return None

    if not isinstance(data, dict):
        logger.warning("%s is not a JSON object; ignoring.", path)

        return None

    return validate_front_matter(data, model, str(path))


def load_platform_settings() -> dict[str, JsonObject]:
    """Load each .agents/settings/<platform>.json, validating its top-level shape."""

    settings: dict[str, JsonObject] = {}
    if not settings_dir().exists():
        return settings

    for path in sorted(settings_dir().glob("*.json")):
        model = CodexSettings if path.stem == "codex" else PlatformSettings
        data = load_json_object(path, model)
        if data is not None:
            settings[path.stem] = data

    return settings


def load_agent_model_overrides() -> dict[str, dict[str, str]]:
    """Load each .agents/models/<agent-slug>.json mapping agent slug to per-platform model."""

    overrides: dict[str, dict[str, str]] = {}
    if not models_dir().exists():
        return overrides

    for path in sorted(models_dir().glob("*.json")):
        slug = validate_slug(path.stem, path)
        data = load_json_object(path, AgentModelOverride)
        if data is not None:
            overrides[slug] = {k: v for k, v in data.items() if isinstance(v, str) and v}

    return overrides


def load_mcp_config() -> McpConfig | None:
    """Load strict canonical MCP configuration, or return None when the source is absent."""

    path = fs.agents_dir() / "mcp.json"
    raw = fs.read_text(path)
    if raw is None:
        return None

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise McpConfigError(f"Invalid JSON in {path}: {exc}") from exc

    if not isinstance(data, dict):
        raise McpConfigError(f"{path} must contain a JSON object")

    try:
        return McpConfig.model_validate(data)
    except ValidationError as exc:
        raise McpConfigError(f"Invalid MCP configuration in {path}: {exc}") from exc


def parse_markdown_file(
    path: Path,
    model: type[BaseModel] | None = None,
) -> tuple[JsonObject, str]:
    """Parse markdown front matter and body content."""

    content = fs.read_text(path)
    if content is None:
        return {}, ""

    front_matter: JsonObject = {}
    body = content

    lines = content.splitlines()
    if lines and lines[0] == "---":
        end_index = -1
        for index, line in enumerate(lines[1:], start=1):
            if line == "---":
                end_index = index
                break

        if end_index == -1:
            logger.warning("Unterminated front matter in %s.", path)
        else:
            front_matter_content = "\n".join(lines[1:end_index]).strip()
            body = "\n".join(lines[end_index + 1 :])
            if front_matter_content:
                raw_data = yaml.safe_load(front_matter_content) or {}
                if not isinstance(raw_data, dict):
                    logger.warning("Invalid front matter in %s.", path)
                elif model is None:
                    front_matter = raw_data
                else:
                    front_matter = validate_front_matter(raw_data, model, str(path)) or {}

    return front_matter, normalize_text(body)


def resolve_agent_model(
    agent_slug: str,
    platform: str,
    platform_settings: dict[str, JsonObject],
    agent_model_overrides: dict[str, dict[str, str]],
) -> str | None:
    """Pick the per-agent override for this platform; fall back to the platform-wide default."""

    override = agent_model_overrides.get(agent_slug, {}).get(platform)
    default = platform_settings.get(platform, {}).get("model")

    return nonempty_str(override) or nonempty_str(default)
