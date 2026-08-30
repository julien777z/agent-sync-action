import logging
import shutil
from pathlib import Path
from typing import Final

logger = logging.getLogger(__name__)

TARBALL_EXCLUDES: Final[frozenset[str]] = frozenset(
    {
        "node_modules",
        "dist",
        "build",
        "__pycache__",
        "package.json",
        "package-lock.json",
        "pnpm-lock.yaml",
        "yarn.lock",
        "tsconfig.json",
        "Makefile",
    }
)
LEGAL_FILE_PREFIXES: Final[tuple[str, ...]] = ("LICENSE", "COPYING", "NOTICE")


def supplement_root_assets(destination: Path, search_root: Path) -> None:
    """Copy sibling skill assets omitted by the installer."""

    for entry in sorted(search_root.iterdir()):
        if entry.name.startswith(".") or entry.name in TARBALL_EXCLUDES:
            continue

        target = destination / entry.name

        if entry.is_dir():
            shutil.copytree(entry, target, dirs_exist_ok=True)
        else:
            shutil.copy2(entry, target)


def copy_legal_files(destination: Path, source_root: Path) -> None:
    """Copy repository-root legal files into the installed skill."""

    legal_files = [
        entry
        for entry in sorted(source_root.iterdir())
        if entry.is_file() and entry.name.upper().startswith(LEGAL_FILE_PREFIXES)
    ]

    for legal_file in legal_files:
        shutil.copy2(legal_file, destination / legal_file.name)
