from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class ActionConfig(BaseSettings):
    """Load runtime settings from typed defaults or environment overrides."""

    model_config = SettingsConfigDict(
        env_prefix="AGENT_SYNC_",
        extra="ignore",
        frozen=True,
    )

    skills_cli_version: str = "1.5.13"
    root: Path | None = None
    agents_dir: str = ".agents"
    output_dir: str = ""
