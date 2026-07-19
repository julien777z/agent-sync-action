import json
import tomllib

from agent_sync.document import ensure_trailing_newline
from agent_sync.errors import AgentSyncError
from agent_sync.models.configuration import CanonicalConfiguration, CodexSettings, PlatformSettings
from agent_sync.models.output import ArtifactKind, GeneratedFile, GeneratedOutput, Provider
from agent_sync.models.provider import PROVIDER_LAYOUTS
from agent_sync.workspace import Workspace


def generate_setting_outputs(
    workspace: Workspace,
    configuration: CanonicalConfiguration,
    instructions: GeneratedFile,
) -> list[GeneratedOutput]:
    """Generate provider settings and synchronized canonical Codex capacity."""

    outputs: list[GeneratedOutput] = []
    claude_settings = configuration.settings.get(Provider.CLAUDE)
    if isinstance(claude_settings, PlatformSettings):
        outputs.append(
            GeneratedFile(
                target_path=(
                    PROVIDER_LAYOUTS[Provider.CLAUDE].root(workspace.root) / "settings.json"
                ),
                content=ensure_trailing_newline(
                    json.dumps(claude_settings.model_dump(exclude_none=True), indent=2)
                ),
                artifact=ArtifactKind.SETTING,
                source_path=workspace.settings_dir / "claude.json",
                provider=Provider.CLAUDE,
            )
        )

    codex_settings = configuration.settings.get(Provider.CODEX)
    if not isinstance(codex_settings, CodexSettings):
        return outputs

    synchronized = codex_settings.model_copy(
        update={"project_doc_max_bytes": len(instructions.content.encode("utf-8"))}
    )
    canonical_path = workspace.settings_dir / "codex.json"
    outputs.append(
        GeneratedFile(
            target_path=canonical_path,
            content=ensure_trailing_newline(
                synchronized.model_dump_json(indent=2, exclude_none=True)
            ),
            artifact=ArtifactKind.SETTING,
            source_path=canonical_path,
            provider=Provider.CODEX,
        )
    )

    config_path = PROVIDER_LAYOUTS[Provider.CODEX].root(workspace.root) / "config.toml"
    outputs.append(
        GeneratedFile(
            target_path=config_path,
            content=render_codex_settings(synchronized),
            artifact=ArtifactKind.SETTING,
            source_path=canonical_path,
            provider=Provider.CODEX,
        )
    )

    return outputs


def render_codex_settings(settings: CodexSettings) -> str:
    """Render the complete generated Codex TOML file."""

    lines: list[str] = []
    if settings.model:
        lines.append(f"model = {json.dumps(settings.model, ensure_ascii=False)}")
    lines.append(f"project_doc_max_bytes = {settings.project_doc_max_bytes}")
    rendered = ensure_trailing_newline("\n".join(lines))
    try:
        tomllib.loads(rendered)
    except tomllib.TOMLDecodeError as exc:
        raise AgentSyncError(f"Generated .codex/config.toml is invalid TOML: {exc}") from exc

    return rendered
