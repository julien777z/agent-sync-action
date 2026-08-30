import logging
import shutil
import tempfile
from pathlib import Path

from agent_sync.models.vendors.lock import VendorInstallResult
from agent_sync.models.vendors.skills_cli import (
    SkillsCliVendor,
    VendoredSkill,
    VendoredSkillResult,
)
from agent_sync.utils import trees_differ
from agent_sync.vendors import skills
from agent_sync.vendors.skills_cli import assets, discovery, github, installer
from agent_sync.workspace import Workspace

logger = logging.getLogger(__name__)


def install_skills_cli_vendor(
    workspace: Workspace,
    vendor: SkillsCliVendor,
    dry_run: bool,
) -> VendorInstallResult:
    """Update every enabled skill and report what it wrote."""

    updatable_skills = [skill for skill in vendor.skills if skill.update_on_sync]

    if not updatable_skills:
        logger.info("No skills are enabled for sync; nothing to update.")

        return VendorInstallResult()

    skills_dir = workspace.agents_dir / "skills"
    results = [
        result
        for repository, skills in group_skills_by_repository(updatable_skills).items()
        for result in update_repository_skills(workspace, vendor, repository, skills, skills_dir, dry_run)
    ]

    report_results(results, dry_run)

    return VendorInstallResult(
        differences_found=dry_run and any(result.changed for result in results),
        paths=sorted(workspace.relative_path(skills_dir / skill.name) for skill in updatable_skills),
    )


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

    search_root = installer.resolve_search_root(source_root, skill)
    install_directory = working_directory / "install" / skill.name

    installer.install_skill(vendor, skill, install_directory, search_root)

    installed = discovery.locate_skill_directory(install_directory, skill.name)

    if discovery.is_search_root_skill(search_root, skill):
        assets.supplement_root_assets(installed, search_root)

    assets.copy_legal_files(installed, source_root)
    skills.normalize_installed_skill(installed, skill.name, f"https://github.com/{skill.repo}")

    destination = skills_dir / skill.name
    changed = trees_differ(installed, destination)

    if changed and not dry_run:
        workspace.delete(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(installed, destination)

    return changed


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
