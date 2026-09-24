import logging
from pathlib import Path

import pytest

from agent_sync.external_skills import sync
from agent_sync.models.registry import ExternalSkill
from agent_sync.workspace import Workspace
from tests.factories import ExternalSkillFactory, SkillsRegistryFactory, materialize_registry


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
