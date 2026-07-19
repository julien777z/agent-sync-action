import io
import re
import subprocess
import tarfile
import urllib.request
from pathlib import Path


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
        raise RuntimeError(
            f"Unexpected tarball layout for {repository}: {[path.name for path in roots]}"
        )

    return roots[0]
