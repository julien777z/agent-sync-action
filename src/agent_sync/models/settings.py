import json
import tomllib
from pathlib import Path
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from agent_sync.models.output import Provider
from agent_sync.utils import AgentSyncError, ensure_trailing_newline, escapes_base_directory


class PlatformSettings(BaseModel):
    """Validate provider settings whose extra keys are mirrored unchanged."""

    model_config = ConfigDict(extra="allow", strict=True)

    model: str | None = None


class CodexSettings(BaseModel):
    """Validate source settings for generated Codex project configuration."""

    model_config = ConfigDict(extra="forbid", strict=True)

    model: str | None = None
    project_doc_max_bytes: int | None = None
    features: dict[str, bool] = Field(default_factory=dict)

    def render_toml(self, notice: str) -> str:
        """Render validated Codex settings with the supplied generated-file notice."""

        lines = [f"# {notice}"]

        if self.model:
            lines.append(f"model = {json.dumps(self.model, ensure_ascii=False)}")

        if self.project_doc_max_bytes is not None:
            lines.append(f"project_doc_max_bytes = {self.project_doc_max_bytes}")

        if self.features:
            lines.append("")
            lines.append("[features]")
            lines.extend(
                f"{json.dumps(name, ensure_ascii=False)} = {json.dumps(enabled)}"
                for name, enabled in self.features.items()
            )

        rendered = ensure_trailing_newline("\n".join(lines))

        try:
            tomllib.loads(rendered)
        except tomllib.TOMLDecodeError as exc:
            raise AgentSyncError(f"Generated .codex/config.toml is invalid TOML: {exc}") from exc

        return rendered


class AgentModelOverride(BaseModel):
    """Validate supported per-provider model overrides for one agent."""

    model_config = ConfigDict(extra="forbid", strict=True)

    claude: str | None = None
    cursor: str | None = None

    def for_provider(self, provider: Provider) -> str | None:
        """Return the configured model override for a supported provider."""

        match provider:
            case Provider.CLAUDE:
                return self.claude
            case Provider.CURSOR:
                return self.cursor
            case Provider.CODEX:
                return None


class SourceConfig(BaseModel):
    """Hold all validated source settings and model overrides."""

    model_config = ConfigDict(frozen=True)

    settings: dict[Provider, PlatformSettings | CodexSettings]
    model_overrides: dict[str, AgentModelOverride]


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
