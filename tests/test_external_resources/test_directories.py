from pathlib import Path

import pytest
from pydantic import ValidationError

from agent_sync.external_resources import directories, sync
from agent_sync.external_resources.directories import SOURCE_MARKER
from agent_sync.external_resources.sync import sync_external_resources
from agent_sync.models.registry import ExternalDirectory, ExternalSkill, ResourcesRegistry
from agent_sync.workspace import Workspace
from tests.factories import (
    ExternalResourceFactory,
    ExternalSkillFactory,
    ResourcesRegistryFactory,
    materialize_registry,
)


class TestExternalResources:
    """Test resource registry validation and directory updates."""

    @pytest.mark.parametrize("source_path", ["/absolute", "../escape", "guides/../../escape", ""])
    def test_resource_source_path_stays_in_repository(self, source_path: str) -> None:
        """Reject paths that can escape the upstream snapshot."""

        with pytest.raises(ValidationError):
            ExternalResourceFactory.build(source_path=source_path)

    def test_duplicate_resource_names_fail(self) -> None:
        """Reject registrations that target the same directory."""

        with pytest.raises(ValidationError, match="names must be unique"):
            ResourcesRegistry(
                resources=[
                    ExternalResourceFactory.build(),
                    ExternalResourceFactory.build(repo="example/other-reference"),
                ]
            )

    def test_mixed_registry_dispatches_each_kind_once(
        self, workspace: Workspace, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Route skills and directories from one registry to their existing destinations."""

        skill = ExternalSkillFactory.build()
        directory = ExternalResourceFactory.build()
        materialize_registry(
            workspace.agents_dir / "external_resources.json",
            ResourcesRegistry(resources=[skill, directory]),
        )
        calls: list[tuple[str, bool]] = []

        def update_skill(
            resolved_workspace: Workspace, entry: ExternalSkill, skills_dir: Path, dry_run: bool
        ) -> bool:
            assert resolved_workspace == workspace
            assert skills_dir == workspace.agents_dir / "skills"
            calls.append((entry.kind, dry_run))
            return True

        def update_directory(resolved_workspace: Workspace, entry: ExternalDirectory, dry_run: bool) -> bool:
            assert resolved_workspace == workspace
            calls.append((entry.kind, dry_run))
            return True

        monkeypatch.setattr(sync, "update_external_skill", update_skill)
        monkeypatch.setattr(sync, "update_external_directory", update_directory)
        sync_external_resources(workspace, dry_run=True)
        assert calls == [("skill", True), ("directory", True)]

    def test_invalid_kind_and_missing_kind_fail(self) -> None:
        """Require every resource to choose one supported vendoring behavior."""

        for value in ("unknown", None):
            with pytest.raises(ValidationError):
                ResourcesRegistry.model_validate(
                    {
                        "resources": [
                            {"kind": value, "name": "sample", "repo": "example/repo", "update_on_sync": True}
                        ]
                    }
                )

    def test_vendors_original_directory_and_removes_stale_files(
        self, workspace: Workspace, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Refresh a managed collection without changing its upstream files."""

        resource = ExternalResourceFactory.build()
        materialize_registry(
            workspace.agents_dir / "external_resources.json",
            ResourcesRegistryFactory.build(resources=[resource]),
        )
        source_files = {"guide.md": "# Guide\n", "nested/example.txt": "example\n"}

        def fake_resolve(repository: str) -> str:
            """Return a stable synthetic revision."""

            return "a" * 40

        def fake_download(repository: str, revision: str, destination: Path) -> Path:
            """Materialize the selected directory in a synthetic snapshot."""

            root = destination / "repository"
            for relative, content in source_files.items():
                target = root / resource.source_path / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content, encoding="utf-8")
            (root / "LICENSE").write_text("Sample license\n", encoding="utf-8")
            return root

        monkeypatch.setattr(directories, "resolve_revision", fake_resolve)
        monkeypatch.setattr(directories, "download_snapshot", fake_download)

        destination = workspace.agents_dir / "resources" / resource.name
        sync_external_resources(workspace, dry_run=False)
        assert (destination / "guide.md").read_text() == source_files["guide.md"]
        assert (destination / "nested/example.txt").read_text() == source_files["nested/example.txt"]
        assert (destination / SOURCE_MARKER).is_file()
        assert (destination / "LICENSE").read_text() == "Sample license\n"

        (destination / "stale.md").write_text("stale", encoding="utf-8")
        sync_external_resources(workspace, dry_run=True)
        assert (destination / "stale.md").exists()
        sync_external_resources(workspace, dry_run=False)
        assert not (destination / "stale.md").exists()

    def test_refuses_unmanaged_destination(self, workspace: Workspace) -> None:
        """Preserve an existing directory that Agent Sync does not own."""

        resource = ExternalResourceFactory.build()
        materialize_registry(
            workspace.agents_dir / "external_resources.json",
            ResourcesRegistryFactory.build(resources=[resource]),
        )
        destination = workspace.agents_dir / "resources" / resource.name
        destination.mkdir(parents=True)
        (destination / "notes.md").write_text("local", encoding="utf-8")

        with pytest.raises(RuntimeError, match="not managed"):
            sync_external_resources(workspace, dry_run=False)

        assert (destination / "notes.md").read_text() == "local"

    def test_refuses_linked_resource_parent(self, workspace: Workspace, tmp_path: Path) -> None:
        """Test that resource writes cannot follow a linked parent outside the workspace."""

        resource = ExternalResourceFactory.build()
        materialize_registry(
            workspace.agents_dir / "external_resources.json",
            ResourcesRegistryFactory.build(resources=[resource]),
        )
        outside = tmp_path / "outside"
        outside.mkdir()
        (workspace.agents_dir / "resources").symlink_to(outside, target_is_directory=True)

        with pytest.raises(RuntimeError, match="unsafe parent"):
            sync_external_resources(workspace, dry_run=False)

        assert not any(outside.iterdir())
