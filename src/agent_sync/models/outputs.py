from pathlib import Path

from pydantic import BaseModel, ConfigDict


class OutputFile(BaseModel):
    """A generated mirror file destined for a Claude/Cursor/Codex path."""

    model_config = ConfigDict(frozen=True)

    target_path: Path
    content: str
    kind: str
    slug: str
    source_path: Path | None


class DiffEntry(BaseModel):
    """A generated output paired with its current on-disk content."""

    model_config = ConfigDict(frozen=True)

    output: OutputFile
    existing: str | None
