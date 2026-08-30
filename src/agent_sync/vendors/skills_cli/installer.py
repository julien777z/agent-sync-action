import logging
import subprocess
from pathlib import Path
from typing import Final

from agent_sync.models.vendors.skills_cli import SkillsCliVendor, VendoredSkill

logger = logging.getLogger(__name__)

SKILLS_CLI_AGENT: Final[str] = "universal"


def resolve_search_root(source_root: Path, skill: VendoredSkill) -> Path:
    """Return the snapshot directory holding one skill's upstream tree."""

    if skill.skills_path is None:
        return source_root

    search_root = source_root / skill.skills_path

    if not search_root.is_dir():
        raise RuntimeError(
            f"Skills path '{skill.skills_path}' for '{skill.name}' is not a directory in {skill.repo}"
        )

    return search_root


def install_skill(
    vendor: SkillsCliVendor,
    skill: VendoredSkill,
    install_directory: Path,
    search_root: Path,
) -> None:
    """Install one skill from a downloaded repository snapshot."""

    command = [
        "npx",
        "--yes",
        f"skills@{vendor.cli_version}",
        "add",
        str(search_root),
        "--skill",
        skill.upstream_skill,
        "-a",
        SKILLS_CLI_AGENT,
        "-y",
        "--copy",
    ]

    install_directory.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        command,
        cwd=install_directory,
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"`skills add {skill.repo} --skill {skill.upstream_skill}` failed "
            f"(exit {result.returncode}):\n{result.stdout}\n{result.stderr}"
        )
