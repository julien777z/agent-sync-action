import subprocess
from pathlib import Path

import pytest

from agent_sync.config import ACTION_CONFIG, ActionConfig
from agent_sync.external_skills import github, installer
from agent_sync.external_skills import sync
from agent_sync.models.registry import ExternalSkill
from agent_sync.workspace import Workspace
from tests.factories import (
    ExternalSkillFactory,
    SkillFrontMatterFactory,
    materialize_skill,
    ROOT_LEVEL_SKILL,
    stub_root_level_upstream,
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
            "  folder: frontend\n"
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
            "  folder: frontend\n"
            "  source: https://github.com/vercel-labs/agent-skills\n"
            "---\n\n"
            "# React\n"
        )

    def test_vendor_drops_provider_ui_metadata(self, tmp_path: Path) -> None:
        """Test that OpenAI metadata is removed without discarding other skill assets."""

        installed = tmp_path / "renamed-skill"
        installed.mkdir()
        (installed / "SKILL.md").write_text("---\nname: original\ndescription: A skill.\n---\n")
        provider_file = installed / "agents/openai.yaml"
        provider_file.parent.mkdir()
        provider_file.write_text('display_name: "/original"\n')
        other_asset = provider_file.parent / "guide.md"
        other_asset.write_text("Skill reference.\n")
        skill = ExternalSkill(
            name="original",
            skill_name_override="renamed-skill",
            repo="example/repository",
            update_on_sync=True,
        )

        sync.normalize_skill_metadata(installed, skill)

        assert "name: renamed-skill\n" in (installed / "SKILL.md").read_text()
        assert not provider_file.exists()
        assert other_asset.read_text() == "Skill reference.\n"

    def test_root_assets_do_not_restore_upstream_metadata(
        self,
        monkeypatch: pytest.MonkeyPatch,
        workspace: Workspace,
    ) -> None:
        """Test that root asset copying cannot undo the local metadata rewrite."""

        stub_root_level_upstream(monkeypatch)

        assert sync.update_external_skill(
            workspace,
            ROOT_LEVEL_SKILL,
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

    def test_vendor_installs_a_new_skill_into_its_declared_category(
        self,
        monkeypatch: pytest.MonkeyPatch,
        workspace: Workspace,
    ) -> None:
        """Test that a first install lands in the folder the registry declares."""

        stub_root_level_upstream(monkeypatch)
        skill = ROOT_LEVEL_SKILL.model_copy(update={"category": "review/style"})

        assert sync.update_external_skill(workspace, skill, workspace.agents_dir / "skills", dry_run=False)
        assert "Content." in (workspace.agents_dir / "skills/review/style/local-skill/SKILL.md").read_text()
        assert not (workspace.agents_dir / "skills/local-skill").exists()

    def test_vendor_renames_an_existing_skill_with_an_override(
        self,
        monkeypatch: pytest.MonkeyPatch,
        workspace: Workspace,
    ) -> None:
        stub_root_level_upstream(monkeypatch)
        skills_dir = workspace.agents_dir / "skills"
        previous = skills_dir / "review/local-skill"
        materialize_skill(
            previous / "SKILL.md",
            SkillFrontMatterFactory.build(
                name=ROOT_LEVEL_SKILL.name,
                metadata={"source": f"https://github.com/{ROOT_LEVEL_SKILL.repo}"},
            ),
            body="Old.",
        )
        skill = ROOT_LEVEL_SKILL.model_copy(
            update={"category": "review", "skill_name_override": "renamed-skill"}
        )

        assert sync.update_external_skill(workspace, skill, skills_dir, dry_run=False)
        renamed = skills_dir / "review/renamed-skill/SKILL.md"
        assert "name: renamed-skill\n" in renamed.read_text()
        assert not previous.exists()

    def test_vendor_updates_a_skill_in_its_declared_folder(
        self,
        monkeypatch: pytest.MonkeyPatch,
        workspace: Workspace,
    ) -> None:
        """Test that a skill already in its declared folder is refreshed where it is."""

        stub_root_level_upstream(monkeypatch)
        skill = ROOT_LEVEL_SKILL.model_copy(update={"category": "review"})
        grouped = workspace.agents_dir / "skills/review/local-skill"
        materialize_skill(
            grouped / "SKILL.md",
            SkillFrontMatterFactory.build(
                name=ROOT_LEVEL_SKILL.name,
                metadata={"source": f"https://github.com/{ROOT_LEVEL_SKILL.repo}"},
            ),
            body="Old.",
        )

        assert sync.update_external_skill(workspace, skill, workspace.agents_dir / "skills", dry_run=False)
        assert "Content." in (grouped / "SKILL.md").read_text()
        assert not (workspace.agents_dir / "skills/local-skill").exists()

    def test_occupied_destination_preserves_existing_skill(
        self,
        monkeypatch: pytest.MonkeyPatch,
        workspace: Workspace,
    ) -> None:
        """Reject a move into an occupied destination without removing either directory."""

        stub_root_level_upstream(monkeypatch)
        skills_dir = workspace.agents_dir / "skills"
        current = skills_dir / ROOT_LEVEL_SKILL.local_name / "SKILL.md"
        materialize_skill(
            current,
            SkillFrontMatterFactory.build(
                name=ROOT_LEVEL_SKILL.local_name,
                metadata={"source": f"https://github.com/{ROOT_LEVEL_SKILL.repo}"},
            ),
        )
        original = current.read_text()
        destination = skills_dir / "review" / ROOT_LEVEL_SKILL.local_name
        destination.mkdir(parents=True)
        marker = destination / "unrelated.txt"
        marker.write_text("keep\n")
        skill = ROOT_LEVEL_SKILL.model_copy(update={"category": "review"})

        with pytest.raises(RuntimeError, match="destination already exists"):
            sync.update_external_skill(workspace, skill, skills_dir, dry_run=False)

        assert current.read_text() == original
        assert marker.read_text() == "keep\n"

    def test_unmanaged_same_name_preserves_existing_skill(
        self,
        monkeypatch: pytest.MonkeyPatch,
        workspace: Workspace,
    ) -> None:
        """Test that an unmanaged same-named skill survives a registry refresh."""

        stub_root_level_upstream(monkeypatch)
        skills_dir = workspace.agents_dir / "skills"
        current = skills_dir / ROOT_LEVEL_SKILL.local_name / "SKILL.md"
        materialize_skill(current, SkillFrontMatterFactory.build(name=ROOT_LEVEL_SKILL.local_name))
        original = current.read_text()
        skill = ROOT_LEVEL_SKILL.model_copy(update={"category": "review"})

        with pytest.raises(RuntimeError, match="not managed"):
            sync.update_external_skill(workspace, skill, skills_dir, dry_run=False)

        assert current.read_text() == original
        assert not (skills_dir / "review" / ROOT_LEVEL_SKILL.local_name).exists()

    def test_linked_same_name_preserves_existing_skill(
        self,
        monkeypatch: pytest.MonkeyPatch,
        workspace: Workspace,
    ) -> None:
        """Test that a linked skill cannot be claimed as a managed installation."""

        stub_root_level_upstream(monkeypatch)
        skills_dir = workspace.agents_dir / "skills"
        source = workspace.root / "linked-skill" / "SKILL.md"
        materialize_skill(
            source,
            SkillFrontMatterFactory.build(
                name=ROOT_LEVEL_SKILL.local_name,
                metadata={"source": f"https://github.com/{ROOT_LEVEL_SKILL.repo}"},
            ),
        )
        link = skills_dir / ROOT_LEVEL_SKILL.local_name
        skills_dir.mkdir(parents=True, exist_ok=True)
        link.symlink_to(source.parent, target_is_directory=True)
        skill = ROOT_LEVEL_SKILL.model_copy(update={"category": "review"})

        with pytest.raises(RuntimeError, match="not a managed installation"):
            sync.update_external_skill(workspace, skill, skills_dir, dry_run=False)

        assert link.is_symlink()
        assert source.exists()

    @pytest.mark.parametrize(
        ("current", "category", "expected"),
        [
            ("local-skill", "review", "review/local-skill"),
            ("review/local-skill", None, "local-skill"),
            ("review/local-skill", "authoring", "authoring/local-skill"),
        ],
    )
    def test_vendor_moves_a_skill_to_its_declared_folder(
        self,
        monkeypatch: pytest.MonkeyPatch,
        workspace: Workspace,
        current: str,
        category: str | None,
        expected: str,
    ) -> None:
        """Test that the registry's folder wins over wherever the skill currently sits."""

        stub_root_level_upstream(monkeypatch)
        skill = ROOT_LEVEL_SKILL.model_copy(update={"category": category})
        skills_dir = workspace.agents_dir / "skills"
        stray = skills_dir / current
        stray.mkdir(parents=True)
        (stray / "SKILL.md").write_text(
            "---\nname: local-skill\ndescription: A skill.\nmetadata:\n"
            "  source: https://github.com/example/repository\n---\n\nContent.\n"
        )

        assert sync.update_external_skill(workspace, skill, skills_dir, dry_run=False)
        assert "Content." in (skills_dir / expected / "SKILL.md").read_text()
        assert list(skills_dir.rglob("SKILL.md")) == [skills_dir / expected / "SKILL.md"]
        assert all(any(path.iterdir()) for path in skills_dir.rglob("*") if path.is_dir())

    def test_moving_a_skill_keeps_a_folder_that_still_holds_others(
        self,
        monkeypatch: pytest.MonkeyPatch,
        workspace: Workspace,
    ) -> None:
        """Test that only folders the move emptied are removed."""

        stub_root_level_upstream(monkeypatch)
        skills_dir = workspace.agents_dir / "skills"
        for name in ("local-skill", "neighbour"):
            materialize_skill(
                skills_dir / "review" / name / "SKILL.md",
                SkillFrontMatterFactory.build(
                    name=name,
                    metadata=(
                        {"source": f"https://github.com/{ROOT_LEVEL_SKILL.repo}"}
                        if name == ROOT_LEVEL_SKILL.name
                        else None
                    ),
                ),
            )

        assert sync.update_external_skill(workspace, ROOT_LEVEL_SKILL, skills_dir, dry_run=False)
        assert (skills_dir / "local-skill/SKILL.md").exists()
        assert not (skills_dir / "review/local-skill").exists()
        assert (skills_dir / "review/neighbour/SKILL.md").exists()

    def test_dry_run_reports_a_pending_move_without_moving(
        self,
        monkeypatch: pytest.MonkeyPatch,
        workspace: Workspace,
    ) -> None:
        """Test that a dry run reports an identical skill in the wrong folder as a change."""

        stub_root_level_upstream(monkeypatch)
        skills_dir = workspace.agents_dir / "skills"
        stray = skills_dir / "local-skill"
        stray.mkdir(parents=True)
        (stray / "SKILL.md").write_text(
            "---\nname: local-skill\ndescription: A skill.\nmetadata:\n"
            "  source: https://github.com/example/repository\n---\n\nContent.\n"
        )
        skill = ROOT_LEVEL_SKILL.model_copy(update={"category": "review"})

        assert sync.update_external_skill(workspace, skill, skills_dir, dry_run=True)
        assert (stray / "SKILL.md").exists()
        assert not (skills_dir / "review").exists()

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
