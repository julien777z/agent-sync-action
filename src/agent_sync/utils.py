import json
import re
from pathlib import Path
from typing import Final

from pydantic import BaseModel, ValidationError

from agent_sync.errors import AgentSyncError

SAFE_SLUG_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[a-z0-9][a-z0-9_-]*$")


def ensure_trailing_newline(text: str) -> str:
    """Return text with a trailing newline."""

    return text if text.endswith("\n") else text + "\n"


def load_json_model[T: BaseModel](
    path: Path,
    model: type[T],
) -> T | None:
    """Load and validate a typed JSON file when it exists."""

    if not path.exists():
        return None

    raw = path.read_text(encoding="utf-8")

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


def trees_differ(source: Path, destination: Path) -> bool:
    """Report whether two directory trees contain different files."""

    return snapshot_tree(source) != snapshot_tree(destination)


def snapshot_tree(directory: Path) -> dict[str, bytes]:
    """Read every file in a directory tree into a comparable snapshot."""

    if not directory.is_dir():
        return {}

    return {
        str(path.relative_to(directory)): path.read_bytes()
        for path in sorted(directory.rglob("*"))
        if path.is_file()
    }
