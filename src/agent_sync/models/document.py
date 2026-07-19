from pydantic import BaseModel, ConfigDict, Field, field_validator


class SkillFrontMatter(BaseModel):
    """Validate required canonical skill metadata."""

    model_config = ConfigDict(extra="allow", strict=True)

    name: str
    description: str

    @field_validator("name", "description")
    @classmethod
    def validate_nonempty_metadata(cls, value: str) -> str:
        """Reject canonical skill metadata containing only whitespace."""

        if not value.strip():
            raise ValueError("Skill metadata must not be empty")

        return value


class CommandFrontMatter(BaseModel):
    """Validate recognized canonical command metadata."""

    model_config = ConfigDict(extra="allow", strict=True, populate_by_name=True)

    allowed_tools: str | None = Field(default=None, alias="allowed-tools")
    variants: dict[str, str] | None = None


class AgentFrontMatter(BaseModel):
    """Validate recognized canonical agent metadata."""

    model_config = ConfigDict(extra="allow", strict=True)

    name: str | None = None
    description: str | None = None
    tools: str | None = None
    model: str | None = None


class RuleFrontMatter(BaseModel):
    """Validate recognized canonical rule metadata."""

    model_config = ConfigDict(extra="allow", strict=True, populate_by_name=True)

    description: str | None = None
    globs: str | list[str] | None = None
    always_apply: bool = Field(default=True, alias="alwaysApply")
    starlark: str | None = None
