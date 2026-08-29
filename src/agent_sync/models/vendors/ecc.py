import logging
from typing import Final

from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator

from agent_sync.utils import SAFE_SLUG_PATTERN

logger = logging.getLogger(__name__)

ANTIGRAVITY_TARGET: Final[str] = "antigravity"
ANTIGRAVITY_AGENTS_DIRNAME: Final[str] = ".agents"


def validate_slugs(values: list[str]) -> list[str]:
    """Reject selectors that are not safe upstream slugs."""

    invalid = [value for value in values if not SAFE_SLUG_PATTERN.fullmatch(value)]

    if invalid:
        raise ValueError(f"Invalid selectors {invalid} (each must match {SAFE_SLUG_PATTERN.pattern})")

    return values


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
