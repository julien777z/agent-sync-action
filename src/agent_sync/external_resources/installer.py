import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Final

import yaml

from agent_sync.config import ActionConfig
from agent_sync.document import parse_markdown
from agent_sync.models.document import SkillFrontMatter
from agent_sync.models.registry import ExternalSkill

SKILLS_CLI_AGENT: Final[str] = "universal"
UNQUOTED_DESCRIPTION: Final[re.Pattern[str]] = re.compile(
    r"^(description|short_description):[ \t]+([^\s\"'|>{\[\]&*!#].*:[ \t].*)$",
    re.MULTILINE,
)
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


def install_skill(
    skill: ExternalSkill, working_directory: Path, source_root: Path, config: ActionConfig
) -> None:
    """Install one skill from a downloaded repository snapshot."""

    normalize_upstream_front_matter(source_root)

    command = [
        "npx",
        "--yes",
        f"skills@{config.skills_cli_version}",
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


def normalize_upstream_front_matter(source_root: Path) -> None:
    """Quote malformed plain-text descriptions before upstream skill discovery."""

    for document in source_root.rglob("SKILL.md"):
        if document.is_symlink():
            continue

        content = document.read_text(encoding="utf-8")

        if not content.startswith("---\n"):
            continue

        front_matter = content[4:]
        delimiter = re.search(r"\n---(?:\n|$)", front_matter)

        if delimiter is None:
            continue

        header = front_matter[: delimiter.start()]
        body = front_matter[delimiter.end() :]

        try:
            yaml.safe_load(header)
        except yaml.YAMLError:
            repaired = UNQUOTED_DESCRIPTION.sub(
                lambda match: f"{match[1]}: {json.dumps(match[2], ensure_ascii=False)}",
                header,
            )

            if repaired == header:
                continue

            normalized = f"---\n{repaired}{delimiter.group()}{body}"

            try:
                yaml.safe_load(repaired)
            except yaml.YAMLError:
                continue

            document.write_text(normalized, encoding="utf-8")


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

    canonical_document = search_root / ".agents" / "skills" / name / "SKILL.md"

    if canonical_document in documents:
        return canonical_document.parent

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
