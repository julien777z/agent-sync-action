from typing import Final

from agent_sync.generation.artifact import (
    generate_agents,
    generate_hooks,
    generate_skills,
)
from agent_sync.generation.context import load_generation_context
from agent_sync.generation.rule import (
    generate_codex_rules,
    generate_rule_mirrors,
    generate_shared_rule_outputs,
)
from agent_sync.generation.setting import (
    generate_claude_code_settings,
    generate_codex_settings,
)
from agent_sync.models.generation import ArtifactRegistration
from agent_sync.models.output import (
    ArtifactKind,
    GeneratedFile,
    Manifest,
    Harness,
)
from agent_sync.models.settings import SourceConfig, Workspace

ARTIFACT_REGISTRY: Final[dict[ArtifactKind, ArtifactRegistration]] = {
    ArtifactKind.SKILL: ArtifactRegistration(
        owned_directory="skills",
        owned_files={},
        handlers={
            Harness.CLAUDE_CODE: generate_skills,
            Harness.CURSOR: generate_skills,
            Harness.CODEX: generate_skills,
        },
    ),
    ArtifactKind.AGENT: ArtifactRegistration(
        owned_directory="agents",
        owned_files={},
        handlers={
            Harness.CLAUDE_CODE: generate_agents,
            Harness.CURSOR: generate_agents,
        },
    ),
    ArtifactKind.RULE: ArtifactRegistration(
        owned_directory="rules",
        owned_files={},
        handlers={
            Harness.CLAUDE_CODE: generate_rule_mirrors,
            Harness.CURSOR: generate_rule_mirrors,
            Harness.CODEX: generate_codex_rules,
        },
    ),
    ArtifactKind.HOOK: ArtifactRegistration(
        owned_directory="hooks",
        owned_files={Harness.CODEX: ("hooks.json",)},
        handlers={
            Harness.CLAUDE_CODE: generate_hooks,
            Harness.CURSOR: generate_hooks,
            Harness.CODEX: generate_hooks,
        },
    ),
    ArtifactKind.SETTING: ArtifactRegistration(
        owned_directory=None,
        owned_files={
            Harness.CLAUDE_CODE: ("settings.json",),
            Harness.CODEX: ("config.toml",),
        },
        handlers={
            Harness.CLAUDE_CODE: generate_claude_code_settings,
            Harness.CODEX: generate_codex_settings,
        },
    ),
}


def generate_manifest(
    workspace: Workspace,
    source_config: SourceConfig,
) -> Manifest:
    """Generate the complete desired harness-output manifest."""

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

    harness_outputs = [
        output
        for registration in ARTIFACT_REGISTRY.values()
        for harness, handler in registration["handlers"].items()
        for output in handler(context, harness)
    ]

    return Manifest(outputs=[*shared_outputs, *harness_outputs])


def owned_harness_directories() -> tuple[tuple[Harness, str], ...]:
    """Return every harness directory fully owned by the registry."""

    return tuple(
        (harness, directory)
        for registration in ARTIFACT_REGISTRY.values()
        for directory in (registration["owned_directory"],)
        if directory is not None
        for harness in registration["handlers"]
    )
