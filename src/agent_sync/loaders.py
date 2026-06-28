import json
import logging
from pathlib import Path

import yaml
from pydantic import BaseModel, ValidationError

from agent_sync.models.front_matter import AgentModelOverride, PlatformSettings
from agent_sync.utils import fs
from agent_sync.utils.markdown import nonempty_str, normalize_text
from agent_sync.utils.slugs import validate_slug

logger = logging.getLogger(__name__)


def settings_dir() -> Path:
    """Return the .agents/settings directory under the configured root."""

    return fs.agents_dir() / "settings"


def models_dir() -> Path:
    """Return the .agents/models directory under the configured root."""

    return fs.agents_dir() / "models"


def validate_front_matter(data: dict, model: type[BaseModel], source: str) -> dict | None:
    """Validate front matter data against a Pydantic model, returning None on failure so callers can skip."""

    try:
        model.model_validate(data)
    except ValidationError as exc:
        logger.warning("Invalid front matter in %s: %s", source, exc)

        return None

    return data


def load_json_object(path: Path, model: type[BaseModel]) -> dict | None:
    """Read a JSON object from path and validate it against model, warning and returning None on failure."""

    raw = fs.read_text(path)
    if raw is None:
        return None

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.warning("Invalid JSON in %s: %s", path, exc)

        return None

    if not isinstance(data, dict):
        logger.warning("%s is not a JSON object; ignoring.", path)

        return None

    return validate_front_matter(data, model, str(path))


def load_platform_settings() -> dict[str, dict]:
    """Load each .agents/settings/<platform>.json, validating its top-level shape."""

    settings: dict[str, dict] = {}
    if not settings_dir().exists():
        return settings

    for path in sorted(settings_dir().glob("*.json")):
        data = load_json_object(path, PlatformSettings)
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


def parse_markdown_file(path: Path, model: type[BaseModel] | None = None) -> tuple[dict, str]:
    """Parse markdown front matter and body content."""

    content = fs.read_text(path)
    if content is None:
        return {}, ""

    front_matter: dict = {}
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
    platform_settings: dict[str, dict],
    agent_model_overrides: dict[str, dict[str, str]],
) -> str | None:
    """Pick the per-agent override for this platform; fall back to the platform-wide default."""

    override = agent_model_overrides.get(agent_slug, {}).get(platform)
    default = platform_settings.get(platform, {}).get("model")

    return nonempty_str(override) or nonempty_str(default)
