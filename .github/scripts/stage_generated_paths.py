import argparse
from pathlib import Path
import subprocess

from agent_sync.generation.artifact import has_generated_notice
from agent_sync.models.output import Provider


def stage_generated_paths(agents_dir: str, output_dir: str) -> None:
    """Stage only canonical sources and generated outputs, including owned deletions."""

    relocated = output_dir not in ("", ".")
    output_root = Path(output_dir) if relocated else Path(".")
    provider_directories = tuple(provider.directory for provider in Provider)
    paths = [*(output_root / directory for directory in provider_directories), Path(agents_dir)]

    if relocated:
        deleted = subprocess.run(
            ["git", "ls-files", "--deleted", "-z", "--", *provider_directories],
            capture_output=True,
            check=True,
        )

        for path in (item.decode() for item in deleted.stdout.split(b"\0") if item):
            subprocess.run(["git", "add", "-u", "--", path], check=True)

    instructions = Path("AGENTS.md")

    if instructions.is_file() and not instructions.is_symlink():
        if has_generated_notice(instructions.read_text(encoding="utf-8")):
            paths.append(instructions)

    elif not instructions.exists() and not instructions.is_symlink():
        previous = subprocess.run(["git", "show", "HEAD:AGENTS.md"], capture_output=True, check=False)

        if previous.returncode == 0 and has_generated_notice(previous.stdout.decode("utf-8")):
            paths.append(instructions)

    for path in paths:
        tracked = subprocess.run(["git", "ls-files", "--", str(path)], capture_output=True, check=True)

        if path.exists() or path.is_symlink() or tracked.stdout:
            subprocess.run(["git", "add", "-A", "--", str(path)], check=True)


if __name__ == "__main__":
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description="Stage Agent Sync-owned outputs in a consumer checkout."
    )
    parser.add_argument("--agents-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    arguments: argparse.Namespace = parser.parse_args()
    stage_generated_paths(arguments.agents_dir, arguments.output_dir)
