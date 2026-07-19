from pydantic import BaseModel, ConfigDict

from agent_sync.models.output import Provider


class PlatformSettings(BaseModel):
    """Validate provider settings whose extra keys are mirrored unchanged."""

    model_config = ConfigDict(extra="allow", strict=True)

    model: str | None = None


class CodexSettings(BaseModel):
    """Validate canonical settings for generated Codex project configuration."""

    model_config = ConfigDict(extra="forbid", strict=True)

    model: str | None = None
    project_doc_max_bytes: int


class AgentModelOverride(BaseModel):
    """Validate supported per-provider model overrides for one agent."""

    model_config = ConfigDict(extra="forbid", strict=True)

    claude: str | None = None
    cursor: str | None = None

    def for_provider(self, provider: Provider) -> str | None:
        """Return the configured model override for a supported provider."""

        match provider:
            case Provider.CLAUDE:
                return self.claude
            case Provider.CURSOR:
                return self.cursor
            case Provider.CODEX:
                return None


class CanonicalConfiguration(BaseModel):
    """Hold all validated canonical settings and model overrides."""

    model_config = ConfigDict(frozen=True)

    settings: dict[Provider, PlatformSettings | CodexSettings]
    model_overrides: dict[str, AgentModelOverride]
