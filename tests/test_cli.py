from agent_sync.cli import main
from agent_sync.workspace import Workspace


class TestCli:
    """Verify the unified CLI exposes both explicit pipeline operations."""

    def test_mirror_command_returns_clean_after_generation(self, workspace: Workspace) -> None:
        """Test that the mirror command runs and reaches an idempotent workspace."""

        arguments = ["mirror-providers", "--root", str(workspace.root)]

        assert main(arguments) == 0
        assert main([*arguments, "--dry-run"]) == 0

    def test_vendor_command_accepts_an_absent_registry(self, workspace: Workspace) -> None:
        """Test that the vendor command treats an absent registry as a clean no-op."""

        assert main(["vendor-skills", "--root", str(workspace.root), "--dry-run"]) == 0

    def test_invalid_source_returns_exit_code_two(self, workspace: Workspace) -> None:
        """Test that invalid canonical input is reported with exit code two."""

        workspace.settings_dir.mkdir()
        (workspace.settings_dir / "claude.json").write_text("{invalid")

        assert main(["mirror-providers", "--root", str(workspace.root)]) == 2
