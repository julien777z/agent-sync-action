import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest

from agent_sync.config import ActionConfig
from agent_sync.models.vendors.skills_cli import SkillsCliVendor, VendoredSkill
from agent_sync.vendors.skills_cli import assets, discovery, github, installer, sync
from agent_sync.workspace import Workspace
from tests.factories import (
    SOURCE_SKILL,
    SkillsCliVendorFactory,
    VendoredSkillFactory,
    materialize_tree,
)


class TestSkillsCliBoundaries:
    """Test that immutable GitHub snapshots and installer behavior work."""

    def test_config_accepts_namespaced_overrides(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that workspace locations can be selected without code changes."""

        monkeypatch.setenv("AGENT_SYNC_ROOT", "/tmp/consumer")
        monkeypatch.setenv("AGENT_SYNC_AGENTS_DIR", "agent-sources")

        config = ActionConfig()

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

    @pytest.mark.parametrize(
        ("skills_path", "expected_suffix"),
        [(None, "source"), ("skills", "source/skills")],
        ids=["repository-root", "registered-subdirectory"],
    )
    def test_installer_searches_registered_path(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        skills_path: str | None,
        expected_suffix: str,
    ) -> None:
        """Test that the installer receives the directory holding the upstream skill."""

        source_root = tmp_path / "source"
        materialize_tree(source_root, {"skills/sample/SKILL.md": SOURCE_SKILL})
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
        vendor = SkillsCliVendorFactory.build(cli_version="9.9.9")
        skill = VendoredSkillFactory.build(skills_path=skills_path)

        search_root = installer.resolve_search_root(source_root, skill)
        installer.install_skill(vendor, skill, tmp_path / "install", search_root)

        assert search_root == tmp_path / expected_suffix
        assert str(search_root) in captured
        assert "skills@9.9.9" in captured
        assert captured[captured.index("-a") + 1] == installer.SKILLS_CLI_AGENT

    def test_configured_version_reaches_installer(
        self,
        configure_action: Callable[..., None],
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """Test that a vendor without its own pin runs the configured version."""

        configure_action(skills_cli_version="9.9.9")
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

        installer.install_skill(
            SkillsCliVendor(),
            VendoredSkillFactory.build(),
            tmp_path / "install",
            tmp_path,
        )

        assert "skills@9.9.9" in captured

    def test_missing_skills_path_fails(self, tmp_path: Path) -> None:
        """Test that a registered directory absent upstream is reported by name."""

        skill = VendoredSkillFactory.build(skills_path="packages/skills")

        with pytest.raises(RuntimeError, match="packages/skills"):
            installer.resolve_search_root(tmp_path, skill)

    def test_installed_discovery_is_provider_neutral(self, tmp_path: Path) -> None:
        """Test that staging discovery does not depend on one provider directory."""

        materialize_tree(
            tmp_path,
            {
                ".staging/skills/sample/SKILL.md": (
                    "---\nname: sample\ndescription: Installed skill.\n---\n\nInstalled.\n"
                )
            },
        )

        located = discovery.locate_skill_directory(tmp_path, "sample")

        assert located == tmp_path / ".staging/skills/sample"

    @pytest.mark.parametrize(
        ("document", "expected"),
        [
            (None, False),
            ("---\nname: sample\ndescription: A skill.\n---\n\nContent.\n", True),
            ("---\nname: other\ndescription: A skill.\n---\n\nContent.\n", False),
        ],
        ids=["no-document", "selected-skill", "different-skill"],
    )
    def test_root_detection_matches_selector(
        self,
        tmp_path: Path,
        document: str | None,
        expected: bool,
    ) -> None:
        """Test that a search root counts as the skill only when it is the selected one."""

        if document is not None:
            materialize_tree(tmp_path, {"SKILL.md": document})

        assert discovery.is_search_root_skill(tmp_path, VendoredSkillFactory.build()) is expected

    def test_vendor_renames_metadata_locally(
        self,
        tmp_path: Path,
    ) -> None:
        """Test that a selected upstream slug becomes valid local canonical metadata."""

        installed = tmp_path / "react-best-practices"
        materialize_tree(
            installed,
            {
                "SKILL.md": (
                    "---\n"
                    "name: vercel-react-best-practices\n"
                    "description: React guidance.\n"
                    "metadata:\n"
                    "  category: frontend\n"
                    "---\n\n"
                    "# React\n"
                )
            },
        )
        skill = VendoredSkill(
            name="react-best-practices",
            repo="vercel-labs/agent-skills",
            skill="vercel-react-best-practices",
            update_on_sync=True,
        )

        assets.normalize_skill_metadata(installed, skill)

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


class TestSkillsCliVendoring:
    """Test that snapshots resolve the registered upstream tree and its assets."""

    def test_mirrored_slugs_vendor_registered_tree(
        self,
        snapshot: Path,
        workspace: Workspace,
    ) -> None:
        """Test that a repository mirroring one slug vendors the registered copy."""

        materialize_tree(
            snapshot,
            {
                "skills/sample/SKILL.md": "---\nname: sample\ndescription: A.\n---\n\nCanonical.\n",
                ".agents/skills/sample/SKILL.md": "---\nname: sample\ndescription: A.\n---\n\nMirror.\n",
                ".kiro/skills/sample/SKILL.md": "---\nname: sample\ndescription: A.\n---\n\nKiro.\n",
                "docs/es/skills/sample/SKILL.md": (
                    "---\nname: sample\ndescription: A.\n---\n\nTranslation.\n"
                ),
                "LICENSE": "License text.\n",
            },
        )

        vendor = SkillsCliVendorFactory.build(skills=[VendoredSkillFactory.build(skills_path="skills")])

        assert sync.install_skills_cli_vendor(workspace, vendor, dry_run=False).paths == [
            ".agents/skills/sample"
        ]

        vendored = workspace.agents_dir / "skills/sample"

        assert "Canonical." in (vendored / "SKILL.md").read_text()
        assert (vendored / "LICENSE").read_text() == "License text.\n"

    def test_nested_skill_excludes_root_files(
        self,
        snapshot: Path,
        workspace: Workspace,
    ) -> None:
        """Test that repository-root content stays out of a nested vendored skill."""

        materialize_tree(
            snapshot,
            {
                "skills/sample/SKILL.md": SOURCE_SKILL,
                "README.md": "Repository readme.\n",
                "LICENSE": "License text.\n",
            },
        )

        vendor = SkillsCliVendorFactory.build(skills=[VendoredSkillFactory.build(skills_path="skills")])
        sync.install_skills_cli_vendor(workspace, vendor, dry_run=False)

        vendored = workspace.agents_dir / "skills/sample"

        assert sorted(path.name for path in vendored.iterdir()) == ["LICENSE", "SKILL.md"]

    def test_root_skill_supplements_own_assets(
        self,
        snapshot: Path,
        workspace: Workspace,
    ) -> None:
        """Test that a repository that is itself one skill keeps its supporting files."""

        materialize_tree(snapshot, {"SKILL.md": SOURCE_SKILL, "reference.md": "Reference.\n"})

        vendor = SkillsCliVendorFactory.build(skills=[VendoredSkillFactory.build()])
        sync.install_skills_cli_vendor(workspace, vendor, dry_run=False)

        assert (workspace.agents_dir / "skills/sample/reference.md").read_text() == "Reference.\n"

    def test_one_snapshot_serves_whole_repository(
        self,
        monkeypatch: pytest.MonkeyPatch,
        snapshot: Path,
        workspace: Workspace,
    ) -> None:
        """Test that skills sharing a repository resolve one revision and one download."""

        resolved: list[str] = []
        downloaded: list[str] = []

        def fake_resolve(repository: str) -> str:
            """Record one revision lookup."""

            resolved.append(repository)

            return "a" * 40

        def fake_download(repository: str, revision: str, destination: Path) -> Path:
            """Record one snapshot download and build it."""

            downloaded.append(repository)
            source_root = destination / "repository"
            materialize_tree(
                source_root,
                {
                    "skills/sample/SKILL.md": SOURCE_SKILL,
                    "skills/other/SKILL.md": "---\nname: other\ndescription: B.\n---\n\nB.\n",
                },
            )

            return source_root

        monkeypatch.setattr(github, "resolve_revision", fake_resolve)
        monkeypatch.setattr(github, "download_snapshot", fake_download)

        vendor = SkillsCliVendorFactory.build(
            skills=[
                VendoredSkillFactory.build(name="sample", skills_path="skills"),
                VendoredSkillFactory.build(name="other", skills_path="skills"),
            ]
        )
        sync.install_skills_cli_vendor(workspace, vendor, dry_run=False)

        assert resolved == ["example/repository"]
        assert downloaded == ["example/repository"]
        assert (workspace.agents_dir / "skills/sample/SKILL.md").is_file()
        assert (workspace.agents_dir / "skills/other/SKILL.md").is_file()

    def test_dry_run_reports_without_writing(
        self,
        snapshot: Path,
        workspace: Workspace,
    ) -> None:
        """Test that a dry run reports a pending change and leaves sources untouched."""

        materialize_tree(snapshot, {"skills/sample/SKILL.md": SOURCE_SKILL})
        vendor = SkillsCliVendorFactory.build(skills=[VendoredSkillFactory.build(skills_path="skills")])

        assert sync.install_skills_cli_vendor(workspace, vendor, dry_run=True).differences_found is True
        assert not (workspace.agents_dir / "skills").exists()
