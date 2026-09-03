import subprocess
import logging
from pathlib import Path

import pytest
from pydantic import ValidationError

from agent_sync.config import ACTION_CONFIG, ActionConfig
from agent_sync.external_skills import github, installer
from agent_sync.external_skills import sync
from agent_sync.models.registry import ExternalSkill, SkillsRegistry
from agent_sync.workspace import Workspace
from tests.factories import (
    ExternalSkillFactory,
    SkillsRegistryFactory,
    materialize_registry,
)


class TestExternalSkillModel:
    """Test that external-skill registry validation and defaults work."""

    def test_upstream_slug_defaults_to_local_name(self) -> None:
        """Test that an omitted upstream slug uses the local skill name."""

        skill = ExternalSkill(
            name="sample-skill",
            repo="example/sample-skill",
            update_on_sync=True,
        )

        assert skill.upstream_skill == "sample-skill"

    @pytest.mark.parametrize("name", ["Bad Name", "UPPER", "-leading", "sample\n"])
    def test_invalid_skill_names_fail(self, name: str) -> None:
        """Test that unsafe external skill names are rejected."""

        with pytest.raises(ValidationError):
            ExternalSkill(name=name, repo="example/sample", update_on_sync=True)

    @pytest.mark.parametrize("skill", ["Bad Name", "UPPER", "../escape"])
    def test_invalid_upstream_skill_names_fail(self, skill: str) -> None:
        """Test that unsafe upstream skill selectors are rejected."""

        with pytest.raises(ValidationError):
            ExternalSkill(
                name="sample",
                repo="example/sample",
                skill=skill,
                update_on_sync=True,
            )

    def test_update_on_sync_is_required(self) -> None:
        """Test that every registry entry chooses its update behavior explicitly."""

        with pytest.raises(ValidationError, match="update_on_sync"):
            ExternalSkill.model_validate({"name": "sample", "repo": "example/sample"})

    def test_duplicate_local_skill_names_fail(self) -> None:
        """Test that entries cannot silently overwrite one local skill directory."""

        with pytest.raises(ValidationError, match="names must be unique"):
            SkillsRegistry(
                skills=[
                    ExternalSkill(
                        name="sample",
                        repo="example/first",
                        update_on_sync=True,
                    ),
                    ExternalSkill(
                        name="sample",
                        repo="example/second",
                        update_on_sync=True,
                    ),
                ]
            )


class TestExternalSkillBoundaries:
    """Test that immutable GitHub snapshots and installer behavior work."""

    def test_runtime_config_accepts_namespaced_overrides(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that future CLI versions can be selected without code changes."""

        monkeypatch.setenv("AGENT_SYNC_SKILLS_CLI_VERSION", "9.9.9")
        monkeypatch.setenv("AGENT_SYNC_ROOT", "/tmp/consumer")
        monkeypatch.setenv("AGENT_SYNC_AGENTS_DIR", "agent-sources")

        config = ActionConfig()

        assert config.skills_cli_version == "9.9.9"
        assert config.root == Path("/tmp/consumer")
        assert config.agents_dir == "agent-sources"

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
            update_on_sync=True,
        )

        installer.install_skill(skill, tmp_path, source_root)

        assert str(source_root) in captured
        assert f"skills@{ACTION_CONFIG.skills_cli_version}" in captured
        assert captured[captured.index("-a") + 1] == installer.SKILLS_CLI_AGENT

    def test_installed_skill_discovery_is_provider_neutral(self, tmp_path: Path) -> None:
        """Test that staging discovery does not depend on one provider directory."""

        source_root = tmp_path / "source/repository"
        source_root.mkdir(parents=True)
        (source_root / "SKILL.md").write_text(
            "---\nname: source\ndescription: Source skill.\n---\n\nSource.\n"
        )

        installed = tmp_path / ".staging/skills/sample"
        installed.mkdir(parents=True)
        (installed / "SKILL.md").write_text(
            "---\nname: sample\ndescription: Installed skill.\n---\n\nInstalled.\n"
        )

        assert installer.locate_skill_directory(tmp_path, "sample", excluded_root=source_root) == installed

    def test_source_skill_discovery_uses_metadata_for_a_root_skill(
        self,
        tmp_path: Path,
    ) -> None:
        """Test that root skills are found among sibling skill documents."""

        (tmp_path / "SKILL.md").write_text("---\nname: root-skill\ndescription: Root skill.\n---\n\nRoot.\n")
        nested = tmp_path / "skills/nested"
        nested.mkdir(parents=True)
        (nested / "SKILL.md").write_text("---\nname: nested\ndescription: Nested skill.\n---\n\nNested.\n")

        assert installer.locate_skill_directory(tmp_path, "root-skill") == tmp_path

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
            update_on_sync=True,
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
            (source_root / "SKILL.md").write_text(
                "---\nname: sample\ndescription: A skill.\n---\n\nContent.\n"
            )

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
            (installed / "SKILL.md").write_text("---\nname: sample\ndescription: A skill.\n---\n\nContent.\n")

        monkeypatch.setattr(installer, "install_skill", fake_install)

        def fake_supplement(destination: Path, source_root: Path) -> None:
            """Record the snapshot used for supplemental assets."""

            observed.append(("assets", str(source_root)))

        monkeypatch.setattr(
            installer,
            "supplement_root_assets",
            fake_supplement,
        )

        sync.update_external_skill(
            workspace,
            skill,
            workspace.agents_dir / "skills",
            dry_run=True,
        )

        assert observed[0] == ("snapshot", revision)
        assert observed[1][0] == "install"
        assert observed[2] == ("assets", observed[1][1])

    def test_vendor_renames_upstream_metadata_for_the_local_directory(
        self,
        tmp_path: Path,
    ) -> None:
        """Test that a selected upstream slug becomes valid local canonical metadata."""

        installed = tmp_path / "react-best-practices"
        installed.mkdir()
        (installed / "SKILL.md").write_text(
            "---\n"
            "name: vercel-react-best-practices\n"
            "description: React guidance.\n"
            "metadata:\n"
            "  category: frontend\n"
            "---\n\n"
            "# React\n"
        )
        skill = ExternalSkill(
            name="react-best-practices",
            repo="vercel-labs/agent-skills",
            skill="vercel-react-best-practices",
            update_on_sync=True,
        )

        sync.normalize_skill_metadata(installed, skill)

        assert (installed / "SKILL.md").read_text() == (
            "---\n"
            "name: react-best-practices\n"
            "description: React guidance.\n"
            "metadata:\n"
            "  category: frontend\n"
            "  source: https://github.com/vercel-labs/agent-skills\n"
            "---\n\n"
            "# React\n"
        )

    def test_root_assets_do_not_restore_upstream_metadata(
        self,
        monkeypatch: pytest.MonkeyPatch,
        workspace: Workspace,
    ) -> None:
        """Test that root asset copying cannot undo the local metadata rewrite."""

        skill = ExternalSkill(
            name="local-skill",
            repo="example/repository",
            skill="upstream-skill",
            update_on_sync=True,
        )

        def fake_resolve(repository: str) -> str:
            """Return a stable synthetic revision."""

            return "a" * 40

        monkeypatch.setattr(github, "resolve_revision", fake_resolve)

        def fake_download(repository: str, revision: str, destination: Path) -> Path:
            """Create a root-level upstream skill document."""

            source_root = destination / "repository"
            source_root.mkdir(parents=True)
            (source_root / "SKILL.md").write_text(
                "---\nname: upstream-skill\ndescription: A skill.\n---\n\nContent.\n"
            )

            return source_root

        monkeypatch.setattr(github, "download_snapshot", fake_download)

        def fake_install(
            installed_skill: ExternalSkill,
            working_directory: Path,
            source_root: Path,
        ) -> None:
            """Create the installed skill before root assets are copied."""

            installed = working_directory / ".staging/skills" / installed_skill.name
            installed.mkdir(parents=True)
            (installed / "SKILL.md").write_text(
                "---\nname: upstream-skill\ndescription: A skill.\n---\n\nContent.\n"
            )

        monkeypatch.setattr(installer, "install_skill", fake_install)

        assert sync.update_external_skill(
            workspace,
            skill,
            workspace.agents_dir / "skills",
            dry_run=False,
        )
        assert (workspace.agents_dir / "skills/local-skill/SKILL.md").read_text() == (
            "---\n"
            "name: local-skill\n"
            "description: A skill.\n"
            "metadata:\n"
            "  source: https://github.com/example/repository\n"
            "---\n\n"
            "Content.\n"
        )

    def test_vendor_preserves_root_legal_files_for_nested_skills(
        self,
        monkeypatch: pytest.MonkeyPatch,
        workspace: Workspace,
    ) -> None:
        """Test that nested external skills retain repository legal files."""

        skill = ExternalSkillFactory.build()

        def fake_resolve(repository: str) -> str:
            """Return a stable synthetic revision."""

            return "a" * 40

        monkeypatch.setattr(github, "resolve_revision", fake_resolve)

        def fake_download(repository: str, revision: str, destination: Path) -> Path:
            """Create a nested synthetic skill and root license."""

            source_root = destination / "repository"
            source_skill = source_root / "skills/sample"
            source_skill.mkdir(parents=True)
            (source_skill / "SKILL.md").write_text(
                "---\nname: sample\ndescription: A skill.\n---\n\nContent.\n"
            )
            (source_root / "LICENSE").write_text("License text.\n")

            return source_root

        monkeypatch.setattr(github, "download_snapshot", fake_download)

        def fake_install(
            installed_skill: ExternalSkill,
            working_directory: Path,
            source_root: Path,
        ) -> None:
            """Create a synthetic installed skill."""

            installed = working_directory / ".staging/skills" / installed_skill.name
            installed.mkdir(parents=True)
            (installed / "SKILL.md").write_text("---\nname: sample\ndescription: A skill.\n---\n\nContent.\n")

        monkeypatch.setattr(installer, "install_skill", fake_install)

        assert sync.update_external_skill(
            workspace,
            skill,
            workspace.agents_dir / "skills",
            dry_run=False,
        )
        assert (workspace.agents_dir / "skills/sample/LICENSE").read_text() == "License text.\n"


class TestExternalSkillService:
    """Test that registry orchestration and dry-run change reporting work."""

    def test_missing_registry_is_clean(self, workspace: Workspace) -> None:
        """Test that an absent optional registry is a successful no-op."""

        assert sync.sync_external_skills(workspace, dry_run=True) is None

    def test_dry_run_reports_changes(
        self,
        caplog: pytest.LogCaptureFixture,
        monkeypatch: pytest.MonkeyPatch,
        workspace: Workspace,
    ) -> None:
        """Test that changed external skills are reported by a dry run."""

        caplog.set_level(logging.INFO)

        materialize_registry(
            workspace.agents_dir / "external_skills.json",
            SkillsRegistryFactory.build(skills=[ExternalSkillFactory.build()]),
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
            sync,
            "update_external_skill",
            fake_update_external_skill,
        )

        assert sync.sync_external_skills(workspace, dry_run=True) is None
        assert "sample (example/repository): would update" in caplog.text

    def test_disabled_update_on_sync_skips_vendoring(
        self,
        monkeypatch: pytest.MonkeyPatch,
        workspace: Workspace,
    ) -> None:
        """Test that disabled entries leave existing local skills untouched."""

        materialize_registry(
            workspace.agents_dir / "external_skills.json",
            SkillsRegistryFactory.build(skills=[ExternalSkillFactory.build(update_on_sync=False)]),
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

        monkeypatch.setattr(sync, "update_external_skill", fail_update)

        assert sync.sync_external_skills(workspace, dry_run=False) is None
        assert local_skill.read_text() == "local\n"
