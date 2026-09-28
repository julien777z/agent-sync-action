from typing import Final

from agent_sync.generation.artifact import generate_agents, generate_hooks, generate_skills
from agent_sync.generation.context import load_generation_context
from agent_sync.generation.rule import (
    generate_codex_rules,
    generate_rule_mirrors,
    generate_shared_rule_outputs,
)
from agent_sync.generation.setting import generate_claude_settings, generate_codex_settings
from agent_sync.models.generation import ArtifactRegistration
from agent_sync.models.output import (
    ArtifactKind,
    GeneratedFile,
    Manifest,
    Provider,
)
from agent_sync.models.settings import SourceConfig, Workspace

ARTIFACT_REGISTRY: Final[dict[ArtifactKind, ArtifactRegistration]] = {
    ArtifactKind.SKILL: ArtifactRegistration(
        owned_directory="skills",
        owned_files={},
        handlers={
            Provider.CLAUDE: generate_skills,
            Provider.CURSOR: generate_skills,
            Provider.CODEX: generate_skills,
        },
    ),
    ArtifactKind.AGENT: ArtifactRegistration(
        owned_directory="agents",
        owned_files={},
        handlers={
            Provider.CLAUDE: generate_agents,
            Provider.CURSOR: generate_agents,
        },
    ),
    ArtifactKind.RULE: ArtifactRegistration(
        owned_directory="rules",
        owned_files={},
        handlers={
            Provider.CLAUDE: generate_rule_mirrors,
            Provider.CURSOR: generate_rule_mirrors,
            Provider.CODEX: generate_codex_rules,
        },
    ),
    ArtifactKind.HOOK: ArtifactRegistration(
        owned_directory="hooks",
        owned_files={},
        handlers={
            Provider.CLAUDE: generate_hooks,
            Provider.CURSOR: generate_hooks,
        },
    ),
    ArtifactKind.SETTING: ArtifactRegistration(
        owned_directory=None,
        owned_files={
            Provider.CLAUDE: ("settings.json",),
            Provider.CODEX: ("config.toml",),
        },
        handlers={
            Provider.CLAUDE: generate_claude_settings,
            Provider.CODEX: generate_codex_settings,
        },
    ),
}


def generate_manifest(
    workspace: Workspace,
    source_config: SourceConfig,
) -> Manifest:
    """Generate the complete desired provider-output manifest."""

    context = load_generation_context(workspace, source_config)
    shared_outputs = generate_shared_rule_outputs(context)

    instructions = next(
        (
            output
            for output in shared_outputs
            if isinstance(output, GeneratedFile) and output.artifact is ArtifactKind.INSTRUCTIONS
        ),
        None,
    )
    if instructions is not None:
        context = context.model_copy(update={"instructions": instructions.content})

    provider_outputs = [
        output
        for registration in ARTIFACT_REGISTRY.values()
        for provider, handler in registration["handlers"].items()
        for output in handler(context, provider)
    ]

    return Manifest(outputs=[*shared_outputs, *provider_outputs])


def owned_provider_directories() -> tuple[tuple[Provider, str], ...]:
    """Return every provider directory fully owned by the registry."""

    return tuple(
        (provider, directory)
        for registration in ARTIFACT_REGISTRY.values()
        for directory in (registration["owned_directory"],)
        if directory is not None
        for provider in registration["handlers"]
    )
