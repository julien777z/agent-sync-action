import shutil
import subprocess
from pathlib import Path
from typing import Final

from pydantic import ValidationError

from agent_sync.models.registry import ExternalSkill, SkillsLock

SKILLS_CLI_VERSION: Final[str] = "1.5.13"
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
        f"skills@{SKILLS_CLI_VERSION}",
        "add",
        str(source_root),
        "--skill",
        skill.upstream_skill,
        "-a",
        "claude-code",
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


def locate_installed_skill(working_directory: Path, name: str) -> Path:
    """Locate the single skill directory produced by the installer."""

    expected = working_directory / ".claude" / "skills" / name
    if expected.is_dir():
        return expected

    installed_root = working_directory / ".claude" / "skills"
    candidates = (
        [path for path in installed_root.iterdir() if path.is_dir()]
        if installed_root.exists()
        else []
    )
    if len(candidates) == 1:
        return candidates[0]

    raise RuntimeError(
        f"Could not locate installed skill '{name}' under {installed_root} "
        f"(found: {[path.name for path in candidates]})"
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
