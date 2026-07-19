import subprocess
import sys

from agent_sync.workspace import Workspace


def run_cli(arguments: list[str]) -> subprocess.CompletedProcess[str]:
    """Run the package script with its real command-line boundary."""

    return subprocess.run(
        [sys.executable, "-m", "agent_sync", *arguments],
        capture_output=True,
        text=True,
        check=False,
    )


class TestCli:
    """Verify the unified CLI exposes both explicit pipeline operations."""

    def test_mirror_command_returns_clean_after_generation(self, workspace: Workspace) -> None:
        """Test that the mirror command runs and reaches an idempotent workspace."""

        arguments = ["mirror-providers", "--root", str(workspace.root)]

        assert run_cli(arguments).returncode == 0
        assert run_cli([*arguments, "--dry-run"]).returncode == 0

    def test_vendor_command_accepts_an_absent_registry(self, workspace: Workspace) -> None:
        """Test that the vendor command treats an absent registry as a clean no-op."""

        result = run_cli(["vendor-skills", "--root", str(workspace.root), "--dry-run"])

        assert result.returncode == 0

    def test_mirror_dry_run_returns_exit_code_one_for_differences(
        self,
        workspace: Workspace,
    ) -> None:
        """Test that the CLI maps detected differences to exit code one."""

        result = run_cli(["mirror-providers", "--root", str(workspace.root), "--dry-run"])

        assert result.returncode == 1

    def test_invalid_source_returns_exit_code_two(self, workspace: Workspace) -> None:
        """Test that invalid canonical input is reported with exit code two."""

        workspace.settings_dir.mkdir()
        (workspace.settings_dir / "claude.json").write_text("{invalid")

        result = run_cli(["mirror-providers", "--root", str(workspace.root)])

        assert result.returncode == 2
