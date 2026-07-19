from pydantic import BaseModel, ConfigDict, Field, field_validator

from agent_sync.utils import SAFE_SLUG_PATTERN


class ExternalSkill(BaseModel):
    """A single skills.sh skill to vendor into .agents/skills/<name>/."""

    model_config = ConfigDict(extra="forbid", strict=True)

    name: str
    repo: str
    skill: str | None = None
    automatic_updates: bool

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        """Reject names that would not be a safe skill directory slug."""

        if not SAFE_SLUG_PATTERN.match(value):
            raise ValueError(
                f"Invalid skill name '{value}' (must match {SAFE_SLUG_PATTERN.pattern})"
            )

        return value

    @property
    def upstream_skill(self) -> str:
        """Return the skill slug to request from the source repo (defaults to the local name)."""

        return self.skill or self.name


class SkillsRegistry(BaseModel):
    """The .agents/skills.json external-skill registry."""

    model_config = ConfigDict(extra="forbid", strict=True)

    version: int = 1
    skills: list[ExternalSkill] = Field(default_factory=list[ExternalSkill])


class SkillLockEntry(BaseModel):
    """Validate one skill installer lock entry."""

    model_config = ConfigDict(extra="allow", strict=True, populate_by_name=True)

    skill_path: str = Field(alias="skillPath")


class SkillsLock(BaseModel):
    """Validate the temporary lock file emitted by the skill installer."""

    model_config = ConfigDict(extra="allow", strict=True)

    skills: dict[str, SkillLockEntry]


class VendorResult(BaseModel):
    """The outcome of vendoring one external skill into .agents/skills/."""

    model_config = ConfigDict(frozen=True)

    skill: ExternalSkill
    changed: bool
