import json
import tomllib

from agent_sync.config import CodexSettings, PlatformSettings
from agent_sync.errors import AgentSyncError
from agent_sync.generation.artifact import GENERATED_FILE_NOTICE
from agent_sync.generation.context import GenerationContext
from agent_sync.models.output import ArtifactKind, GeneratedFile, GeneratedOutput, Provider
from agent_sync.utils import ensure_trailing_newline


def generate_claude_settings(
    context: GenerationContext,
    provider: Provider,
) -> list[GeneratedOutput]:
    """Generate complete Claude settings when configured."""

    settings = context.source_config.settings.get(provider)

    if not isinstance(settings, PlatformSettings):
        return []

    return [
        GeneratedFile(
            target_path=provider.root(context.workspace.output_root) / "settings.json",
            content=ensure_trailing_newline(
                json.dumps(
                    {
                        "$comment": GENERATED_FILE_NOTICE,
                        **settings.model_dump(exclude_none=True, exclude={"$comment"}),
                    },
                    indent=2,
                )
            ),
            artifact=ArtifactKind.SETTING,
            source_path=context.workspace.settings_dir / f"{provider.value}.json",
            provider=provider,
        )
    ]


def generate_codex_settings(
    context: GenerationContext,
    provider: Provider,
) -> list[GeneratedOutput]:
    """Generate synchronized Codex settings and source capacity."""

    settings = context.source_config.settings.get(provider)

    if not isinstance(settings, CodexSettings):
        if not context.instructions:
            return []
        settings = CodexSettings()

    synchronized = settings

    if context.instructions:
        synchronized = settings.model_copy(
            update={"project_doc_max_bytes": len(context.instructions.encode("utf-8"))}
        )

    source_path = context.workspace.settings_dir / "codex.json"

    return [
        GeneratedFile(
            target_path=provider.root(context.workspace.output_root) / "config.toml",
            content=render_codex_settings(synchronized),
            artifact=ArtifactKind.SETTING,
            source_path=source_path,
            provider=provider,
        ),
    ]


def render_codex_settings(settings: CodexSettings) -> str:
    """Render the complete generated Codex TOML file."""

    lines = [f"# {GENERATED_FILE_NOTICE}"]

    if settings.model:
        lines.append(f"model = {json.dumps(settings.model, ensure_ascii=False)}")

    if settings.project_doc_max_bytes is not None:
        lines.append(f"project_doc_max_bytes = {settings.project_doc_max_bytes}")

    if settings.features:
        lines.append("")
        lines.append("[features]")
        lines.extend(
            f"{json.dumps(name, ensure_ascii=False)} = {json.dumps(enabled)}"
            for name, enabled in settings.features.items()
        )

    rendered = ensure_trailing_newline("\n".join(lines))

    try:
        tomllib.loads(rendered)
    except tomllib.TOMLDecodeError as exc:
        raise AgentSyncError(f"Generated .codex/config.toml is invalid TOML: {exc}") from exc

    return rendered
