import logging
from typing import NotRequired, Self, TypedDict

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    field_validator,
    model_validator,
)

logger = logging.getLogger(__name__)


class SkillFrontMatter(BaseModel):
    """Validate required canonical skill metadata."""

    model_config = ConfigDict(extra="allow", strict=True, populate_by_name=True)

    name: str
    description: str
    disable_model_invocation: bool = Field(
        default=False,
        alias="disable-model-invocation",
        exclude_if=lambda value: not value,
    )
    metadata: dict[str, JsonValue] | None = None

    @field_validator("name", "description")
    @classmethod
    def validate_nonempty_metadata(cls, value: str) -> str:
        """Reject canonical skill metadata containing only whitespace."""

        if not value.strip():
            raise ValueError("Skill metadata must not be empty")

        return value


class SkillMetadataUpdate(TypedDict):
    """Type the metadata patch applied to a vendored skill document."""

    name: str
    metadata: dict[str, JsonValue]
    short_description: NotRequired[str]


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
    paths: str | list[str] | None = None
    always_apply: bool = Field(default=True, alias="alwaysApply")
    starlark: str | None = None

    @model_validator(mode="after")
    def validate_matching_scopes(self) -> Self:
        """Reject differing Claude and Cursor scopes."""

        if self.globs is not None and self.paths is not None:
            globs = [self.globs] if isinstance(self.globs, str) else self.globs
            paths = [self.paths] if isinstance(self.paths, str) else self.paths
            if globs != paths:
                raise ValueError("globs and paths must describe the same patterns")

        return self

    @property
    def scope_patterns(self) -> list[str]:
        """Return the file patterns this rule is scoped to."""

        scope = self.globs if self.globs is not None else self.paths
        if scope is None:
            return []

        return [scope] if isinstance(scope, str) else scope
