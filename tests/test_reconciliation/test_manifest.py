import pytest
from pydantic import ValidationError

from agent_sync.models.output import ArtifactKind, GeneratedFile, Manifest
from agent_sync.workspace import Workspace


class TestManifest:
    """Test that generated output ownership is unambiguous."""

    def test_duplicate_targets_are_rejected(self, workspace: Workspace) -> None:
        """Test that two outputs cannot own the same target path."""

        output = GeneratedFile(
            target_path=workspace.root / "same",
            content="content\n",
            artifact=ArtifactKind.RULE,
            source_path=workspace.agents_dir / "rules/sample.md",
        )

        with pytest.raises(ValidationError, match="Duplicate generated targets"):
            Manifest(outputs=[output, output])
