import logging

from pydantic import BaseModel, ConfigDict, Field, field_validator

from agent_sync.config import ACTION_CONFIG
from agent_sync.utils import SAFE_RELATIVE_PATH_PATTERN, SAFE_SLUG_PATTERN

logger = logging.getLogger(__name__)


class VendoredSkill(BaseModel):
    """A single skills.sh skill to vendor into .agents/skills/<name>/."""

    model_config = ConfigDict(extra="forbid", strict=True)

    name: str
    repo: str
    skill: str | None = None
    skills_path: str | None = None
    update_on_sync: bool

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        """Reject names that would not be a safe skill directory slug."""

        if not SAFE_SLUG_PATTERN.fullmatch(value):
            raise ValueError(f"Invalid skill name '{value}' (must match {SAFE_SLUG_PATTERN.pattern})")

        return value

    @field_validator("skill")
    @classmethod
    def validate_skill(cls, value: str | None) -> str | None:
        """Reject upstream skill selectors that are not safe slugs."""

        if value is not None and not SAFE_SLUG_PATTERN.fullmatch(value):
            raise ValueError(f"Invalid upstream skill '{value}' (must match {SAFE_SLUG_PATTERN.pattern})")

        return value

    @field_validator("skills_path")
    @classmethod
    def validate_skills_path(cls, value: str | None) -> str | None:
        """Reject upstream skill directories that are not safe relative paths."""

        if value is not None and not SAFE_RELATIVE_PATH_PATTERN.fullmatch(value):
            raise ValueError(
                f"Invalid skills path '{value}' (must match {SAFE_RELATIVE_PATH_PATTERN.pattern})"
            )

        return value

    @property
    def upstream_skill(self) -> str:
        """Return the skill slug to request from the source repo (defaults to the local name)."""

        return self.skill or self.name


class SkillsCliVendor(BaseModel):
    """Skills installed from their source repositories through the skills.sh CLI."""

    model_config = ConfigDict(extra="forbid", strict=True)

    update_on_sync: bool = True
    cli_version: str = Field(default_factory=lambda: ACTION_CONFIG.skills_cli_version)
    skills: list[VendoredSkill] = Field(default_factory=list[VendoredSkill])

    @field_validator("skills")
    @classmethod
    def validate_unique_names(cls, value: list[VendoredSkill]) -> list[VendoredSkill]:
        """Reject entries that would write to the same local skill directory."""

        names = [skill.name for skill in value]
        duplicates = sorted({name for name in names if names.count(name) > 1})

        if duplicates:
            raise ValueError(f"Vendored skill names must be unique: {', '.join(duplicates)}")

        return value


class VendoredSkillResult(BaseModel):
    """The outcome of updating one vendored skill in .agents/skills/."""

    model_config = ConfigDict(frozen=True)

    skill: VendoredSkill
    changed: bool
