import logging
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Final

from agent_sync.document import parse_markdown, render_front_matter
from agent_sync.models.document import SkillFrontMatter
from agent_sync.models.vendors import SkillsCliVendor, VendoredSkill, VendoredSkillResult
from agent_sync.utils import trees_differ
from agent_sync.vendors import github
from agent_sync.workspace import Workspace

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


def install_skills_cli_vendor(workspace: Workspace, vendor: SkillsCliVendor, dry_run: bool) -> bool:
    """Update every enabled skill and report whether a dry run found changes."""

    updatable_skills = [skill for skill in vendor.skills if skill.update_on_sync]

    if not updatable_skills:
        logger.info("No skills are enabled for sync; nothing to update.")

        return False

    skills_dir = workspace.agents_dir / "skills"
    results = [
        result
        for repository, skills in group_skills_by_repository(updatable_skills).items()
        for result in update_repository_skills(workspace, vendor, repository, skills, skills_dir, dry_run)
    ]

    report_results(results, dry_run)

    return dry_run and any(result.changed for result in results)


def group_skills_by_repository(skills: list[VendoredSkill]) -> dict[str, list[VendoredSkill]]:
    """Group registry entries by the repository they are vendored from."""

    grouped: dict[str, list[VendoredSkill]] = {}

    for skill in skills:
        grouped.setdefault(skill.repo, []).append(skill)

    return grouped


def update_repository_skills(
    workspace: Workspace,
    vendor: SkillsCliVendor,
    repository: str,
    skills: list[VendoredSkill],
    skills_dir: Path,
    dry_run: bool,
) -> list[VendoredSkillResult]:
    """Update every registered skill from one immutable repository snapshot."""

    logger.info("Updating %d skill(s) from %s", len(skills), repository)

    with tempfile.TemporaryDirectory(prefix="agent-sync-skills-") as temporary_directory:
        working_directory = Path(temporary_directory)
        revision = github.resolve_revision(repository)
        source_root = github.download_snapshot(repository, revision, working_directory / "source")

        return [
            VendoredSkillResult(
                skill=skill,
                changed=vendor_skill(
                    workspace,
                    vendor,
                    skill,
                    skills_dir,
                    source_root,
                    working_directory,
                    dry_run,
                ),
            )
            for skill in skills
        ]


def vendor_skill(
    workspace: Workspace,
    vendor: SkillsCliVendor,
    skill: VendoredSkill,
    skills_dir: Path,
    source_root: Path,
    working_directory: Path,
    dry_run: bool,
) -> bool:
    """Vendor one skill from an already downloaded repository snapshot."""

    search_root = resolve_search_root(source_root, skill)
    install_directory = working_directory / "install" / skill.name

    install_skill(vendor, skill, install_directory, search_root)

    installed = locate_skill_directory(install_directory, skill.name)

    if is_search_root_skill(search_root, skill):
        supplement_root_assets(installed, search_root)

    copy_legal_files(installed, source_root)
    normalize_skill_metadata(installed, skill)

    destination = skills_dir / skill.name
    changed = trees_differ(installed, destination)

    if changed and not dry_run:
        workspace.delete(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(installed, destination)

    return changed


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


def locate_skill_directory(search_root: Path, name: str) -> Path:
    """Locate one skill directory under a search root."""

    documents = sorted(search_root.rglob("SKILL.md"))
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


def is_search_root_skill(search_root: Path, skill: VendoredSkill) -> bool:
    """Report whether the searched directory is itself the selected upstream skill."""

    document = search_root / "SKILL.md"

    if not document.is_file():
        return False

    front_matter, _ = parse_markdown(
        document.read_text(encoding="utf-8"),
        SkillFrontMatter,
        str(document),
    )

    return front_matter.name == skill.upstream_skill


def supplement_root_assets(destination: Path, search_root: Path) -> None:
    """Copy sibling skill assets omitted by the installer."""

    for entry in sorted(search_root.iterdir()):
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


def normalize_skill_metadata(installed: Path, skill: VendoredSkill) -> None:
    """Rewrite installed skill metadata for its local canonical directory."""

    document = installed / "SKILL.md"
    content = document.read_text(encoding="utf-8")
    front_matter, body = parse_markdown(content, SkillFrontMatter, str(document))
    metadata = dict(front_matter.metadata or {})
    metadata["source"] = f"https://github.com/{skill.repo}"

    document.write_text(
        render_front_matter(
            front_matter.model_copy(
                update={
                    "name": skill.name,
                    "metadata": metadata,
                }
            ),
            body,
        ),
        encoding="utf-8",
    )


def report_results(results: list[VendoredSkillResult], dry_run: bool) -> None:
    """Log the result of each vendored skill update."""

    for result in results:
        if result.changed:
            status = "would update" if dry_run else "updated"
        else:
            status = "unchanged"

        logger.info("  %s (%s): %s", result.skill.name, result.skill.repo, status)

    changed_count = sum(result.changed for result in results)
    verb = "would change" if dry_run else "changed"
    logger.info("%d of %d vendored skill(s) %s.", changed_count, len(results), verb)
