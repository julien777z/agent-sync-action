import io
import re
import shutil
import subprocess
import tarfile
import urllib.request
from pathlib import Path
from typing import Final

LEGAL_FILE_PREFIXES: Final[tuple[str, ...]] = ("LICENSE", "COPYING", "NOTICE")


def resolve_revision(repository: str) -> str:
    """Resolve a GitHub repository HEAD to one immutable commit SHA."""

    command = ["git", "ls-remote", f"https://github.com/{repository}.git", "HEAD"]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    revision = result.stdout.split(maxsplit=1)[0] if result.stdout.strip() else ""

    if result.returncode != 0 or re.fullmatch(r"[0-9a-fA-F]{40}", revision) is None:
        raise RuntimeError(
            f"`git ls-remote {repository} HEAD` failed (exit {result.returncode}):\n"
            f"{result.stdout}\n{result.stderr}"
        )

    return revision


def download_snapshot(repository: str, revision: str, destination: Path) -> Path:
    """Download one GitHub revision and return its extracted repository root."""

    url = f"https://codeload.github.com/{repository}/tar.gz/{revision}"
    request = urllib.request.Request(url, headers={"User-Agent": "agent-sync"})

    with urllib.request.urlopen(request, timeout=60) as response:
        payload = response.read()

    with tarfile.open(fileobj=io.BytesIO(payload), mode="r:gz") as archive:
        archive.extractall(destination, filter="data")

    roots = [path for path in destination.iterdir() if path.is_dir()]

    if len(roots) != 1:
        raise RuntimeError(f"Unexpected tarball layout for {repository}: {[path.name for path in roots]}")

    return roots[0]


def copy_legal_files(destination: Path, source_root: Path) -> None:
    """Copy repository-root legal files beside vendored content."""

    for entry in sorted(source_root.iterdir()):
        if not entry.is_file() or not entry.name.upper().startswith(LEGAL_FILE_PREFIXES):
            continue

        target = destination / entry.name

        if not target.exists():
            shutil.copy2(entry, target)
            continue

        if target.read_bytes() != entry.read_bytes():
            raise RuntimeError(f"Conflicting legal file in {destination}: {entry.name}")
