from pathlib import Path

from pydantic import BaseModel, ConfigDict, field_validator


class ExplicitSkillInvocationPolicy(BaseModel):
    """Describe one provider's generated explicit-invocation policy."""

    model_config = ConfigDict(frozen=True)

    relative_path: Path
    content: str

    @field_validator("relative_path")
    @classmethod
    def validate_relative_path(cls, value: Path) -> Path:
        """Require generated metadata to live below the skill root."""

        if value.is_absolute() or ".." in value.parts or len(value.parts) < 2:
            raise ValueError("Skill invocation metadata must use a nested relative path")

        return value


class ProviderLayout(BaseModel):
    """Describe stable paths and extensions for one provider."""

    model_config = ConfigDict(frozen=True)

    directory: str
    rule_extension: str
    explicit_skill_invocation_policy: ExplicitSkillInvocationPolicy | None = None

    def root(self, repository_root: Path) -> Path:
        """Return the provider configuration root."""

        return repository_root / self.directory
