import re
from pathlib import Path
from typing import Final

from agent_sync.errors import AgentSyncError

SAFE_SLUG_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[a-z0-9][a-z0-9_-]*$")


def validate_slug(slug: str, source_path: Path) -> str:
    """Return a safe canonical slug or reject the source path."""

    if not SAFE_SLUG_PATTERN.fullmatch(slug):
        raise AgentSyncError(f"Invalid slug '{slug}' from {source_path}")

    return slug
