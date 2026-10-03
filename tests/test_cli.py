import runpy
import sys

import pytest

from agent_sync.config import ActionConfig
from agent_sync.external_resources import sync
from agent_sync.models.settings import Workspace
from agent_sync.workspace import agents_dir, settings_dir
from tests.factories import run_cli


class TestCli:
    """Test that the unified CLI exposes both explicit pipeline operations."""

    def test_mirror_command_returns_clean_after_generation(self, workspace: Workspace) -> None:
        """Test that the mirror command runs and reaches an idempotent workspace."""

        arguments = ["mirror-providers", "--root", str(workspace.root)]

        assert run_cli(arguments).returncode == 0
        assert run_cli([*arguments, "--dry-run"]).returncode == 0

    def test_cli_output_directory_overrides_the_environment(
        self, monkeypatch: pytest.MonkeyPatch, workspace: Workspace
    ) -> None:
        """Test that the CLI selects its output directory before the environment default."""

        monkeypatch.setenv("AGENT_SYNC_OUTPUT_DIR", ".generated")
        settings_dir(workspace).mkdir()
        (settings_dir(workspace) / "codex.json").write_text('{"model":"example"}')
        command = ["mirror-providers", "--root", str(workspace.root)]

        assert run_cli(command).returncode == 0
        assert (workspace.root / ".generated/.codex/config.toml").exists()

        assert run_cli([*command, "--output-dir", "chosen"]).returncode == 0
        assert (workspace.root / "chosen/.codex/config.toml").exists()

    def test_vendor_command_accepts_an_absent_registry(self, workspace: Workspace) -> None:
        """Test that the vendor command treats an absent registry as a clean no-op."""

        result = run_cli(["refresh-external-resources", "--root", str(workspace.root), "--dry-run"])

        assert result.returncode == 0

    def test_old_vendor_command_has_no_compatibility_alias(self, workspace: Workspace) -> None:
        """Test that consumers must use the unified public command."""

        result = run_cli(["vendor-skills", "--root", str(workspace.root)])

        assert result.returncode == 2

    def test_old_registry_is_not_loaded(self, workspace: Workspace) -> None:
        """Test that an obsolete registry cannot activate a second vendoring path."""

        (agents_dir(workspace) / "external_skills.json").write_text("{invalid")

        assert run_cli(["refresh-external-resources", "--root", str(workspace.root)]).returncode == 0

    def test_vendor_dry_run_updates_are_informational(
        self,
        monkeypatch: pytest.MonkeyPatch,
        workspace: Workspace,
    ) -> None:
        """Test that pending external updates do not fail a dry run."""

        def fake_sync_external_resources(
            resolved_workspace: Workspace, dry_run: bool, config: ActionConfig
        ) -> None:
            """Represent a successful dry run with pending updates."""

            assert resolved_workspace == workspace
            assert dry_run

        monkeypatch.setattr(sync, "sync_external_resources", fake_sync_external_resources)
        monkeypatch.setattr(
            sys,
            "argv",
            ["agent-sync", "refresh-external-resources", "--root", str(workspace.root), "--dry-run"],
        )

        with pytest.raises(SystemExit) as exit_result:
            runpy.run_module("agent_sync", run_name="__main__")

        assert exit_result.value.code == 0

    def test_mirror_dry_run_returns_exit_code_one_for_differences(
        self,
        workspace: Workspace,
    ) -> None:
        """Test that the CLI maps detected differences to exit code one."""

        (agents_dir(workspace) / "project.md").write_text("# Project\n")
        result = run_cli(["mirror-providers", "--root", str(workspace.root), "--dry-run"])

        assert result.returncode == 1

    def test_output_directory_outside_the_repository_returns_exit_code_two(
        self,
        workspace: Workspace,
    ) -> None:
        """Test that a rejected output directory is reported with exit code two."""

        result = run_cli(["mirror-providers", "--root", str(workspace.root), "--output-dir", "../escape"])

        assert result.returncode == 2

    def test_vendor_command_rejects_an_output_directory(self, workspace: Workspace) -> None:
        """Test that the command writing no provider trees does not accept their location."""

        result = run_cli(
            ["refresh-external-resources", "--root", str(workspace.root), "--output-dir", "generated"]
        )

        assert result.returncode == 2

    def test_invalid_source_returns_exit_code_two(self, workspace: Workspace) -> None:
        """Test that invalid canonical input is reported with exit code two."""

        settings_dir(workspace).mkdir()
        (settings_dir(workspace) / "claude.json").write_text("{invalid")

        result = run_cli(["mirror-providers", "--root", str(workspace.root)])

        assert result.returncode == 2

    def test_removed_instruction_generation_flag_is_rejected(self, workspace: Workspace) -> None:
        """Test that the removed CLI option cannot silently change generation."""

        result = run_cli(["mirror-providers", "--root", str(workspace.root), "--no-generate-agents-md"])
        assert result.returncode == 2
