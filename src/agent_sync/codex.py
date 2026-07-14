import json
import tomllib
from typing import Final

from agent_sync.utils.markdown import ensure_trailing_newline

CODEX_SETTINGS_START_MARKER: Final[str] = "# >>> agent-sync managed Codex settings >>>"
CODEX_SETTINGS_END_MARKER: Final[str] = "# <<< agent-sync managed Codex settings <<<"


class CodexGenerationError(ValueError):
    """Raised when managed Codex settings cannot be safely generated."""


def generate_codex_settings(
    settings: dict[str, object],
    existing: str | None,
) -> str:
    """Replace the managed top-level Codex settings block without touching MCP config."""

    current = existing or ""
    start_count = current.count(CODEX_SETTINGS_START_MARKER)
    end_count = current.count(CODEX_SETTINGS_END_MARKER)
    if start_count != end_count or start_count > 1:
        raise CodexGenerationError(".codex/config.toml has malformed Codex settings markers")

    lines = [CODEX_SETTINGS_START_MARKER]
    model = settings.get("model")
    if isinstance(model, str) and model:
        lines.append(f"model = {json.dumps(model, ensure_ascii=False)}")
    lines.append(f"project_doc_max_bytes = {settings['project_doc_max_bytes']}")
    lines.append(CODEX_SETTINGS_END_MARKER)
    block = "\n".join(lines)

    if start_count:
        start = current.index(CODEX_SETTINGS_START_MARKER)
        end = current.index(CODEX_SETTINGS_END_MARKER, start) + len(CODEX_SETTINGS_END_MARKER)
        rendered = current[:start] + block + current[end:]
    else:
        first_table = next(
            (index for index, line in enumerate(current.splitlines(keepends=True)) if line.lstrip().startswith("[")),
            None,
        )
        if first_table is None:
            rendered = "\n\n".join(part for part in (current.rstrip(), block) if part)
        else:
            split_lines = current.splitlines(keepends=True)
            rendered = "".join(split_lines[:first_table]).rstrip() + "\n\n" + block + "\n\n" + "".join(split_lines[first_table:]).lstrip()

    rendered = ensure_trailing_newline(rendered)
    try:
        tomllib.loads(rendered)
    except tomllib.TOMLDecodeError as exc:
        raise CodexGenerationError(f"generated .codex/config.toml is invalid TOML: {exc}") from exc

    return rendered
