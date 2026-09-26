from pathlib import Path

import pytest
from pydantic import ValidationError

from agent_sync.external_resources import SOURCE_MARKER, sync_external_resources
from agent_sync import external_sources
from agent_sync.models.registry import ResourcesRegistry
from agent_sync.workspace import Workspace
from tests.factories import ExternalResourceFactory, ResourcesRegistryFactory, materialize_resource_registry


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

    def test_vendors_original_directory_and_removes_stale_files(
        self, workspace: Workspace, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Refresh a managed collection without changing its upstream files."""

        resource = ExternalResourceFactory.build()
        materialize_resource_registry(
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

        monkeypatch.setattr(external_sources, "resolve_revision", fake_resolve)
        monkeypatch.setattr(external_sources, "download_snapshot", fake_download)

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
        materialize_resource_registry(
            workspace.agents_dir / "external_resources.json",
            ResourcesRegistryFactory.build(resources=[resource]),
        )
        destination = workspace.agents_dir / "resources" / resource.name
        destination.mkdir(parents=True)
        (destination / "notes.md").write_text("local", encoding="utf-8")

        with pytest.raises(RuntimeError, match="not managed"):
            sync_external_resources(workspace, dry_run=False)

        assert (destination / "notes.md").read_text() == "local"
