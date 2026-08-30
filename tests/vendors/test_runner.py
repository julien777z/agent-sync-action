import pytest

from agent_sync.models.vendors.ecc import EccVendor
from agent_sync.models.vendors.lock import VendorInstallResult
from agent_sync.models.vendors.registry import Vendors
from agent_sync.models.vendors.skills_cli import SkillsCliVendor
from agent_sync.vendors import runner
from agent_sync.vendors.skills_cli import sync
from agent_sync.workspace import Workspace
from tests.factories import (
    EccVendorFactory,
    SkillsCliVendorFactory,
    VendoredSkillFactory,
    VendorRegistryFactory,
    materialize_registry,
)


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
        ) -> VendorInstallResult:
            """Report one synthetic skills.sh change."""

            installed.append("skills-cli")

            return VendorInstallResult(differences_found=True)

        def fake_ecc(
            resolved_workspace: Workspace,
            vendor: EccVendor,
            dry_run: bool,
        ) -> VendorInstallResult:
            """Report one synthetic ECC installation."""

            installed.append("ecc")

            return VendorInstallResult()

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

    def test_disabled_vendors_are_skipped(
        self,
        monkeypatch: pytest.MonkeyPatch,
        workspace: Workspace,
    ) -> None:
        """Test that a vendor opting out of sync is never installed."""

        def fail_install(*args: object, **kwargs: object) -> VendorInstallResult:
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

    def test_disabled_skills_leave_sources_untouched(
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

        monkeypatch.setattr(sync, "update_repository_skills", fail_update)

        assert runner.install_vendors(workspace, dry_run=False) is False
        assert local_skill.read_text() == "local\n"
