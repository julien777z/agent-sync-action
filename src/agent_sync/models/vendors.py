import logging
from typing import Final

from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator

from agent_sync.utils import SAFE_RELATIVE_PATH_PATTERN, SAFE_SLUG_PATTERN

logger = logging.getLogger(__name__)

ANTIGRAVITY_TARGET: Final[str] = "antigravity"
ANTIGRAVITY_AGENTS_DIRNAME: Final[str] = ".agents"


def validate_slugs(values: list[str]) -> list[str]:
    """Reject selectors that are not safe upstream slugs."""

    invalid = [value for value in values if not SAFE_SLUG_PATTERN.fullmatch(value)]

    if invalid:
        raise ValueError(f"Invalid selectors {invalid} (each must match {SAFE_SLUG_PATTERN.pattern})")

    return values


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
    cli_version: str = "1.5.13"
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


class EccVendor(BaseModel):
    """The ECC agent catalog installed through its own selective-install CLI."""

    model_config = ConfigDict(extra="forbid", strict=True)

    update_on_sync: bool = True
    version: str = "latest"
    target: str = ANTIGRAVITY_TARGET
    profile: str | None = None
    modules: list[str] = Field(default_factory=list[str])
    skills: list[str] = Field(default_factory=list[str])

    @field_validator("target", "profile")
    @classmethod
    def validate_selector(cls, value: str | None) -> str | None:
        """Reject targets and profiles that are not safe upstream slugs."""

        if value is not None and not SAFE_SLUG_PATTERN.fullmatch(value):
            raise ValueError(f"Invalid selector '{value}' (must match {SAFE_SLUG_PATTERN.pattern})")

        return value

    @field_validator("modules", "skills")
    @classmethod
    def validate_selectors(cls, value: list[str]) -> list[str]:
        """Reject module and skill IDs that are not safe upstream slugs."""

        return validate_slugs(value)

    @property
    def agents_dirname(self) -> str | None:
        """Return the canonical directory this target writes to, when it writes to one."""

        return ANTIGRAVITY_AGENTS_DIRNAME if self.target == ANTIGRAVITY_TARGET else None


class EccInstallPlan(BaseModel):
    """The file operations one ECC selective-install run reported."""

    model_config = ConfigDict(extra="ignore")

    operations: list[JsonValue] = Field(default_factory=list[JsonValue])


class EccInstallOutput(BaseModel):
    """The machine-readable output of one ECC selective-install run."""

    model_config = ConfigDict(extra="ignore")

    plan: EccInstallPlan | None = None
    result: EccInstallPlan | None = None

    @property
    def operation_count(self) -> int:
        """Return the number of file operations the run reported."""

        reported = self.plan or self.result

        return len(reported.operations) if reported is not None else 0


class Vendors(BaseModel):
    """The third-party systems Agent Sync can install from."""

    model_config = ConfigDict(extra="forbid", strict=True, populate_by_name=True)

    skills_cli: SkillsCliVendor | None = Field(
        default=None,
        validation_alias="skills-cli",
        serialization_alias="skills-cli",
    )
    ecc: EccVendor | None = None


class VendorRegistry(BaseModel):
    """The .agents/vendors.json vendor registry."""

    model_config = ConfigDict(extra="forbid", strict=True)

    version: int = 1
    vendors: Vendors = Field(default_factory=Vendors)


class VendoredSkillResult(BaseModel):
    """The outcome of updating one vendored skill in .agents/skills/."""

    model_config = ConfigDict(frozen=True)

    skill: VendoredSkill
    changed: bool
