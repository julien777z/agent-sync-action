from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

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
    """Validate shared lifecycle registration for Claude Code, Cursor and Codex."""

    model_config = ConfigDict(extra="forbid", strict=True)

    description: str | None = None
    hooks: dict[HookEvent, list[HookMatcher]]

    @model_validator(mode="after")
    def validate_codex_session_end_timeout(self) -> Self:
        """Keep SessionEnd handlers within Codex's supported timeout."""

        for group in self.hooks.get("SessionEnd", []):
            for handler in group.hooks:
                if handler.timeout is not None and handler.timeout > 3:
                    raise ValueError("SessionEnd hook timeouts cannot exceed 3 seconds")

        return self
