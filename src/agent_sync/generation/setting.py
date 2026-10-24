import json

from agent_sync.generation.artifact import GENERATED_FILE_NOTICE
from agent_sync.models.generation import GenerationContext
from agent_sync.models.output import ArtifactKind, GeneratedFile, GeneratedOutput, Harness
from agent_sync.models.settings import CodexSettings, PlatformSettings
from agent_sync.utils import AgentSyncError, ensure_trailing_newline
from agent_sync.workspace import agents_dir, output_root, settings_dir


def generate_claude_settings(
    context: GenerationContext,
    harness: Harness,
) -> list[GeneratedOutput]:
    """Generate complete Claude Code settings when configured."""

    settings = context.source_config.settings.get(harness)

    if not isinstance(settings, PlatformSettings):
        if context.hook_config is None:
            return []

        settings = PlatformSettings()

    values = settings.model_dump(exclude_none=True, exclude={"$comment"})

    if "hooks" in (settings.model_extra or {}):
        raise AgentSyncError(
            f"Define hooks in {agents_dir(context.workspace) / 'hooks/hooks.json'}; "
            f"{settings_dir(context.workspace) / 'claude.json'} must omit hooks"
        )

    if context.hook_config is not None:
        values["hooks"] = context.hook_config.model_dump(by_alias=True, exclude_none=True)["hooks"]

    return [
        GeneratedFile(
            target_path=harness.root(output_root(context.workspace)) / "settings.json",
            content=ensure_trailing_newline(
                json.dumps(
                    {
                        "$comment": GENERATED_FILE_NOTICE,
                        **values,
                    },
                    indent=2,
                )
            ),
            artifact=ArtifactKind.SETTING,
            source_path=(
                agents_dir(context.workspace) / "hooks/hooks.json"
                if context.hook_config is not None
                else settings_dir(context.workspace) / f"{harness.value}.json"
            ),
            harness=harness,
        )
    ]


def generate_codex_settings(
    context: GenerationContext,
    harness: Harness,
) -> list[GeneratedOutput]:
    """Generate synchronized Codex settings and source capacity."""

    settings = context.source_config.settings.get(harness)

    if not isinstance(settings, CodexSettings):
        if not context.instructions:
            return []

        settings = CodexSettings()

    synchronized = settings

    if context.instructions:
        synchronized = settings.model_copy(
            update={"project_doc_max_bytes": len(context.instructions.encode("utf-8"))}
        )

    source_path = settings_dir(context.workspace) / "codex.json"

    return [
        GeneratedFile(
            target_path=harness.root(output_root(context.workspace)) / "config.toml",
            content=synchronized.render_toml(GENERATED_FILE_NOTICE),
            artifact=ArtifactKind.SETTING,
            source_path=source_path,
            harness=harness,
        ),
    ]
