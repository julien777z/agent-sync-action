import runpy
import subprocess
import sys

import pytest

from agent_sync.external_skills import sync
from agent_sync.workspace import Workspace


class TestCli:
    """Test that the unified CLI exposes both explicit pipeline operations."""

    def run_cli(self, arguments: list[str]) -> subprocess.CompletedProcess[str]:
        """Run the package script with its real command-line boundary."""

        return subprocess.run(
            [sys.executable, "-m", "agent_sync", *arguments],
            capture_output=True,
            text=True,
            check=False,
        )

    def test_mirror_command_returns_clean_after_generation(self, workspace: Workspace) -> None:
        """Test that the mirror command runs and reaches an idempotent workspace."""

        arguments = ["mirror-providers", "--root", str(workspace.root)]

        assert self.run_cli(arguments).returncode == 0
        assert self.run_cli([*arguments, "--dry-run"]).returncode == 0

    def test_vendor_command_accepts_an_absent_registry(self, workspace: Workspace) -> None:
        """Test that the vendor command treats an absent registry as a clean no-op."""

        result = self.run_cli(["vendor-skills", "--root", str(workspace.root), "--dry-run"])

        assert result.returncode == 0

    def test_vendor_dry_run_updates_are_informational(
        self,
        monkeypatch: pytest.MonkeyPatch,
        workspace: Workspace,
    ) -> None:
        """Test that pending external updates do not fail a dry run."""

        def fake_sync_external_skills(resolved_workspace: Workspace, dry_run: bool) -> None:
            """Represent a successful dry run with pending updates."""

            assert resolved_workspace == workspace
            assert dry_run

        monkeypatch.setattr(sync, "sync_external_skills", fake_sync_external_skills)
        monkeypatch.setattr(
            sys,
            "argv",
            ["agent-sync", "vendor-skills", "--root", str(workspace.root), "--dry-run"],
        )

        with pytest.raises(SystemExit) as exit_result:
            runpy.run_module("agent_sync", run_name="__main__")

        assert exit_result.value.code == 0

    def test_mirror_dry_run_returns_exit_code_one_for_differences(
        self,
        workspace: Workspace,
    ) -> None:
        """Test that the CLI maps detected differences to exit code one."""

        (workspace.agents_dir / "project.md").write_text("# Project\n")
        result = self.run_cli(["mirror-providers", "--root", str(workspace.root), "--dry-run"])

        assert result.returncode == 1

    def test_output_directory_outside_the_repository_returns_exit_code_two(
        self,
        workspace: Workspace,
    ) -> None:
        """Test that a rejected output directory is reported with exit code two."""

        result = self.run_cli(
            ["mirror-providers", "--root", str(workspace.root), "--output-dir", "../escape"]
        )

        assert result.returncode == 2

    def test_vendor_command_rejects_an_output_directory(self, workspace: Workspace) -> None:
        """Test that the command writing no provider trees does not accept their location."""

        result = self.run_cli(["vendor-skills", "--root", str(workspace.root), "--output-dir", "generated"])

        assert result.returncode == 2

    def test_invalid_source_returns_exit_code_two(self, workspace: Workspace) -> None:
        """Test that invalid canonical input is reported with exit code two."""

        workspace.settings_dir.mkdir()
        (workspace.settings_dir / "claude.json").write_text("{invalid")

        result = self.run_cli(["mirror-providers", "--root", str(workspace.root)])

        assert result.returncode == 2

    def test_removed_instruction_generation_flag_is_rejected(self, workspace: Workspace) -> None:
        """Test that the removed CLI option cannot silently change generation."""

        result = self.run_cli(["mirror-providers", "--root", str(workspace.root), "--no-generate-agents-md"])
        assert result.returncode == 2
