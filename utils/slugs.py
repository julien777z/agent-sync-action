import re
from pathlib import Path
from typing import Final

SAFE_SLUG_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
NUMBERED_COPY_PATTERN: Final[re.Pattern[str]] = re.compile(r" \d+$")


def validate_slug(slug: str, source_path: Path) -> str:
    """Return the slug when it matches the safe pattern, else raise ValueError."""

    if not SAFE_SLUG_PATTERN.match(slug):
        raise ValueError(f"Invalid slug '{slug}' from {source_path}")

    return slug


def slug_to_codex_name(slug: str) -> str:
    """Normalize a slug into a codex-safe skill directory name."""

    normalized = re.sub(r"[^a-zA-Z0-9]+", "-", slug).strip("-").lower()

    return normalized or slug
