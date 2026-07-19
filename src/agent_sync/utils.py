import json
import re
from pathlib import Path
from typing import Final

from pydantic import BaseModel, ValidationError

from agent_sync.errors import AgentSyncError
from agent_sync.workspace import Workspace

SAFE_SLUG_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[a-z0-9][a-z0-9_-]*$")


def load_json_model[T: BaseModel](
    workspace: Workspace,
    path: Path,
    model: type[T],
) -> T | None:
    """Load and validate a typed JSON file when it exists."""

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
        raise AgentSyncError(f"Invalid source at {path}: {exc}") from exc


def validate_slug(slug: str, source_path: Path) -> str:
    """Return a safe canonical slug or reject the source path."""

    if not SAFE_SLUG_PATTERN.fullmatch(slug):
        raise AgentSyncError(f"Invalid slug '{slug}' from {source_path}")

    return slug
