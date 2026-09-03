from pathlib import Path
from typing import Final

from agent_sync.models.output import Provider
from agent_sync.models.providers import ExplicitSkillInvocationPolicy, ProviderLayout

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
