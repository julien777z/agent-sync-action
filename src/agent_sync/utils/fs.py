import argparse
import os
import shutil
from pathlib import Path
from typing import Final

from pydantic import BaseModel, Field

TEXT_CACHE: Final[dict[Path, str | None]] = {}

DEFAULT_AGENTS_DIRNAME: Final[str] = ".agents"


class SyncContext(BaseModel):
    """Mutable holder for the configured repository root and source directory name."""

    path: Path = Field(default_factory=Path.cwd)
    agents_dirname: str = DEFAULT_AGENTS_DIRNAME


CONTEXT: Final[SyncContext] = SyncContext()


def set_root(path: Path, agents_dirname: str = DEFAULT_AGENTS_DIRNAME) -> None:
    """Point the sync at a repository root, set the source dir name, and reset the read cache."""

    CONTEXT.path = Path(path).resolve()
    CONTEXT.agents_dirname = agents_dirname or DEFAULT_AGENTS_DIRNAME

    TEXT_CACHE.clear()


def root() -> Path:
    """Return the configured repository root."""

    return CONTEXT.path


def agents_dir() -> Path:
    """Return the source-of-truth agents directory under the configured root."""

    return CONTEXT.path / CONTEXT.agents_dirname


def add_root_arguments(parser: argparse.ArgumentParser) -> None:
    """Register the shared --root / --agents-dir options on an argument parser."""

    parser.add_argument(
        "--root",
        default=None,
        help="Repository root (default: $AGENT_SYNC_ROOT or cwd).",
    )
    parser.add_argument(
        "--agents-dir",
        default=None,
        help="Source directory name (default: $AGENT_SYNC_AGENTS_DIR or .agents).",
    )


def set_root_from_args(args: argparse.Namespace) -> None:
    """Resolve --root/--agents-dir (then env, then defaults) and point the sync at that root."""

    resolved_root = args.root or os.environ.get("AGENT_SYNC_ROOT") or os.getcwd()
    agents_dirname = (
        args.agents_dir
        or os.environ.get("AGENT_SYNC_AGENTS_DIR")
        or DEFAULT_AGENTS_DIRNAME
    )
    set_root(Path(resolved_root), agents_dirname)


def read_text(path: Path) -> str | None:
    """Read a file with caching to avoid repeated disk reads."""

    if path in TEXT_CACHE:
        return TEXT_CACHE[path]

    if not path.exists():
        TEXT_CACHE[path] = None
        return None

    content = path.read_text(encoding="utf-8")
    TEXT_CACHE[path] = content

    return content


def read_bytes(path: Path) -> bytes | None:
    """Read a file as raw bytes, returning None when it does not exist."""

    if not path.exists():
        return None

    return path.read_bytes()


def write(path: Path, content: str | bytes) -> None:
    """Write a file, update its cache entry, and apply the executable bit."""

    path.parent.mkdir(parents=True, exist_ok=True)

    if isinstance(content, bytes):
        path.write_bytes(content)
        TEXT_CACHE.pop(path, None)
    else:
        path.write_text(content, encoding="utf-8")
        TEXT_CACHE[path] = content

    if is_executable_output(path, content):
        path.chmod(0o755)


def delete_path(path: Path) -> None:
    """Delete a file or directory and clear any cached text entries."""

    if not path.exists():
        return

    if path.is_dir():
        shutil.rmtree(path)
        stale_keys = [cached for cached in TEXT_CACHE if cached.is_relative_to(path)]
        for stale_key in stale_keys:
            TEXT_CACHE.pop(stale_key, None)

        return

    path.unlink(missing_ok=True)
    TEXT_CACHE.pop(path, None)


def is_executable_output(path: Path, content: str | bytes) -> bool:
    """Report whether an output should carry the exec bit (shell scripts and shebang files)."""

    shebang = b"#!" if isinstance(content, bytes) else "#!"

    return path.suffix == ".sh" or content.startswith(shebang)
