import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from agent_sync.config import ActionConfig
from agent_sync.external_resources import sync
from agent_sync.external_resources.directories import SOURCE_MARKER, update_external_directory
from agent_sync.external_resources.sync import sync_external_resources
from agent_sync.models.registry import (
    DirectorySourceMarker,
    ExternalDirectory,
    ExternalSkill,
    ResourcesRegistry,
)
from agent_sync.models.settings import Workspace
from agent_sync.workspace import agents_dir
from tests.factories import (
    ExternalResourceFactory,
    ExternalSkillFactory,
    ResourcesRegistryFactory,
    materialize_registry,
    materialize_tree,
    stub_external_directory_upstream,
)


class TestExternalResources:
    """Test that resource registry validation and directory updates work."""

    @pytest.mark.parametrize("source_path", ["/absolute", "../escape", "guides/../../escape", ""])
    def test_resource_source_path_stays_in_repository(self, source_path: str) -> None:
        """Test that paths cannot escape the upstream snapshot."""

        with pytest.raises(ValidationError):
            ExternalResourceFactory.build(source_path=source_path)

    def test_duplicate_resource_names_fail(self) -> None:
        """Test that registrations cannot target the same directory."""

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
        """Test that one registry routes skills and directories to their destinations."""

        skill = ExternalSkillFactory.build()
        directory = ExternalResourceFactory.build()
        materialize_registry(
            agents_dir(workspace) / "external_resources.json",
            ResourcesRegistry(resources=[skill, directory]),
        )
        calls: list[tuple[str, bool]] = []

        def update_skill(
            resolved_workspace: Workspace,
            entry: ExternalSkill,
            skills_dir: Path,
            dry_run: bool,
            config: ActionConfig,
        ) -> bool:
            assert resolved_workspace == workspace
            assert skills_dir == agents_dir(workspace) / "skills"
            calls.append((entry.kind, dry_run))
            return True

        def update_directory(resolved_workspace: Workspace, entry: ExternalDirectory, dry_run: bool) -> bool:
            assert resolved_workspace == workspace
            calls.append((entry.kind, dry_run))
            return True

        monkeypatch.setattr(sync, "update_external_skill", update_skill)
        monkeypatch.setattr(sync, "update_external_directory", update_directory)

        sync_external_resources(workspace, dry_run=True, config=ActionConfig())

        assert calls == [("skill", True), ("directory", True)]

    @pytest.mark.parametrize("kind", ["unknown", None], ids=["invalid", "missing"])
    def test_invalid_kind_and_missing_kind_fail(self, kind: str | None) -> None:
        """Test that every resource selects a supported vendoring behavior."""

        resource = ExternalResourceFactory.build().model_dump()
        if kind is None:
            del resource["kind"]
        else:
            resource["kind"] = kind

        with pytest.raises(ValidationError):
            ResourcesRegistry.model_validate({"resources": [resource]})

    def test_vendors_original_directory_and_removes_stale_files(
        self, workspace: Workspace, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that refresh preserves upstream files and removes stale local files."""

        resource = ExternalResourceFactory.build()
        materialize_registry(
            agents_dir(workspace) / "external_resources.json",
            ResourcesRegistryFactory.build(resources=[resource]),
        )
        source_files = {"guide.md": "# Guide\n", "nested/example.txt": "example\n"}

        stub_external_directory_upstream(monkeypatch, resource, source_files, root_license="Sample license\n")

        destination = agents_dir(workspace) / "resources" / resource.name
        sync_external_resources(workspace, dry_run=False, config=ActionConfig())

        assert (destination / "guide.md").read_text() == source_files["guide.md"]
        assert (destination / "nested/example.txt").read_text() == source_files["nested/example.txt"]
        assert (destination / SOURCE_MARKER).is_file()
        assert (destination / "LICENSE").read_text() == "Sample license\n"

        (destination / "stale.md").write_text("stale", encoding="utf-8")
        sync_external_resources(workspace, dry_run=True, config=ActionConfig())

        assert (destination / "stale.md").exists()

        sync_external_resources(workspace, dry_run=False, config=ActionConfig())

        assert not (destination / "stale.md").exists()
        assert not update_external_directory(workspace, resource, dry_run=False)

    def test_removes_stale_link(self, workspace: Workspace, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that refresh removes a stale link when upstream files are unchanged."""

        resource = ExternalResourceFactory.build(name="stale-link-reference", repo="example/stale-link")
        stub_external_directory_upstream(monkeypatch, resource, {"guide.md": "upstream"})
        destination = agents_dir(workspace) / "resources" / resource.name
        assert update_external_directory(workspace, resource, dry_run=False)

        stale_link = destination / "stale-link"
        stale_link.symlink_to("missing")

        assert stale_link.is_symlink()

        assert update_external_directory(workspace, resource, dry_run=False)

        assert not stale_link.exists()
        assert not stale_link.is_symlink()
        assert not update_external_directory(workspace, resource, dry_run=False)

    def test_refuses_unmanaged_destination(self, workspace: Workspace) -> None:
        """Test that an unmanaged directory is preserved."""

        resource = ExternalResourceFactory.build()
        materialize_registry(
            agents_dir(workspace) / "external_resources.json",
            ResourcesRegistryFactory.build(resources=[resource]),
        )
        destination = agents_dir(workspace) / "resources" / resource.name
        destination.mkdir(parents=True)
        (destination / "notes.md").write_text("local", encoding="utf-8")

        with pytest.raises(RuntimeError, match="not managed"):
            sync_external_resources(workspace, dry_run=False, config=ActionConfig())

        assert (destination / "notes.md").read_text() == "local"

    def test_refuses_linked_source_marker(
        self, workspace: Workspace, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that a linked ownership marker cannot claim a local directory."""

        resource = ExternalResourceFactory.build(name="linked-source-reference", repo="example/linked-source")
        destination = agents_dir(workspace) / "resources" / resource.name
        destination.mkdir(parents=True)
        local_note = destination / "notes.md"
        materialize_tree(destination, {"notes.md": "local"})
        marker_content = (
            json.dumps(DirectorySourceMarker(repo=resource.repo, source_path=resource.source_path), indent=2)
            + "\n"
        )
        outside_marker = tmp_path / "matching-source.json"
        outside_marker.write_text(marker_content, encoding="utf-8")
        marker = destination / SOURCE_MARKER
        marker.symlink_to(outside_marker)

        stub_external_directory_upstream(monkeypatch, resource, {"guide.md": "upstream"})

        with pytest.raises(RuntimeError, match="not managed"):
            update_external_directory(workspace, resource, dry_run=False)

        assert local_note.read_text(encoding="utf-8") == "local"
        assert marker.is_symlink()
        assert outside_marker.read_text(encoding="utf-8") == marker_content

    def test_refuses_linked_source_parent(
        self, workspace: Workspace, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that a linked source ancestor cannot select another upstream directory."""

        resource = ExternalResourceFactory.build(
            name="linked-source-parent",
            repo="example/linked-source-parent",
            source_path="references/sub",
        )
        stub_external_directory_upstream(
            monkeypatch,
            resource,
            {"guide.md": "upstream"},
            snapshot_path="docs/sub",
            links={"references": "docs"},
        )

        with pytest.raises(RuntimeError, match="source directory does not exist"):
            update_external_directory(workspace, resource, dry_run=False)

        assert not (agents_dir(workspace) / "resources" / resource.name).exists()

    def test_refuses_linked_resource_parent(self, workspace: Workspace, tmp_path: Path) -> None:
        """Test that resource writes cannot follow a linked parent outside the workspace."""

        resource = ExternalResourceFactory.build()
        materialize_registry(
            agents_dir(workspace) / "external_resources.json",
            ResourcesRegistryFactory.build(resources=[resource]),
        )
        outside = tmp_path / "outside"
        outside.mkdir()
        (agents_dir(workspace) / "resources").symlink_to(outside, target_is_directory=True)

        with pytest.raises(RuntimeError, match="unsafe parent"):
            sync_external_resources(workspace, dry_run=False, config=ActionConfig())

        assert not any(outside.iterdir())
