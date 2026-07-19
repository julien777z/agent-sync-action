from enum import StrEnum
from pathlib import Path
from typing import Self

from pydantic import BaseModel, ConfigDict, model_validator


class OutputKind(StrEnum):
    """The category of a generated mirror file, used for stale detection and reporting."""

    CURSOR_SKILL = "cursor_skill"
    CLAUDE_SKILL = "claude_skill"
    CODEX_SKILL = "codex_skill"
    CURSOR_SKILL_ASSET = "cursor_skill_asset"
    CLAUDE_SKILL_ASSET = "claude_skill_asset"
    CODEX_SKILL_ASSET = "codex_skill_asset"
    CLAUDE_COMMAND = "claude_command"
    CURSOR_COMMAND = "cursor_command"
    CLAUDE_AGENT = "claude_agent"
    CURSOR_AGENT = "cursor_agent"
    AGENTS_RULE = "agents_rule"
    CLAUDE_RULE = "claude_rule"
    CURSOR_RULE = "cursor_rule"
    CODEX_RULE = "codex_rule"
    CLAUDE_HOOK = "claude_hook"
    CURSOR_HOOK = "cursor_hook"
    CLAUDE_SETTINGS = "claude_settings"
    AGENTS_INSTRUCTIONS = "agents_instructions"
    CODEX_SETTINGS = "codex_settings"
    CLAUDE_MCP = "claude_mcp"
    CURSOR_MCP = "cursor_mcp"
    CODEX_MCP = "codex_mcp"


class OutputFile(BaseModel):
    """A generated mirror file or relative symlink destined for an agent-config path."""

    model_config = ConfigDict(frozen=True)

    target_path: Path
    content: str | bytes
    kind: OutputKind
    slug: str
    source_path: Path | None
    link_target: Path | None = None

    @model_validator(mode="after")
    def validate_link_has_no_content(self) -> Self:
        """Reject symlink outputs that also carry file content."""

        if self.link_target is not None and self.content:
            raise ValueError("Symlink outputs must not define content.")

        return self


class DiffEntry(BaseModel):
    """A generated output paired with its current on-disk content."""

    model_config = ConfigDict(frozen=True)

    output: OutputFile
    existing: str | bytes | None
