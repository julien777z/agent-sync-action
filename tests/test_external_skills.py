import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest
from pydantic import ValidationError

from agent_sync.config import CONFIG, Config
from agent_sync.external_skills import github, installer
from agent_sync.external_skills import sync as external_skills
from agent_sync.models.registry import ExternalSkill, SkillsRegistry
from agent_sync.workspace import Workspace


class TestExternalSkillModel:
    """Verify external-skill registry validation and defaults."""

    def test_upstream_slug_defaults_to_local_name(self) -> None:
        """Test that an omitted upstream slug uses the local skill name."""

        skill = ExternalSkill(
            name="sample-skill",
            repo="example/sample-skill",
            automatic_updates=True,
        )

        assert skill.upstream_skill == "sample-skill"

    @pytest.mark.parametrize("name", ["Bad Name", "UPPER", "-leading"])
    def test_invalid_skill_names_fail(self, name: str) -> None:
        """Test that unsafe external skill names are rejected."""

        with pytest.raises(ValidationError):
            ExternalSkill(name=name, repo="example/sample", automatic_updates=True)

    def test_automatic_updates_is_required(self) -> None:
        """Test that every registry entry chooses its update behavior explicitly."""

        with pytest.raises(ValidationError, match="automatic_updates"):
            ExternalSkill.model_validate({"name": "sample", "repo": "example/sample"})


class TestExternalSkillBoundaries:
    """Verify immutable GitHub snapshots and installer behavior."""

    def test_runtime_config_accepts_namespaced_overrides(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that future CLI versions can be selected without code changes."""

        monkeypatch.setenv("AGENT_SYNC_SKILLS_CLI_VERSION", "9.9.9")

        assert Config().skills_cli_version == "9.9.9"

    def test_revision_resolution_returns_exact_head(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that repository HEAD resolution returns the exact SHA."""

        revision = "a" * 40

        def fake_run(
            command: list[str],
            *,
            capture_output: bool,
            text: bool,
            check: bool,
        ) -> subprocess.CompletedProcess[str]:
            """Return a successful immutable revision lookup."""

            return subprocess.CompletedProcess(command, 0, f"{revision}\tHEAD\n", "")

        monkeypatch.setattr(github.subprocess, "run", fake_run)

        assert github.resolve_revision("example/repository") == revision

    def test_invalid_revision_output_fails(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that unusable remote output fails before sources can be mixed."""

        def fake_run(
            command: list[str],
            *,
            capture_output: bool,
            text: bool,
            check: bool,
        ) -> subprocess.CompletedProcess[str]:
            """Return an invalid revision lookup result."""

            return subprocess.CompletedProcess(command, 0, "not-a-sha\tHEAD\n", "")

        monkeypatch.setattr(github.subprocess, "run", fake_run)

        with pytest.raises(RuntimeError, match="git ls-remote"):
            github.resolve_revision("example/repository")

    def test_installer_uses_downloaded_snapshot(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """Test that the installer receives the local immutable source directory."""

        source_root = tmp_path / "source"
        captured: list[str] = []

        def fake_run(
            command: list[str],
            *,
            cwd: Path,
            capture_output: bool,
            text: bool,
            check: bool,
        ) -> subprocess.CompletedProcess[str]:
            """Capture one installer invocation."""

            captured.extend(command)
            return subprocess.CompletedProcess(command, 0, "", "")

        monkeypatch.setattr(installer.subprocess, "run", fake_run)
        skill = ExternalSkill(
            name="sample",
            repo="example/repository",
            automatic_updates=True,
        )

        installer.install_skill(skill, tmp_path, source_root)

        assert str(source_root) in captured
        assert f"skills@{CONFIG.skills_cli_version}" in captured
        assert captured[captured.index("-a") + 1] == installer.SKILLS_CLI_AGENT

    def test_installed_skill_discovery_is_provider_neutral(self, tmp_path: Path) -> None:
        """Test that staging discovery does not depend on one provider directory."""

        source_root = tmp_path / "source/repository"
        source_root.mkdir(parents=True)
        (source_root / "SKILL.md").write_text("source\n")

        installed = tmp_path / ".staging/skills/sample"
        installed.mkdir(parents=True)
        (installed / "SKILL.md").write_text("installed\n")

        assert installer.locate_installed_skill(tmp_path, source_root, "sample") == installed

    def test_one_snapshot_drives_installation_and_assets(
        self,
        monkeypatch: pytest.MonkeyPatch,
        workspace: Workspace,
    ) -> None:
        """Test that installation and supplemental assets share one revision."""

        revision = "c" * 40
        observed: list[tuple[str, str]] = []
        skill = ExternalSkill(
            name="sample",
            repo="example/repository",
            automatic_updates=True,
        )

        def fake_resolve(repository: str) -> str:
            """Resolve a stable synthetic revision."""

            return revision

        monkeypatch.setattr(github, "resolve_revision", fake_resolve)

        def fake_download(repository: str, downloaded_revision: str, destination: Path) -> Path:
            """Create one synthetic downloaded snapshot."""

            observed.append(("snapshot", downloaded_revision))
            source_root = destination / "repository"
            source_root.mkdir(parents=True)
            (source_root / "SKILL.md").write_text("content\n")

            return source_root

        monkeypatch.setattr(github, "download_snapshot", fake_download)

        def fake_install(
            installed_skill: ExternalSkill,
            working_directory: Path,
            source_root: Path,
        ) -> None:
            """Create one synthetic installed skill."""

            observed.append(("install", str(source_root)))
            installed = working_directory / ".staging/skills" / installed_skill.name
            installed.mkdir(parents=True)
            (installed / "SKILL.md").write_text("content\n")

        monkeypatch.setattr(installer, "install_skill", fake_install)

        def fake_read_skill_path(working_directory: Path) -> str:
            """Return the synthetic installed skill path."""

            return "SKILL.md"

        monkeypatch.setattr(installer, "read_skill_path", fake_read_skill_path)

        def fake_supplement(destination: Path, source_root: Path) -> None:
            """Record the snapshot used for supplemental assets."""

            observed.append(("assets", str(source_root)))

        monkeypatch.setattr(
            installer,
            "supplement_root_assets",
            fake_supplement,
        )

        external_skills.update_external_skill(
            workspace,
            skill,
            workspace.agents_dir / "skills",
            dry_run=True,
        )

        assert observed[0] == ("snapshot", revision)
        assert observed[1][0] == "install"
        assert observed[2] == ("assets", observed[1][1])


class TestExternalSkillService:
    """Verify registry orchestration and dry-run change reporting."""

    def test_missing_registry_is_clean(self, workspace: Workspace) -> None:
        """Test that an absent optional registry is a successful no-op."""

        assert external_skills.sync_external_skills(workspace, dry_run=True) is False

    def test_dry_run_reports_changes(
        self,
        monkeypatch: pytest.MonkeyPatch,
        workspace: Workspace,
        registry_file_factory: Callable[[SkillsRegistry], Path],
    ) -> None:
        """Test that changed external skills are reported by a dry run."""

        registry_file_factory(
            SkillsRegistry(
                skills=[
                    ExternalSkill(
                        name="sample",
                        repo="example/repository",
                        automatic_updates=True,
                    )
                ]
            )
        )

        def fake_update_external_skill(
            resolved_workspace: Workspace,
            skill: ExternalSkill,
            skills_dir: Path,
            dry_run: bool,
        ) -> bool:
            """Report one synthetic vendoring change."""

            return True

        monkeypatch.setattr(
            external_skills,
            "update_external_skill",
            fake_update_external_skill,
        )

        assert external_skills.sync_external_skills(workspace, dry_run=True) is True

    def test_disabled_automatic_updates_skip_vendoring(
        self,
        monkeypatch: pytest.MonkeyPatch,
        workspace: Workspace,
        registry_file_factory: Callable[[SkillsRegistry], Path],
    ) -> None:
        """Test that disabled entries leave existing local skills untouched."""

        registry_file_factory(
            SkillsRegistry(
                skills=[
                    ExternalSkill(
                        name="sample",
                        repo="example/repository",
                        automatic_updates=False,
                    )
                ]
            )
        )

        local_skill = workspace.agents_dir / "skills/sample/SKILL.md"
        local_skill.parent.mkdir(parents=True)
        local_skill.write_text("local\n")

        def fail_update(
            resolved_workspace: Workspace,
            skill: ExternalSkill,
            skills_dir: Path,
            dry_run: bool,
        ) -> bool:
            """Fail if a disabled skill reaches vendoring."""

            raise AssertionError("disabled skill must not be vendored")

        monkeypatch.setattr(external_skills, "update_external_skill", fail_update)

        assert external_skills.sync_external_skills(workspace, dry_run=False) is False
        assert local_skill.read_text() == "local\n"


class TestInstallerState:
    """Verify installer lock reading."""

    def test_reads_the_only_lock_entry(
        self,
        skills_lock_factory: Callable[..., Path],
    ) -> None:
        """Test that one lock entry resolves regardless of its key."""

        directory = skills_lock_factory("skills/sample/SKILL.md", key="upstream")

        assert installer.read_skill_path(directory) == "skills/sample/SKILL.md"
