import json
import tomllib
from typing import Final

from agent_sync.document import ensure_trailing_newline
from agent_sync.errors import AgentSyncError
from agent_sync.models.configuration import CanonicalConfiguration, CodexSettings, PlatformSettings
from agent_sync.models.output import ArtifactKind, GeneratedFile, GeneratedOutput, Provider
from agent_sync.models.provider import PROVIDER_LAYOUTS
from agent_sync.workspace import Workspace

CODEX_SETTINGS_START_MARKER: Final[str] = "# >>> agent-sync managed Codex settings >>>"
CODEX_SETTINGS_END_MARKER: Final[str] = "# <<< agent-sync managed Codex settings <<<"


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
            content=render_codex_settings(
                synchronized,
                workspace.read_text(config_path),
            ),
            artifact=ArtifactKind.SETTING,
            source_path=canonical_path,
            provider=Provider.CODEX,
        )
    )

    return outputs


def render_codex_settings(settings: CodexSettings, existing: str | None) -> str:
    """Replace the managed top-level settings block in Codex TOML."""

    current = existing or ""
    start_count = current.count(CODEX_SETTINGS_START_MARKER)
    end_count = current.count(CODEX_SETTINGS_END_MARKER)
    if start_count != end_count or start_count > 1:
        raise AgentSyncError(".codex/config.toml has malformed managed settings markers")

    lines = [CODEX_SETTINGS_START_MARKER]
    if settings.model:
        lines.append(f"model = {json.dumps(settings.model, ensure_ascii=False)}")
    lines.extend(
        (
            f"project_doc_max_bytes = {settings.project_doc_max_bytes}",
            CODEX_SETTINGS_END_MARKER,
        )
    )
    block = "\n".join(lines)

    if start_count:
        start = current.index(CODEX_SETTINGS_START_MARKER)
        end = current.index(CODEX_SETTINGS_END_MARKER, start) + len(CODEX_SETTINGS_END_MARKER)
        rendered = current[:start] + block + current[end:]
    else:
        rendered = insert_before_first_table(current, block)

    rendered = ensure_trailing_newline(rendered)
    try:
        tomllib.loads(rendered)
    except tomllib.TOMLDecodeError as exc:
        raise AgentSyncError(f"Generated .codex/config.toml is invalid TOML: {exc}") from exc

    return rendered


def insert_before_first_table(current: str, block: str) -> str:
    """Insert managed top-level settings before the first TOML table."""

    split_lines = current.splitlines(keepends=True)
    first_table = next(
        (index for index, line in enumerate(split_lines) if line.lstrip().startswith("[")),
        None,
    )
    if first_table is None:
        return "\n\n".join(part for part in (current.rstrip(), block) if part)

    prefix = "".join(split_lines[:first_table]).rstrip()
    suffix = "".join(split_lines[first_table:]).lstrip()

    return "\n\n".join(part for part in (prefix, block, suffix) if part)
