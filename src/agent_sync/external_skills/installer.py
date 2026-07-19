import logging
import shutil
import subprocess
from pathlib import Path
from typing import Final

from pydantic import ValidationError

from agent_sync.config import ACTION_CONFIG
from agent_sync.models.registry import ExternalSkill, SkillsLock

logger = logging.getLogger(__name__)

SKILLS_CLI_AGENT: Final[str] = "universal"
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


def install_skill(skill: ExternalSkill, working_directory: Path, source_root: Path) -> None:
    """Install one skill from a downloaded repository snapshot."""

    command = [
        "npx",
        "--yes",
        f"skills@{ACTION_CONFIG.skills_cli_version}",
        "add",
        str(source_root),
        "--skill",
        skill.upstream_skill,
        "-a",
        SKILLS_CLI_AGENT,
        "-y",
        "--copy",
    ]

    result = subprocess.run(
        command,
        cwd=working_directory,
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"`skills add {skill.repo} --skill {skill.upstream_skill}` failed "
            f"(exit {result.returncode}):\n{result.stdout}\n{result.stderr}"
        )


def locate_installed_skill(working_directory: Path, source_root: Path, name: str) -> Path:
    """Locate the single skill directory produced by the installer."""

    candidates = sorted(
        {
            path.parent
            for path in working_directory.rglob("SKILL.md")
            if source_root not in path.parents
        },
        key=str,
    )
    matching = [candidate for candidate in candidates if candidate.name == name]

    if len(matching) == 1:
        return matching[0]

    if not matching and len(candidates) == 1:
        return candidates[0]

    raise RuntimeError(
        f"Could not locate one installed skill '{name}' under {working_directory} "
        f"(found: {[str(path.relative_to(working_directory)) for path in candidates]})"
    )


def read_skill_path(working_directory: Path) -> str | None:
    """Read the sole installer lock entry's canonical skill path."""

    path = working_directory / "skills-lock.json"

    if not path.exists():
        return None

    try:
        lock = SkillsLock.model_validate_json(path.read_text(encoding="utf-8"))
    except ValidationError as exc:
        raise RuntimeError(f"Invalid skill installer lock at {path}: {exc}") from exc

    if len(lock.skills) != 1:
        return None

    return next(iter(lock.skills.values())).skill_path


def supplement_root_assets(destination: Path, source_root: Path) -> None:
    """Copy repository-root skill assets omitted by the installer."""

    for entry in sorted(source_root.iterdir()):
        if entry.name.startswith(".") or entry.name in TARBALL_EXCLUDES:
            continue

        target = destination / entry.name

        if entry.is_dir():
            shutil.copytree(entry, target, dirs_exist_ok=True)
        else:
            shutil.copy2(entry, target)
