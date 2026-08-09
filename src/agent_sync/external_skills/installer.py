import logging
import shutil
import subprocess
from pathlib import Path
from typing import Final

from agent_sync.config import ACTION_CONFIG
from agent_sync.document import parse_markdown
from agent_sync.models.document import SkillFrontMatter
from agent_sync.models.registry import ExternalSkill

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
LEGAL_FILE_PREFIXES: Final[tuple[str, ...]] = ("LICENSE", "COPYING", "NOTICE")


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


def locate_skill_directory(
    search_root: Path,
    name: str,
    excluded_root: Path | None = None,
) -> Path:
    """Locate one skill directory under a search root."""

    documents = sorted(
        path
        for path in search_root.rglob("SKILL.md")
        if excluded_root is None or excluded_root not in path.parents
    )
    directory_matches = [document.parent for document in documents if document.parent.name == name]

    if len(directory_matches) == 1:
        return directory_matches[0]

    metadata_matches = [
        document.parent
        for document in documents
        if parse_markdown(
            document.read_text(encoding="utf-8"),
            SkillFrontMatter,
            str(document),
        )[0].name
        == name
    ]

    if len(metadata_matches) == 1:
        return metadata_matches[0]

    if not directory_matches and not metadata_matches and len(documents) == 1:
        return documents[0].parent

    raise RuntimeError(
        f"Could not locate one skill '{name}' under {search_root} "
        f"(found: {[str(path.parent.relative_to(search_root)) for path in documents]})"
    )


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


def copy_legal_files(destination: Path, source_root: Path) -> None:
    """Copy repository-root legal files into the installed skill."""

    legal_files = [
        entry
        for entry in sorted(source_root.iterdir())
        if entry.is_file() and entry.name.upper().startswith(LEGAL_FILE_PREFIXES)
    ]

    for legal_file in legal_files:
        shutil.copy2(legal_file, destination / legal_file.name)
