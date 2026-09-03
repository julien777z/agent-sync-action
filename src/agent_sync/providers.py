import logging
from pathlib import Path
from typing import Final

from pydantic import BaseModel, ConfigDict, field_validator

from agent_sync.models.output import Provider

logger = logging.getLogger(__name__)


class ExplicitSkillInvocationPolicy(BaseModel):
    """Describe one provider's generated explicit-invocation policy."""

    model_config = ConfigDict(frozen=True)

    relative_path: Path
    content: str

    @field_validator("relative_path")
    @classmethod
    def validate_relative_path(cls, value: Path) -> Path:
        """Require generated metadata to live below the skill root."""

        if value.is_absolute() or len(value.parts) < 2:
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


PROVIDER_LAYOUTS: Final[dict[Provider, ProviderLayout]] = {
    Provider.CLAUDE: ProviderLayout(directory=".claude", rule_extension=".md"),
    Provider.CURSOR: ProviderLayout(directory=".cursor", rule_extension=".mdc"),
    Provider.CODEX: ProviderLayout(
        directory=".codex",
        rule_extension=".rules",
        explicit_skill_invocation_policy=ExplicitSkillInvocationPolicy(
            relative_path=Path("agents/openai.yaml"),
            content="policy:\n  allow_implicit_invocation: false\n",
        ),
    ),
}
