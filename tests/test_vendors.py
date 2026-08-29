import subprocess
from pathlib import Path

import pytest
from pydantic import ValidationError

from agent_sync.config import ActionConfig
from agent_sync.models.vendors import (
    EccVendor,
    SkillsCliVendor,
    VendoredSkill,
    VendorRegistry,
    Vendors,
)
from agent_sync.vendors import ecc, github, runner, skills_cli
from agent_sync.workspace import Workspace
from tests.factories import (
    EccVendorFactory,
    SkillsCliVendorFactory,
    VendoredSkillFactory,
    VendorRegistryFactory,
    materialize_registry,
)

SOURCE_SKILL = "---\nname: sample\ndescription: A skill.\n---\n\nContent.\n"


def write_skill(directory: Path, document: str = SOURCE_SKILL) -> Path:
    """Write one synthetic skill document and return its directory."""

    directory.mkdir(parents=True, exist_ok=True)
    (directory / "SKILL.md").write_text(document, encoding="utf-8")

    return directory


class TestVendoredSkillModel:
    """Test that vendored-skill validation and defaults work."""

    def test_upstream_slug_defaults_to_local_name(self) -> None:
        """Test that an omitted upstream slug uses the local skill name."""

        skill = VendoredSkill(
            name="sample-skill",
            repo="example/sample-skill",
            update_on_sync=True,
        )

        assert skill.upstream_skill == "sample-skill"
        assert skill.skills_path is None

    @pytest.mark.parametrize("name", ["Bad Name", "UPPER", "-leading", "sample\n"])
    def test_invalid_skill_names_fail(self, name: str) -> None:
        """Test that unsafe vendored skill names are rejected."""

        with pytest.raises(ValidationError):
            VendoredSkill(name=name, repo="example/sample", update_on_sync=True)

    @pytest.mark.parametrize("skill", ["Bad Name", "UPPER", "../escape"])
    def test_invalid_upstream_skill_names_fail(self, skill: str) -> None:
        """Test that unsafe upstream skill selectors are rejected."""

        with pytest.raises(ValidationError):
            VendoredSkill(
                name="sample",
                repo="example/sample",
                skill=skill,
                update_on_sync=True,
            )

    @pytest.mark.parametrize(
        "skills_path",
        ["/skills", "../skills", "skills/..", "skills/", ".hidden", "skills dir", ""],
    )
    def test_invalid_skills_paths_fail(self, skills_path: str) -> None:
        """Test that unsafe upstream skill directories are rejected."""

        with pytest.raises(ValidationError):
            VendoredSkill(
                name="sample",
                repo="example/sample",
                skills_path=skills_path,
                update_on_sync=True,
            )

    @pytest.mark.parametrize("skills_path", ["skills", "packages/skills", "skills.v2"])
    def test_valid_skills_paths_are_accepted(self, skills_path: str) -> None:
        """Test that ordinary upstream directory names are accepted."""

        skill = VendoredSkill(
            name="sample",
            repo="example/sample",
            skills_path=skills_path,
            update_on_sync=True,
        )

        assert skill.skills_path == skills_path

    def test_update_on_sync_is_required(self) -> None:
        """Test that every skill entry chooses its update behavior explicitly."""

        with pytest.raises(ValidationError, match="update_on_sync"):
            VendoredSkill.model_validate({"name": "sample", "repo": "example/sample"})

    def test_duplicate_local_skill_names_fail(self) -> None:
        """Test that entries cannot silently overwrite one local skill directory."""

        with pytest.raises(ValidationError, match="names must be unique"):
            SkillsCliVendor(
                skills=[
                    VendoredSkill(name="sample", repo="example/first", update_on_sync=True),
                    VendoredSkill(name="sample", repo="example/second", update_on_sync=True),
                ]
            )


class TestVendorRegistryModel:
    """Test that the vendor registry accepts supported vendors and rejects others."""

    def test_registry_accepts_every_supported_vendor(self) -> None:
        """Test that both supported vendors can be configured together."""

        registry = VendorRegistry.model_validate(
            {
                "version": 1,
                "vendors": {
                    "skills-cli": {"update_on_sync": True, "skills": []},
                    "ecc": {"update_on_sync": True, "profile": "core"},
                },
            }
        )

        assert registry.vendors.skills_cli is not None
        assert registry.vendors.ecc is not None
        assert registry.vendors.ecc.profile == "core"

    def test_unknown_vendor_names_fail(self) -> None:
        """Test that an unsupported vendor name is rejected rather than ignored."""

        with pytest.raises(ValidationError, match="unsupported-vendor"):
            VendorRegistry.model_validate(
                {"version": 1, "vendors": {"unsupported-vendor": {"update_on_sync": True}}}
            )

    def test_undeclared_vendors_are_absent(self) -> None:
        """Test that a registry declaring one vendor leaves the others unset."""

        registry = VendorRegistry.model_validate({"version": 1, "vendors": {"ecc": {}}})

        assert registry.vendors.skills_cli is None

    def test_registry_round_trips_through_its_serialized_keys(self) -> None:
        """Test that a serialized registry validates back into the same configuration."""

        registry = VendorRegistryFactory.build(
            vendors=Vendors(skills_cli=SkillsCliVendorFactory.build(), ecc=EccVendorFactory.build())
        )

        assert VendorRegistry.model_validate_json(registry.model_dump_json(by_alias=True)) == registry


class TestEccVendor:
    """Test that ECC selective-install invocations are built and guarded correctly."""

    def test_profile_only_selection_builds_a_minimal_command(self) -> None:
        """Test that a profile-only configuration passes just its profile."""

        command = ecc.build_command(EccVendorFactory.build(), dry_run=False)

        assert command[:4] == ["npx", "--yes", f"{ecc.ECC_PACKAGE}@latest", "install"]
        assert command[command.index("--target") + 1] == "antigravity"
        assert command[command.index("--profile") + 1] == "core"
        assert "--modules" not in command
        assert "--skills" not in command
        assert command[-1] == "--json"

    def test_modules_and_skills_are_passed_as_comma_lists(self) -> None:
        """Test that explicit module and skill selections reach the installer."""

        vendor = EccVendorFactory.build(modules=["security", "database"], skills=["deep-research"])

        command = ecc.build_command(vendor, dry_run=False)

        assert command[command.index("--modules") + 1] == "security,database"
        assert command[command.index("--skills") + 1] == "deep-research"

    def test_dry_run_forwards_the_installer_dry_run(self) -> None:
        """Test that a dry run never asks the installer to write files."""

        assert "--dry-run" in ecc.build_command(EccVendorFactory.build(), dry_run=True)

    @pytest.mark.parametrize("field", ["modules", "skills"])
    def test_unsafe_selectors_fail(self, field: str) -> None:
        """Test that unsafe module and skill IDs are rejected before invocation."""

        with pytest.raises(ValidationError):
            EccVendor.model_validate({field: ["../escape"]})

    def test_mismatched_canonical_directory_fails(self, tmp_path: Path) -> None:
        """Test that a target writing outside canonical sources is refused."""

        workspace = Workspace(root=tmp_path, agents_dirname="agent-sources")

        with pytest.raises(RuntimeError, match="agent-sources"):
            ecc.assert_target_writes_to_workspace(workspace, EccVendorFactory.build())

    def test_a_failing_installer_surfaces_its_output(
        self,
        monkeypatch: pytest.MonkeyPatch,
        workspace: Workspace,
    ) -> None:
        """Test that installer failures report the captured diagnostics."""

        def fake_run(
            command: list[str],
            *,
            cwd: Path,
            capture_output: bool,
            text: bool,
            check: bool,
        ) -> subprocess.CompletedProcess[str]:
            """Return a failed installer invocation."""

            return subprocess.CompletedProcess(command, 1, "planned nothing", "unknown profile")

        monkeypatch.setattr(ecc.subprocess, "run", fake_run)

        with pytest.raises(RuntimeError, match="unknown profile"):
            ecc.install_ecc_vendor(workspace, EccVendorFactory.build(), dry_run=False)

    def test_operation_counts_come_from_installer_output(self) -> None:
        """Test that reported operation counts are read from the installer's own plan."""

        assert ecc.count_operations('{"dryRun": true, "plan": {"operations": [1, 2, 3]}}') == 3
        assert ecc.count_operations('{"dryRun": false, "result": {"operations": [1]}}') == 1
        assert ecc.count_operations("not json") == 0

    @pytest.mark.parametrize("dry_run", [True, False], ids=["dry-run", "applied"])
    def test_local_install_state_is_not_kept(
        self,
        monkeypatch: pytest.MonkeyPatch,
        workspace: Workspace,
        dry_run: bool,
    ) -> None:
        """Test that an applied install leaves no machine-specific state in canonical sources."""

        install_state = workspace.agents_dir / ecc.INSTALL_STATE_FILENAME
        install_state.write_text('{"installedAt": "2026-01-01T00:00:00.000Z"}', encoding="utf-8")

        def fake_run(
            command: list[str],
            *,
            cwd: Path,
            capture_output: bool,
            text: bool,
            check: bool,
        ) -> subprocess.CompletedProcess[str]:
            """Return a successful installer invocation."""

            return subprocess.CompletedProcess(command, 0, '{"plan": {"operations": []}}', "")

        monkeypatch.setattr(ecc.subprocess, "run", fake_run)

        ecc.install_ecc_vendor(workspace, EccVendorFactory.build(), dry_run=dry_run)

        assert install_state.exists() is dry_run


class TestSkillsCliBoundaries:
    """Test that immutable GitHub snapshots and installer behavior work."""

    def test_runtime_config_accepts_namespaced_overrides(
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
    def test_installer_searches_the_registered_skills_path(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        skills_path: str | None,
        expected_suffix: str,
    ) -> None:
        """Test that the installer receives the directory holding the upstream skill."""

        source_root = tmp_path / "source"
        write_skill(source_root / "skills/sample")
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

        monkeypatch.setattr(skills_cli.subprocess, "run", fake_run)
        vendor = SkillsCliVendorFactory.build(cli_version="9.9.9")
        skill = VendoredSkillFactory.build(skills_path=skills_path)

        search_root = skills_cli.resolve_search_root(source_root, skill)
        skills_cli.install_skill(vendor, skill, tmp_path / "install", search_root)

        assert search_root == tmp_path / expected_suffix
        assert str(search_root) in captured
        assert "skills@9.9.9" in captured
        assert captured[captured.index("-a") + 1] == skills_cli.SKILLS_CLI_AGENT

    def test_a_missing_skills_path_fails(self, tmp_path: Path) -> None:
        """Test that a registered directory absent upstream is reported by name."""

        skill = VendoredSkillFactory.build(skills_path="packages/skills")

        with pytest.raises(RuntimeError, match="packages/skills"):
            skills_cli.resolve_search_root(tmp_path, skill)

    def test_installed_skill_discovery_is_provider_neutral(self, tmp_path: Path) -> None:
        """Test that staging discovery does not depend on one provider directory."""

        installed = write_skill(
            tmp_path / ".staging/skills/sample",
            "---\nname: sample\ndescription: Installed skill.\n---\n\nInstalled.\n",
        )

        assert skills_cli.locate_skill_directory(tmp_path, "sample") == installed

    @pytest.mark.parametrize(
        ("document", "expected"),
        [
            (None, False),
            ("---\nname: sample\ndescription: A skill.\n---\n\nContent.\n", True),
            ("---\nname: other\ndescription: A skill.\n---\n\nContent.\n", False),
        ],
        ids=["no-document", "selected-skill", "different-skill"],
    )
    def test_root_skill_detection_matches_the_upstream_selector(
        self,
        tmp_path: Path,
        document: str | None,
        expected: bool,
    ) -> None:
        """Test that a search root counts as the skill only when it is the selected one."""

        if document is not None:
            (tmp_path / "SKILL.md").write_text(document, encoding="utf-8")

        assert skills_cli.is_search_root_skill(tmp_path, VendoredSkillFactory.build()) is expected

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
        skill = VendoredSkill(
            name="react-best-practices",
            repo="vercel-labs/agent-skills",
            skill="vercel-react-best-practices",
            update_on_sync=True,
        )

        skills_cli.normalize_skill_metadata(installed, skill)

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

    @pytest.fixture
    def snapshot(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
        """Install fakes that serve one synthetic snapshot to the vendoring path."""

        source_root = tmp_path / "snapshot"
        source_root.mkdir()

        def fake_resolve(repository: str) -> str:
            """Return a stable synthetic revision."""

            return "a" * 40

        def fake_download(repository: str, revision: str, destination: Path) -> Path:
            """Return the prepared synthetic snapshot."""

            return source_root

        def fake_install(
            vendor: SkillsCliVendor,
            skill: VendoredSkill,
            install_directory: Path,
            search_root: Path,
        ) -> None:
            """Copy the resolved upstream skill the way the installer would."""

            located = skills_cli.locate_skill_directory(search_root, skill.upstream_skill)
            write_skill(
                install_directory / ".staging/skills" / skill.name,
                (located / "SKILL.md").read_text(encoding="utf-8"),
            )

        monkeypatch.setattr(github, "resolve_revision", fake_resolve)
        monkeypatch.setattr(github, "download_snapshot", fake_download)
        monkeypatch.setattr(skills_cli, "install_skill", fake_install)

        return source_root

    def test_mirrored_skill_slugs_vendor_the_registered_tree(
        self,
        snapshot: Path,
        workspace: Workspace,
    ) -> None:
        """Test that a repository mirroring one slug vendors the registered copy."""

        write_skill(snapshot / "skills/sample", "---\nname: sample\ndescription: A.\n---\n\nCanonical.\n")
        write_skill(
            snapshot / ".agents/skills/sample",
            "---\nname: sample\ndescription: A.\n---\n\nMirror.\n",
        )
        write_skill(
            snapshot / "docs/es/skills/sample",
            "---\nname: sample\ndescription: A.\n---\n\nTranslation.\n",
        )
        (snapshot / "LICENSE").write_text("License text.\n", encoding="utf-8")

        vendor = SkillsCliVendorFactory.build(skills=[VendoredSkillFactory.build(skills_path="skills")])

        assert skills_cli.install_skills_cli_vendor(workspace, vendor, dry_run=False) is False

        vendored = workspace.agents_dir / "skills/sample"

        assert "Canonical." in (vendored / "SKILL.md").read_text()
        assert (vendored / "LICENSE").read_text() == "License text.\n"

    def test_a_nested_skill_does_not_absorb_repository_root_files(
        self,
        snapshot: Path,
        workspace: Workspace,
    ) -> None:
        """Test that repository-root content stays out of a nested vendored skill."""

        write_skill(snapshot / "skills/sample")
        (snapshot / "README.md").write_text("Repository readme.\n", encoding="utf-8")
        (snapshot / "LICENSE").write_text("License text.\n", encoding="utf-8")

        vendor = SkillsCliVendorFactory.build(skills=[VendoredSkillFactory.build(skills_path="skills")])
        skills_cli.install_skills_cli_vendor(workspace, vendor, dry_run=False)

        vendored = workspace.agents_dir / "skills/sample"

        assert sorted(path.name for path in vendored.iterdir()) == ["LICENSE", "SKILL.md"]

    def test_a_root_skill_supplements_its_own_assets(
        self,
        snapshot: Path,
        workspace: Workspace,
    ) -> None:
        """Test that a repository that is itself one skill keeps its supporting files."""

        write_skill(snapshot)
        (snapshot / "reference.md").write_text("Reference.\n", encoding="utf-8")

        vendor = SkillsCliVendorFactory.build(skills=[VendoredSkillFactory.build()])
        skills_cli.install_skills_cli_vendor(workspace, vendor, dry_run=False)

        assert (workspace.agents_dir / "skills/sample/reference.md").read_text() == "Reference.\n"

    def test_one_snapshot_serves_every_skill_from_one_repository(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
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
            write_skill(source_root / "skills/sample")
            write_skill(source_root / "skills/other", "---\nname: other\ndescription: B.\n---\n\nB.\n")

            return source_root

        def fake_install(
            vendor: SkillsCliVendor,
            skill: VendoredSkill,
            install_directory: Path,
            search_root: Path,
        ) -> None:
            """Copy the resolved upstream skill the way the installer would."""

            located = skills_cli.locate_skill_directory(search_root, skill.upstream_skill)
            write_skill(
                install_directory / ".staging/skills" / skill.name,
                (located / "SKILL.md").read_text(encoding="utf-8"),
            )

        monkeypatch.setattr(github, "resolve_revision", fake_resolve)
        monkeypatch.setattr(github, "download_snapshot", fake_download)
        monkeypatch.setattr(skills_cli, "install_skill", fake_install)

        vendor = SkillsCliVendorFactory.build(
            skills=[
                VendoredSkillFactory.build(name="sample", skills_path="skills"),
                VendoredSkillFactory.build(name="other", skills_path="skills"),
            ]
        )
        skills_cli.install_skills_cli_vendor(workspace, vendor, dry_run=False)

        assert resolved == ["example/repository"]
        assert downloaded == ["example/repository"]
        assert (workspace.agents_dir / "skills/sample/SKILL.md").is_file()
        assert (workspace.agents_dir / "skills/other/SKILL.md").is_file()

    def test_dry_run_reports_changes_without_writing(
        self,
        snapshot: Path,
        workspace: Workspace,
    ) -> None:
        """Test that a dry run reports a pending change and leaves sources untouched."""

        write_skill(snapshot / "skills/sample")
        vendor = SkillsCliVendorFactory.build(skills=[VendoredSkillFactory.build(skills_path="skills")])

        assert skills_cli.install_skills_cli_vendor(workspace, vendor, dry_run=True) is True
        assert not (workspace.agents_dir / "skills").exists()


class TestVendorRunner:
    """Test that registry orchestration and dry-run change reporting work."""

    def test_missing_registry_is_clean(self, workspace: Workspace) -> None:
        """Test that an absent optional registry is a successful no-op."""

        assert runner.install_vendors(workspace, dry_run=True) is False

    def test_registry_without_vendors_is_clean(self, workspace: Workspace) -> None:
        """Test that a registry declaring no vendors installs nothing."""

        materialize_registry(workspace.agents_dir / "vendors.json", VendorRegistryFactory.build())

        assert runner.install_vendors(workspace, dry_run=True) is False

    def test_every_declared_vendor_runs(
        self,
        monkeypatch: pytest.MonkeyPatch,
        workspace: Workspace,
    ) -> None:
        """Test that each enabled vendor is installed and reported."""

        installed: list[str] = []

        def fake_skills_cli(
            resolved_workspace: Workspace,
            vendor: SkillsCliVendor,
            dry_run: bool,
        ) -> bool:
            """Report one synthetic skills.sh change."""

            installed.append("skills-cli")

            return True

        def fake_ecc(resolved_workspace: Workspace, vendor: EccVendor, dry_run: bool) -> bool:
            """Report one synthetic ECC installation."""

            installed.append("ecc")

            return False

        monkeypatch.setattr(runner, "install_skills_cli_vendor", fake_skills_cli)
        monkeypatch.setattr(runner, "install_ecc_vendor", fake_ecc)
        materialize_registry(
            workspace.agents_dir / "vendors.json",
            VendorRegistryFactory.build(
                vendors=Vendors(skills_cli=SkillsCliVendorFactory.build(), ecc=EccVendorFactory.build())
            ),
        )

        assert runner.install_vendors(workspace, dry_run=True) is True
        assert installed == ["skills-cli", "ecc"]

    @pytest.mark.parametrize("vendor_name", ["skills-cli", "ecc"])
    def test_disabled_vendors_are_skipped(
        self,
        monkeypatch: pytest.MonkeyPatch,
        workspace: Workspace,
        vendor_name: str,
    ) -> None:
        """Test that a vendor opting out of sync is never installed."""

        def fail_install(*args: object, **kwargs: object) -> bool:
            """Fail if a disabled vendor reaches installation."""

            raise AssertionError("disabled vendor must not be installed")

        monkeypatch.setattr(runner, "install_skills_cli_vendor", fail_install)
        monkeypatch.setattr(runner, "install_ecc_vendor", fail_install)
        materialize_registry(
            workspace.agents_dir / "vendors.json",
            VendorRegistryFactory.build(
                vendors=Vendors(
                    skills_cli=SkillsCliVendorFactory.build(update_on_sync=False),
                    ecc=EccVendorFactory.build(update_on_sync=False),
                )
            ),
        )

        assert runner.install_vendors(workspace, dry_run=False) is False

    def test_disabled_skills_leave_local_sources_untouched(
        self,
        monkeypatch: pytest.MonkeyPatch,
        workspace: Workspace,
    ) -> None:
        """Test that disabled skill entries leave existing local skills in place."""

        materialize_registry(
            workspace.agents_dir / "vendors.json",
            VendorRegistryFactory.build(
                vendors=Vendors(
                    skills_cli=SkillsCliVendorFactory.build(
                        skills=[VendoredSkillFactory.build(update_on_sync=False)]
                    )
                )
            ),
        )

        local_skill = workspace.agents_dir / "skills/sample/SKILL.md"
        local_skill.parent.mkdir(parents=True)
        local_skill.write_text("local\n")

        def fail_update(*args: object, **kwargs: object) -> bool:
            """Fail if a disabled skill reaches vendoring."""

            raise AssertionError("disabled skill must not be vendored")

        monkeypatch.setattr(skills_cli, "update_repository_skills", fail_update)

        assert runner.install_vendors(workspace, dry_run=False) is False
        assert local_skill.read_text() == "local\n"
