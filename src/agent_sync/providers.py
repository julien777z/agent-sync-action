from typing import Final

from agent_sync.models.output import Provider
from agent_sync.models.providers import ProviderLayout

PROVIDER_LAYOUTS: Final[dict[Provider, ProviderLayout]] = {
    Provider.CLAUDE: ProviderLayout(directory=".claude", rule_extension=".md"),
    Provider.CURSOR: ProviderLayout(directory=".cursor", rule_extension=".mdc"),
    Provider.CODEX: ProviderLayout(directory=".codex", rule_extension=".rules"),
}
