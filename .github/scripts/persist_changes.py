import argparse
import logging
import os
from pathlib import Path
import subprocess
import sys

from agent_sync.config import ActionConfig

logger: logging.Logger = logging.getLogger(__name__)


def run_git(*arguments: str) -> None:
    """Run one required Git operation."""

    subprocess.run(["git", *arguments], check=True)


def stage_generated_paths(action_path: Path, agents_dir: str, output_dir: str) -> None:
    """Stage only files owned by Agent Sync."""

    script = action_path / ".github/scripts/stage_generated_paths.py"
    subprocess.run(
        [sys.executable, str(script), "--agents-dir", agents_dir, "--output-dir", output_dir],
        check=True,
    )


def mirror_providers(agents_dir: str, output_dir: str) -> None:
    """Regenerate provider files after incorporating remote commits."""

    subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_sync",
            "mirror-providers",
            "--root",
            ".",
            "--agents-dir",
            agents_dir,
            "--output-dir",
            output_dir,
        ],
        check=True,
    )


def persist_changes(action_path: Path, agents_dir: str, output_dir: str, mode: str, ref: str) -> None:
    """Commit and push generated changes in the selected mode."""

    run_git("config", "user.name", ActionConfig.COMMIT_AUTHOR_NAME)
    run_git("config", "user.email", ActionConfig.COMMIT_AUTHOR_EMAIL)
    subprocess.run(
        ["git", "config", "--local", "--unset-all", "http.https://github.com/.extraheader"],
        check=False,
    )

    repository = os.environ["GITHUB_REPOSITORY"]
    token = os.environ["GH_TOKEN"]
    remote = f"https://x-access-token:{token}@github.com/{repository}.git"
    configured = subprocess.run(
        ["git", "remote", "set-url", "origin", remote],
        capture_output=True,
        check=False,
    )

    if configured.returncode != 0:
        raise RuntimeError("Unable to configure the authenticated origin")

    stage_generated_paths(action_path, agents_dir, output_dir)

    if subprocess.run(["git", "diff", "--cached", "--quiet"], check=False).returncode == 0:
        logger.info("No changes to commit.")
        return

    run_git("commit", "-m", "chore: run agent sync")

    if mode == "pull-request":
        branch = f"agent-sync/{ref}"
        run_git("push", "--force", "origin", f"HEAD:{branch}")

        existing = subprocess.run(["gh", "pr", "view", branch], capture_output=True, check=False)

        if existing.returncode != 0:
            subprocess.run(
                [
                    "gh",
                    "pr",
                    "create",
                    "--base",
                    ref,
                    "--head",
                    branch,
                    "--title",
                    "chore: agent sync",
                    "--body",
                    "Automated provider mirroring and resource vendoring update.",
                ],
                check=True,
            )

        return

    previous_head = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    run_git("pull", "--rebase", "origin", ref)

    registry = str(Path(agents_dir) / "external_resources.json")
    changed = subprocess.run(
        ["git", "diff", "--quiet", previous_head, "HEAD", "--", registry],
        check=False,
    )

    if changed.returncode == 1:
        subprocess.run(
            [
                sys.executable,
                "-m",
                "agent_sync",
                "vendor-resources",
                "--root",
                ".",
                "--agents-dir",
                agents_dir,
            ],
            check=True,
        )
    elif changed.returncode != 0:
        raise RuntimeError("Unable to compare external-resource registry revisions")

    mirror_providers(agents_dir, output_dir)

    stage_generated_paths(action_path, agents_dir, output_dir)

    if subprocess.run(["git", "diff", "--cached", "--quiet"], check=False).returncode != 0:
        run_git("commit", "--amend", "--no-edit")

    run_git("push", "origin", f"HEAD:{ref}")


if __name__ == "__main__":
    parser: argparse.ArgumentParser = argparse.ArgumentParser(description="Persist Agent Sync-owned output.")
    parser.add_argument("--action-path", type=Path, required=True)
    parser.add_argument("--agents-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--mode", choices=("commit", "pull-request"), required=True)
    parser.add_argument("--ref", required=True)
    arguments: argparse.Namespace = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    persist_changes(
        arguments.action_path,
        arguments.agents_dir,
        arguments.output_dir,
        arguments.mode,
        arguments.ref,
    )
