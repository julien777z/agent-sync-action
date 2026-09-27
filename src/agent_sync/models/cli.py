from typing import Literal

from pydantic import BaseModel, ConfigDict


class CliArguments(BaseModel):
    """Validate parsed command-line arguments before dispatch."""

    model_config = ConfigDict(extra="forbid", strict=True)

    command: Literal["mirror-providers", "vendor-resources"]
    root: str | None
    agents_dir: str | None
    output_dir: str | None = None
    dry_run: bool
