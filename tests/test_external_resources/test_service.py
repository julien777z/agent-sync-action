import logging
from pathlib import Path

import pytest

from agent_sync.external_resources import sync
from agent_sync.models.registry import ExternalSkill
from agent_sync.reconciliation import mirror_providers
from agent_sync.workspace import Workspace
from tests.factories import (
    ExternalSkillFactory,
    ResourcesRegistryFactory,
    ROOT_LEVEL_SKILL,
    materialize_registry,
    stub_root_level_upstream,
)


class TestExternalSkillService:
    """Test that registry orchestration and dry-run change reporting work."""

    def test_missing_registry_is_clean(self, workspace: Workspace) -> None:
        """Test that an absent optional registry is a successful no-op."""

        assert sync.sync_external_resources(workspace, dry_run=True) is None

    def test_vendored_skill_reaches_provider_mirrors(
        self, workspace: Workspace, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Mirror an installed external skill to every supported provider."""

        stub_root_level_upstream(monkeypatch)
        materialize_registry(
            workspace.agents_dir / "external_resources.json",
            ResourcesRegistryFactory.build(resources=[ROOT_LEVEL_SKILL]),
        )
        sync.sync_external_resources(workspace, dry_run=False)
        assert mirror_providers(workspace, dry_run=False) is False

        for provider in (".claude", ".cursor", ".codex"):
            document = workspace.output_root / provider / "skills/local-skill/SKILL.md"
            assert document.is_file()
            assert "name: local-skill" in document.read_text()

    def test_dry_run_reports_changes(
        self,
        caplog: pytest.LogCaptureFixture,
        monkeypatch: pytest.MonkeyPatch,
        workspace: Workspace,
    ) -> None:
        """Test that changed external skills are reported by a dry run."""

        caplog.set_level(logging.INFO)

        materialize_registry(
            workspace.agents_dir / "external_resources.json",
            ResourcesRegistryFactory.build(resources=[ExternalSkillFactory.build()]),
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

        assert sync.sync_external_resources(workspace, dry_run=True) is None
        assert "sample (example/repository): would update" in caplog.text

    def test_disabled_update_on_sync_skips_vendoring(
        self,
        monkeypatch: pytest.MonkeyPatch,
        workspace: Workspace,
    ) -> None:
        """Test that disabled entries leave existing local skills untouched."""

        materialize_registry(
            workspace.agents_dir / "external_resources.json",
            ResourcesRegistryFactory.build(resources=[ExternalSkillFactory.build(update_on_sync=False)]),
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

        assert sync.sync_external_resources(workspace, dry_run=False) is None
        assert local_skill.read_text() == "local\n"
