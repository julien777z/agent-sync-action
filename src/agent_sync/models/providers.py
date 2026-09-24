from pathlib import Path

from pydantic import BaseModel, ConfigDict


class ProviderLayout(BaseModel):
    """Describe stable paths and extensions for one provider."""

    model_config = ConfigDict(frozen=True)

    directory: str
    rule_extension: str

    def root(self, output_root: Path) -> Path:
        """Return the provider configuration root."""

        return output_root / self.directory
