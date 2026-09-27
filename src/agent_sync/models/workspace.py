from pathlib import Path
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from agent_sync.utils import escapes_base_directory


class CliArguments(BaseModel):
    """Validate parsed command-line arguments before dispatch."""

    model_config = ConfigDict(extra="forbid", strict=True)

    command: Literal["mirror-providers", "vendor-resources"]
    root: str | None
    agents_dir: str | None
    output_dir: str | None = None
    dry_run: bool


class Workspace(BaseModel):
    """Describe one repository and its canonical agent source directory."""

    model_config = ConfigDict(frozen=True)

    root: Path = Field(default_factory=Path.cwd)
    agents_dirname: str = ".agents"
    output_dirname: str = ""

    @field_validator("output_dirname")
    @classmethod
    def validate_output_dirname(cls, value: str) -> str:
        """Require generated provider trees to stay inside the repository."""

        if escapes_base_directory(Path(value)):
            raise ValueError("Generated output directory must be a relative path inside the repository")

        return value

    @model_validator(mode="after")
    def validate_output_avoids_read_sources(self) -> Self:
        """Require generated provider trees to sit outside every directory the run reads."""

        if not self.output_dirname:
            return self

        output = Path(self.output_dirname)
        enclosing = {output, *output.parents}
        source_names = ("skills", "agents", "rules", "hooks", "settings", "models", "resources")

        if enclosing & {Path(self.agents_dirname) / name for name in source_names}:
            raise ValueError("Generated output directory must sit outside the directories a run reads")

        return self
