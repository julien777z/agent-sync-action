from pathlib import Path
from typing import ClassVar

from pydantic_settings import BaseSettings, SettingsConfigDict


class ActionConfig(BaseSettings):
    """Load runtime settings from typed defaults or environment overrides."""

    COMMIT_AUTHOR_NAME: ClassVar[str] = "github-actions[bot]"
    COMMIT_AUTHOR_EMAIL: ClassVar[str] = "github-actions[bot]@users.noreply.github.com"

    model_config = SettingsConfigDict(
        env_prefix="AGENT_SYNC_",
        extra="ignore",
        frozen=True,
    )

    skills_cli_version: str = "1.5.13"
    root: Path | None = None
    agents_dir: str = ".agents"
    output_dir: str = ""
