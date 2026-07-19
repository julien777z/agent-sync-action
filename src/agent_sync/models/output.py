from collections import Counter
from enum import StrEnum
import logging
from pathlib import Path
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

logger = logging.getLogger(__name__)


class Provider(StrEnum):
    """Identify a generated provider layout."""

    CLAUDE = "claude"
    CURSOR = "cursor"
    CODEX = "codex"


class ArtifactKind(StrEnum):
    """Identify the canonical artifact represented by a generated output."""

    SKILL = "skill"
    AGENT = "agent"
    RULE = "rule"
    HOOK = "hook"
    SETTING = "setting"
    INSTRUCTIONS = "instructions"


class GeneratedFile(BaseModel):
    """Describe one generated text file."""

    model_config = ConfigDict(frozen=True)

    output_type: Literal["file"] = "file"
    target_path: Path
    content: str
    artifact: ArtifactKind
    source_path: Path
    provider: Provider | None = None
    executable: bool = False


class GeneratedLink(BaseModel):
    """Describe one generated relative symlink."""

    model_config = ConfigDict(frozen=True)

    output_type: Literal["link"] = "link"
    target_path: Path
    link_target: Path
    artifact: ArtifactKind
    source_path: Path
    provider: Provider


GeneratedOutput = Annotated[GeneratedFile | GeneratedLink, Field(discriminator="output_type")]


class Manifest(BaseModel):
    """Hold the complete validated set of desired generated outputs."""

    model_config = ConfigDict(frozen=True)

    outputs: list[GeneratedOutput]

    @model_validator(mode="after")
    def validate_unique_targets(self) -> Self:
        """Reject manifests containing more than one owner for a target path."""

        target_counts = Counter(output.target_path for output in self.outputs)
        duplicates = sorted(
            (target for target, count in target_counts.items() if count > 1), key=str
        )

        if duplicates:
            raise ValueError(f"Duplicate generated targets: {duplicates}")

        return self


class Change(BaseModel):
    """Pair a generated output with the current on-disk representation."""

    model_config = ConfigDict(frozen=True)

    output: GeneratedOutput
    existing: str | None


class ReconciliationPlan(BaseModel):
    """Describe generated changes and stale managed paths."""

    model_config = ConfigDict(frozen=True)

    changes: list[Change]
    stale_paths: list[Path]

    @property
    def is_clean(self) -> bool:
        """Report whether reconciliation would leave the workspace unchanged."""

        return not self.changes and not self.stale_paths
