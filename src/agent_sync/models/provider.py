from pathlib import Path
from typing import Final

from pydantic import BaseModel, ConfigDict

from agent_sync.models.output import Provider


class ProviderLayout(BaseModel):
    """Describe stable paths and extensions for one provider."""

    model_config = ConfigDict(frozen=True)

    directory: str
    rule_extension: str

    def root(self, repository_root: Path) -> Path:
        """Return the provider configuration root."""

        return repository_root / self.directory


PROVIDER_LAYOUTS: Final[dict[Provider, ProviderLayout]] = {
    Provider.CLAUDE: ProviderLayout(directory=".claude", rule_extension=".md"),
    Provider.CURSOR: ProviderLayout(directory=".cursor", rule_extension=".mdc"),
    Provider.CODEX: ProviderLayout(directory=".codex", rule_extension=".rules"),
}
