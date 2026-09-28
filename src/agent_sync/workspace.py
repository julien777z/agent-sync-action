import os
import shutil
from pathlib import Path

from agent_sync.models.settings import Workspace
from agent_sync.utils import AgentSyncError


def agents_dir(workspace: Workspace) -> Path:
    """Return the canonical agent source directory."""

    return workspace.root / workspace.agents_dirname


def output_root(workspace: Workspace) -> Path:
    """Return the directory that holds every generated provider tree."""

    return workspace.root / workspace.output_dirname if workspace.output_dirname else workspace.root


def settings_dir(workspace: Workspace) -> Path:
    """Return the canonical provider settings directory."""

    return agents_dir(workspace) / "settings"


def models_dir(workspace: Workspace) -> Path:
    """Return the canonical agent model override directory."""

    return agents_dir(workspace) / "models"


def read_optional_text(path: Path) -> str | None:
    """Read UTF-8 text when a path exists."""

    if not path.exists():
        return None

    return path.read_text(encoding="utf-8")


def read_link(path: Path) -> str | None:
    """Read a symlink target without following it."""

    if not path.is_symlink():
        return None

    return os.readlink(path)


def replace_text(workspace: Workspace, path: Path, content: str, executable: bool) -> None:
    """Replace a path with a generated UTF-8 file."""

    prepare_parent(workspace, path)

    if path.is_symlink() or path.is_dir():
        delete_path(workspace, path)

    path.write_text(content, encoding="utf-8")
    path.chmod(0o755 if executable else 0o644)


def replace_link(workspace: Workspace, path: Path, target: Path) -> None:
    """Replace a path with a relative symlink."""

    prepare_parent(workspace, path)

    if path.is_symlink() or path.exists():
        delete_path(workspace, path)

    path.symlink_to(os.path.relpath(target, path.parent))


def find_parent_blockers(workspace: Workspace, path: Path) -> list[Path]:
    """Return non-directory ancestors that would make an output unsafe to write."""

    relative_parent = path.parent.relative_to(workspace.root)
    current = workspace.root
    blockers: list[Path] = []

    for part in relative_parent.parts:
        current /= part

        if current.is_symlink() or (current.exists() and not current.is_dir()):
            blockers.append(current)

            break

    return blockers


def prepare_parent(workspace: Workspace, path: Path) -> None:
    """Replace unsafe output ancestors, then create the output parent directory."""

    for blocker in find_parent_blockers(workspace, path):
        delete_path(workspace, blocker)

    path.parent.mkdir(parents=True, exist_ok=True)


def contains(workspace: Workspace, path: Path) -> bool:
    """Report whether a path resolves to somewhere inside this repository."""

    root = workspace.root.resolve()
    resolved = path.parent.resolve() / path.name

    return resolved == root or root in resolved.parents


def delete_path(workspace: Workspace, path: Path) -> None:
    """Delete a file, directory, or symlink without following links."""

    if not contains(workspace, path):
        raise AgentSyncError(f"Refusing to delete {path}, which resolves outside the repository")

    if path.is_symlink():
        path.unlink()

        return

    if not path.exists():
        return

    if path.is_dir():
        shutil.rmtree(path)

        return

    path.unlink()
