import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Final

LEGAL_FILE_PREFIXES: Final[tuple[str, ...]] = ("LICENSE", "COPYING", "NOTICE")
REPOSITORY_URL_TEMPLATE: Final[str] = "https://github.com/{repository}.git"


def resolve_revision(repository: str) -> str:
    """Resolve a GitHub repository HEAD to one immutable commit SHA."""

    command = ["git", "ls-remote", REPOSITORY_URL_TEMPLATE.format(repository=repository), "HEAD"]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    revision = result.stdout.split(maxsplit=1)[0] if result.stdout.strip() else ""

    if result.returncode != 0 or re.fullmatch(r"[0-9a-fA-F]{40}", revision) is None:
        raise RuntimeError(
            f"`git ls-remote {repository} HEAD` failed (exit {result.returncode}):\n"
            f"{result.stdout}\n{result.stderr}"
        )

    return revision


def run_git(command: list[str]) -> None:
    """Run one git command, raising with its output when it fails."""

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "GIT_LFS_SKIP_SMUDGE": "1", "GIT_TERMINAL_PROMPT": "0"},
    )

    if result.returncode != 0:
        raise RuntimeError(f"`{' '.join(command)}` failed (exit {result.returncode}):\n{result.stderr}")


def download_snapshot(repository: str, revision: str, destination: Path) -> Path:
    """Fetch one GitHub revision over git and return its checked-out repository root."""

    source_root = destination / "repository"
    source_root.mkdir(parents=True)

    run_git(["git", "init", "--quiet", str(source_root)])
    run_git(
        [
            "git",
            "-C",
            str(source_root),
            "fetch",
            "--quiet",
            "--depth",
            "1",
            REPOSITORY_URL_TEMPLATE.format(repository=repository),
            revision,
        ]
    )
    run_git(["git", "-C", str(source_root), "checkout", "--quiet", "--detach", "FETCH_HEAD"])

    shutil.rmtree(source_root / ".git")

    return source_root


def copy_legal_files(destination: Path, source_root: Path, *, overwrite_existing: bool = False) -> None:
    """Copy repository-root legal files beside vendored content."""

    for entry in sorted(source_root.iterdir()):
        if not entry.is_file() or not entry.name.upper().startswith(LEGAL_FILE_PREFIXES):
            continue

        target = destination / entry.name

        if target.is_symlink():
            if not overwrite_existing:
                raise RuntimeError(f"Conflicting legal link in {destination}: {entry.name}")

            target.unlink()

        if target.is_dir():
            raise RuntimeError(f"Conflicting legal directory in {destination}: {entry.name}")

        if target.exists() and not overwrite_existing:
            if target.read_bytes() != entry.read_bytes():
                raise RuntimeError(f"Conflicting legal file in {destination}: {entry.name}")

            continue

        shutil.copy2(entry, target)
