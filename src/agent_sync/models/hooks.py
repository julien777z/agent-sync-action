from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

type HookEvent = Literal[
    "SessionStart",
    "SessionEnd",
    "PreToolUse",
    "PostToolUse",
    "PreCompact",
    "UserPromptSubmit",
    "SubagentStop",
    "Stop",
]


class CommandHook(BaseModel):
    """Validate a portable command handler for the supported harnesses."""

    model_config = ConfigDict(extra="forbid", strict=True)

    type: Literal["command"]
    command: str = Field(min_length=1)
    timeout: int | None = Field(default=None, gt=0, le=2**64 - 1)


class HookMatcher(BaseModel):
    """Validate an event's matcher group and command handlers."""

    model_config = ConfigDict(extra="forbid", strict=True)

    matcher: str | None = None
    hooks: list[CommandHook] = Field(min_length=1)


class HooksConfig(BaseModel):
    """Validate shared lifecycle registration for Claude, Cursor and Codex."""

    model_config = ConfigDict(extra="forbid", strict=True)

    description: str | None = None
    hooks: dict[HookEvent, list[HookMatcher]]
