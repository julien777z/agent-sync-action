from pathlib import Path

import pytest
from pydantic import ValidationError

from agent_sync.config import ActionConfig
from agent_sync.workspace import Workspace


class TestWorkspace:
    """Test that a workspace resolves its directories and observes the filesystem directly."""

    def test_output_root_defaults_to_the_repository_root(self, tmp_path: Path) -> None:
        """Test that an unset output directory writes generated trees at the repository root."""

        assert Workspace(root=tmp_path).output_root == tmp_path

    def test_output_root_follows_the_configured_directory(self, tmp_path: Path) -> None:
        """Test that a configured output directory nests every generated tree below it."""

        workspace = Workspace(root=tmp_path, output_dirname=".agents/.auto_generated")

        assert workspace.output_root == tmp_path / ".agents/.auto_generated"

    @pytest.mark.parametrize(
        "output_dirname",
        ["/absolute", "../escape", "nested/../.."],
        ids=["absolute", "parent", "nested-parent"],
    )
    def test_rejects_an_output_directory_outside_the_repository(self, output_dirname: str) -> None:
        """Test that a generated output directory cannot escape the repository."""

        with pytest.raises(ValidationError, match="relative path inside the repository"):
            Workspace(output_dirname=output_dirname)

    def test_resolve_accepts_an_explicit_output_directory(self, tmp_path: Path) -> None:
        """Test that the resolved workspace carries the requested output directory."""

        workspace = Workspace.resolve(str(tmp_path), None, ".agents/.auto_generated")

        assert workspace.output_dirname == ".agents/.auto_generated"

    def test_resolve_falls_back_to_the_environment_for_an_unset_output_directory(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """Test that an absent or empty output directory takes the configured one."""

        monkeypatch.setattr(
            "agent_sync.workspace.ACTION_CONFIG",
            ActionConfig(output_dir=".generated"),
        )

        assert Workspace.resolve(str(tmp_path), None, None).output_dirname == ".generated"
        assert Workspace.resolve(str(tmp_path), None, "").output_dirname == ".generated"
        assert Workspace.resolve(str(tmp_path), None, "chosen").output_dirname == "chosen"

    def test_reads_current_disk_state(self, workspace: Workspace) -> None:
        """Test that workspace reads never return stale cached content."""

        path = workspace.root / "state.txt"
        path.write_text("first")

        assert workspace.read_text(path) == "first"

        path.write_text("second")

        assert workspace.read_text(path) == "second"
