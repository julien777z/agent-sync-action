import json
import logging
import shutil
import tempfile
from pathlib import Path
from typing import Final

from agent_sync.external_resources.github import copy_legal_files, download_snapshot, resolve_revision
from agent_sync.models.registry import ExternalDirectory
from agent_sync.utils import replace_tree, trees_differ
from agent_sync.workspace import Workspace

logger: logging.Logger = logging.getLogger(__name__)

SOURCE_MARKER: Final[str] = ".agent-sync-source.json"


def update_external_directory(workspace: Workspace, resource: ExternalDirectory, dry_run: bool) -> bool:
    """Replace one managed directory while preserving upstream file contents."""

    destination = workspace.agents_dir / "resources" / resource.name
    if (
        not destination.is_relative_to(workspace.root)
        or not workspace.contains(destination)
        or workspace.find_parent_blockers(destination)
    ):
        raise RuntimeError(f"Resource directory has an unsafe parent: {destination}")
    marker = {"repo": resource.repo, "source_path": resource.source_path}
    marker_text = json.dumps(marker, indent=2) + "\n"

    if destination.is_symlink():
        raise RuntimeError(f"Resource directory is a link: {destination}")
    if destination.exists():
        marker_path = destination / SOURCE_MARKER
        if not marker_path.is_file() or marker_path.read_text(encoding="utf-8") != marker_text:
            raise RuntimeError(f"Resource directory is not managed by {resource.repo}: {destination}")

    with tempfile.TemporaryDirectory(prefix="agent-sync-resource-") as temporary_directory:
        working_directory = Path(temporary_directory)
        revision = resolve_revision(resource.repo)
        source_root = download_snapshot(resource.repo, revision, working_directory / "source")
        source = source_root / resource.source_path
        if source.is_symlink() or not source.is_dir():
            raise RuntimeError(
                f"Resource source directory does not exist: {resource.repo}/{resource.source_path}"
            )
        if any(path.is_symlink() for path in source.rglob("*")):
            raise RuntimeError(f"Resource source contains a link: {resource.repo}/{resource.source_path}")
        if (source / SOURCE_MARKER).exists():
            raise RuntimeError(
                f"Resource source uses reserved marker name: {resource.repo}/{resource.source_path}"
            )

        staged = working_directory / "resource"
        shutil.copytree(source, staged)
        copy_legal_files(staged, source_root)
        (staged / SOURCE_MARKER).write_text(marker_text, encoding="utf-8")
        changed = trees_differ(staged, destination)

        if changed and not dry_run:
            replace_tree(staged, destination, destination if destination.exists() else None)

    return changed
