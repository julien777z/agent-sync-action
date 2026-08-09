import logging

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, computed_field, field_validator

logger = logging.getLogger(__name__)


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
    globs: str | list[str] | None = Field(
        default=None, validation_alias=AliasChoices("globs", "paths")
    )
    always_apply: bool = Field(default=True, alias="alwaysApply")
    starlark: str | None = None

    @computed_field
    @property
    def paths(self) -> str | list[str] | None:
        """Mirror the file scope under the key the other providers read."""

        return self.globs

    @property
    def scope_patterns(self) -> list[str]:
        """Return the file patterns this rule is scoped to."""

        if self.globs is None:
            return []

        return [self.globs] if isinstance(self.globs, str) else self.globs
