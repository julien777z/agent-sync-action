from pydantic import BaseModel, ConfigDict, Field


class PlatformSettings(BaseModel):
    """Top-level shape of a .agents/settings/<platform>.json file."""

    model_config = ConfigDict(extra="allow", strict=True)

    model: str | None = None


class AgentModelOverride(BaseModel):
    """Per-platform model overrides for a single agent."""

    model_config = ConfigDict(extra="forbid", strict=True)

    claude: str | None = None
    cursor: str | None = None
    codex: str | None = None


class SkillFrontMatter(BaseModel):
    """Recognized front matter keys on a skill SKILL.md."""

    model_config = ConfigDict(extra="allow", strict=True)

    name: str | None = None
    description: str | None = None


class CommandFrontMatter(BaseModel):
    """Recognized front matter keys on a command markdown file."""

    model_config = ConfigDict(extra="allow", strict=True, populate_by_name=True)

    allowed_tools: str | None = Field(default=None, alias="allowed-tools")
    variants: dict[str, str] | None = None


class AgentFrontMatter(BaseModel):
    """Recognized front matter keys on an agent markdown file."""

    model_config = ConfigDict(extra="allow", strict=True)

    name: str | None = None
    description: str | None = None
    tools: str | None = None
    model: str | None = None


class RuleFrontMatter(BaseModel):
    """Recognized front matter keys on a rule markdown file."""

    model_config = ConfigDict(extra="allow", strict=True, populate_by_name=True)

    description: str | None = None
    globs: str | list[str] | None = None
    always_apply: bool = Field(default=True, alias="alwaysApply")
    starlark: str | None = None
