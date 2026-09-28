import argparse
import os
from pathlib import Path
import subprocess


def registry_changed(agents_dir: str, before: str, current: str) -> bool:
    """Check whether the registered resource list changed in a push."""

    if not before:
        return False

    previous = subprocess.run(
        ["git", "cat-file", "-e", f"{before}^{{commit}}"], capture_output=True, check=False
    )

    if previous.returncode != 0:
        subprocess.run(["git", "fetch", "--depth=1", "origin", before], capture_output=True, check=False)

        previous = subprocess.run(
            ["git", "cat-file", "-e", f"{before}^{{commit}}"], capture_output=True, check=False
        )

    if previous.returncode != 0:
        return False

    prefix = subprocess.run(
        ["git", "-C", agents_dir, "rev-parse", "--show-prefix"],
        capture_output=True,
        check=False,
        text=True,
    )

    if prefix.returncode != 0:
        return False

    changed = subprocess.run(
        ["git", "diff", "--name-only", "-z", before, current],
        capture_output=True,
        check=True,
    )
    registry = f"{prefix.stdout.strip()}external_resources.json".encode()

    return registry in changed.stdout.split(b"\0")


if __name__ == "__main__":
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description="Decide whether external resources need refreshing."
    )
    parser.add_argument("--agents-dir", required=True)
    parser.add_argument("--before", required=True)
    parser.add_argument("--current", required=True)
    parser.add_argument("--event", required=True)
    parser.add_argument("--force", required=True)
    arguments: argparse.Namespace = parser.parse_args()

    enabled: bool = arguments.force == "true" or (
        arguments.event == "push"
        and registry_changed(arguments.agents_dir, arguments.before, arguments.current)
    )

    with Path(os.environ["GITHUB_OUTPUT"]).open("a", encoding="utf-8") as output:
        output.write(f"enabled={str(enabled).lower()}\n")
