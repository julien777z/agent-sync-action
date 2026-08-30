import json
import logging
from pathlib import Path
from typing import Final

from agent_sync.models.vendors.lock import VendorLock, VendorLockEntry
from agent_sync.utils import ensure_trailing_newline, load_json_model
from agent_sync.workspace import Workspace

logger = logging.getLogger(__name__)

LOCK_FILENAME: Final[str] = "vendors.lock.json"


def load_lock(workspace: Workspace) -> VendorLock:
    """Read the record of what each vendor installed, defaulting to an empty one."""

    return load_json_model(workspace.agents_dir / LOCK_FILENAME, VendorLock) or VendorLock()


def save_lock(workspace: Workspace, lock: VendorLock) -> None:
    """Write the record of what each vendor installed."""

    path = workspace.agents_dir / LOCK_FILENAME
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        ensure_trailing_newline(json.dumps(lock.model_dump(), indent=2)),
        encoding="utf-8",
    )


def orphaned_paths(
    lock: VendorLock, installed: dict[str, list[str]], declared: set[str]
) -> dict[str, list[str]]:
    """Return the recorded paths each vendor no longer claims."""

    orphaned: dict[str, list[str]] = {}

    for name, entry in lock.vendors.items():
        if name not in declared:
            orphaned[name] = sorted(entry.paths)

            continue

        if name not in installed:
            continue

        remaining = sorted(set(entry.paths) - set(installed[name]))

        if remaining:
            orphaned[name] = remaining

    return orphaned


def prune_empty_parents(workspace: Workspace, path: Path) -> None:
    """Remove directories left empty by a deletion, stopping at the agents directory."""

    for parent in path.parents:
        if parent == workspace.agents_dir or not parent.is_relative_to(workspace.agents_dir):
            return

        if any(parent.iterdir()):
            return

        parent.rmdir()


def reconcile_installed_paths(
    workspace: Workspace,
    installed: dict[str, list[str]],
    declared: set[str],
    dry_run: bool,
) -> bool:
    """Remove what each vendor no longer claims and record what it does."""

    lock = load_lock(workspace)
    orphaned = orphaned_paths(lock, installed, declared)

    for name, paths in orphaned.items():
        for path in paths:
            logger.info("  %s: %s %s", name, "would remove" if dry_run else "removed", path)

            if not dry_run:
                removed = workspace.root / path
                workspace.delete(removed)
                prune_empty_parents(workspace, removed)

    if dry_run:
        return bool(orphaned)

    retained = {
        name: entry for name, entry in lock.vendors.items() if name in declared and name not in installed
    }
    save_lock(
        workspace,
        VendorLock(
            version=lock.version,
            vendors={
                **retained,
                **{name: VendorLockEntry(paths=sorted(paths)) for name, paths in installed.items()},
            },
        ),
    )

    return False


def relative_installed_paths(workspace: Workspace, destinations: list[str]) -> list[str]:
    """Return the destinations that lie inside the workspace, repository-relative."""

    relative: list[str] = []

    for destination in destinations:
        path = Path(destination)

        if path.is_relative_to(workspace.root):
            relative.append(workspace.relative_path(path))

    return sorted(set(relative))
