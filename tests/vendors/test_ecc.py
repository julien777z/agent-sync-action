import json
import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest
from pydantic import ValidationError

from agent_sync.models.vendors.ecc import EccVendor
from agent_sync.vendors.ecc import command, install
from agent_sync.workspace import Workspace
from tests.factories import EccVendorFactory, materialize_tree


class TestEccCommand:
    """Test that ECC selective-install invocations are built from vendor options."""

    def test_profile_only_selection_builds_command(self) -> None:
        """Test that a profile-only configuration passes just its profile."""

        invocation = command.build_command(EccVendorFactory.build(), dry_run=False)

        assert invocation[:2] == ["npx", "--yes"]
        assert invocation[3] == "install"
        assert invocation[invocation.index("--target") + 1] == "antigravity"
        assert invocation[invocation.index("--profile") + 1] == "core"
        assert "--modules" not in invocation
        assert "--skills" not in invocation
        assert invocation[-1] == "--json"

    def test_configured_version_reaches_command(
        self,
        configure_action: Callable[..., None],
    ) -> None:
        """Test that a vendor without its own pin runs the configured version."""

        configure_action(ecc_version="2.2.0")

        invocation = command.build_command(EccVendor(), dry_run=False)

        assert invocation[2] == f"{command.ECC_PACKAGE}@2.2.0"

    def test_modules_and_skills_pass_comma_lists(self) -> None:
        """Test that explicit module and skill selections reach the installer."""

        vendor = EccVendorFactory.build(modules=["security", "database"], skills=["deep-research"])

        invocation = command.build_command(vendor, dry_run=False)

        assert invocation[invocation.index("--modules") + 1] == "security,database"
        assert invocation[invocation.index("--skills") + 1] == "deep-research"

    def test_dry_run_forwards_installer_flag(self) -> None:
        """Test that a dry run never asks the installer to write files."""

        assert "--dry-run" in command.build_command(EccVendorFactory.build(), dry_run=True)

    @pytest.mark.parametrize("field", ["modules", "skills"])
    def test_unsafe_selectors_fail(self, field: str) -> None:
        """Test that unsafe module and skill IDs are rejected before invocation."""

        with pytest.raises(ValidationError):
            EccVendor.model_validate({field: ["../escape"]})

    def test_destinations_come_from_installer_output(self) -> None:
        """Test that installed destinations are read from the installer's own plan."""

        planned = '{"dryRun": true, "plan": {"operations": [{"destinationPath": "/repo/.agents/a.md"}]}}'
        applied = '{"dryRun": false, "result": {"operations": [{"destinationPath": "/repo/.agents/b.md"}]}}'

        assert command.installed_destinations(planned) == ["/repo/.agents/a.md"]
        assert command.installed_destinations(applied) == ["/repo/.agents/b.md"]
        assert command.installed_destinations("not json") == []


class TestEccInstall:
    """Test that ECC installation is guarded and leaves no machine-local state."""

    def test_mismatched_canonical_directory_fails(self, tmp_path: Path) -> None:
        """Test that a target writing outside canonical sources is refused."""

        workspace = Workspace(root=tmp_path, agents_dirname="agent-sources")

        with pytest.raises(RuntimeError, match="agent-sources"):
            install.assert_target_writes_to_workspace(workspace, EccVendorFactory.build())

    def test_failing_installer_surfaces_output(
        self,
        monkeypatch: pytest.MonkeyPatch,
        workspace: Workspace,
    ) -> None:
        """Test that installer failures report the captured diagnostics."""

        def fake_run(
            invocation: list[str],
            *,
            cwd: Path,
            capture_output: bool,
            text: bool,
            check: bool,
        ) -> subprocess.CompletedProcess[str]:
            """Return a failed installer invocation."""

            return subprocess.CompletedProcess(invocation, 1, "planned nothing", "unknown profile")

        monkeypatch.setattr(install.subprocess, "run", fake_run)

        with pytest.raises(RuntimeError, match="unknown profile"):
            install.install_ecc_vendor(workspace, EccVendorFactory.build(), dry_run=False)

    @pytest.mark.parametrize("dry_run", [True, False], ids=["dry-run", "applied"])
    def test_local_install_state_is_not_kept(
        self,
        monkeypatch: pytest.MonkeyPatch,
        workspace: Workspace,
        dry_run: bool,
    ) -> None:
        """Test that an applied install leaves no machine-specific state in canonical sources."""

        install_state = workspace.agents_dir / install.INSTALL_STATE_FILENAME
        install_state.write_text('{"installedAt": "2026-01-01T00:00:00.000Z"}', encoding="utf-8")

        def fake_run(
            invocation: list[str],
            *,
            cwd: Path,
            capture_output: bool,
            text: bool,
            check: bool,
        ) -> subprocess.CompletedProcess[str]:
            """Return a successful installer invocation."""

            return subprocess.CompletedProcess(invocation, 0, '{"plan": {"operations": []}}', "")

        monkeypatch.setattr(install.subprocess, "run", fake_run)

        install.install_ecc_vendor(workspace, EccVendorFactory.build(), dry_run=dry_run)

        assert install_state.exists() is dry_run

    def test_installed_skill_names_match_their_directories(
        self,
        monkeypatch: pytest.MonkeyPatch,
        workspace: Workspace,
    ) -> None:
        """Test that a catalog skill announcing another name is renamed to its directory."""

        directory = workspace.agents_dir / "skills" / "scientific-db-pubmed-database"
        materialize_tree(
            directory,
            {
                "SKILL.md": (
                    "---\n"
                    "name: pubmed-database\n"
                    "description: Search biomedical literature.\n"
                    "---\n\n"
                    "# PubMed\n"
                )
            },
        )
        destination = str(directory / "SKILL.md")

        def fake_run(
            invocation: list[str],
            *,
            cwd: Path,
            capture_output: bool,
            text: bool,
            check: bool,
        ) -> subprocess.CompletedProcess[str]:
            """Return an installer invocation that wrote one skill document."""

            plan = json.dumps(
                {"plan": {"operations": [{"destinationPath": destination}]}},
            )

            return subprocess.CompletedProcess(invocation, 0, plan, "")

        monkeypatch.setattr(install.subprocess, "run", fake_run)

        install.install_ecc_vendor(workspace, EccVendorFactory.build(), dry_run=False)

        assert (directory / "SKILL.md").read_text() == (
            "---\n"
            "name: scientific-db-pubmed-database\n"
            "description: Search biomedical literature.\n"
            "---\n\n"
            "# PubMed\n"
        )
