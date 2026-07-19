from collections.abc import Callable
from typing import Final, TypedDict

from agent_sync.generation.agent import generate_agents
from agent_sync.generation.command import generate_claude_commands, generate_cursor_commands
from agent_sync.generation.context import GenerationContext
from agent_sync.generation.hook import generate_hooks
from agent_sync.generation.rule import generate_codex_rules, generate_rule_links
from agent_sync.generation.setting import generate_claude_settings, generate_codex_settings
from agent_sync.generation.skill import generate_skills
from agent_sync.models.output import ArtifactKind, GeneratedOutput, Provider

type GenerationHandler = Callable[[GenerationContext, Provider], list[GeneratedOutput]]


class ArtifactRegistration(TypedDict):
    """Describe generation and ownership for one artifact kind."""

    owned_directory: str | None
    owned_files: dict[Provider, tuple[str, ...]]
    handlers: dict[Provider, GenerationHandler]


ARTIFACT_REGISTRY: Final[dict[ArtifactKind, ArtifactRegistration]] = {
    ArtifactKind.SKILL: {
        "owned_directory": "skills",
        "owned_files": {},
        "handlers": {
            Provider.CLAUDE: generate_skills,
            Provider.CURSOR: generate_skills,
            Provider.CODEX: generate_skills,
        },
    },
    ArtifactKind.COMMAND: {
        "owned_directory": "commands",
        "owned_files": {},
        "handlers": {
            Provider.CLAUDE: generate_claude_commands,
            Provider.CURSOR: generate_cursor_commands,
        },
    },
    ArtifactKind.AGENT: {
        "owned_directory": "agents",
        "owned_files": {},
        "handlers": {
            Provider.CLAUDE: generate_agents,
            Provider.CURSOR: generate_agents,
        },
    },
    ArtifactKind.RULE: {
        "owned_directory": "rules",
        "owned_files": {},
        "handlers": {
            Provider.CLAUDE: generate_rule_links,
            Provider.CURSOR: generate_rule_links,
            Provider.CODEX: generate_codex_rules,
        },
    },
    ArtifactKind.HOOK: {
        "owned_directory": "hooks",
        "owned_files": {},
        "handlers": {
            Provider.CLAUDE: generate_hooks,
            Provider.CURSOR: generate_hooks,
        },
    },
    ArtifactKind.SETTING: {
        "owned_directory": None,
        "owned_files": {
            Provider.CLAUDE: ("settings.json",),
            Provider.CODEX: ("config.toml",),
        },
        "handlers": {
            Provider.CLAUDE: generate_claude_settings,
            Provider.CODEX: generate_codex_settings,
        },
    },
}


def owned_provider_directories() -> tuple[tuple[Provider, str], ...]:
    """Return every provider directory fully owned by the registry."""

    return tuple(
        (provider, directory)
        for registration in ARTIFACT_REGISTRY.values()
        for directory in (registration["owned_directory"],)
        if directory is not None
        for provider in registration["handlers"]
    )
