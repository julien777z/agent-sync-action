from dataclasses import dataclass
from pathlib import Path
from typing import Final

from agent_sync.models.output import Provider


@dataclass(frozen=True)
class ProviderLayout:
    """Describe stable paths and extensions for one provider."""

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
