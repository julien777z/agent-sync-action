import logging
import shutil
import tempfile
from pathlib import Path
from typing import Final

from agent_sync.models.registry import ExternalSkill, SkillsRegistry, VendorResult
from agent_sync.utils import load_json_model, trees_differ
from agent_sync.vendor import github, installer
from agent_sync.workspace import Workspace

logger = logging.getLogger(__name__)

REGISTRY_FILENAME: Final[str] = "skills.json"


def vendor_skills(workspace: Workspace, dry_run: bool) -> bool:
    """Vendor external skills and report whether a dry run found changes."""

    registry_path = workspace.agents_dir / REGISTRY_FILENAME
    registry = load_json_model(registry_path, SkillsRegistry)

    if registry is None:
        logger.info("No external-skill registry at %s; nothing to vendor.", registry_path)

        return False

    updatable_skills = [skill for skill in registry.skills if skill.automatic_updates]

    if not updatable_skills:
        logger.info("No external skills have automatic updates enabled; nothing to vendor.")

        return False

    skills_dir = workspace.agents_dir / "skills"
    results = [
        VendorResult(
            skill=skill,
            changed=vendor_skill(workspace, skill, skills_dir, dry_run),
        )
        for skill in updatable_skills
    ]

    report_results(results, dry_run)

    return dry_run and any(result.changed for result in results)


def vendor_skill(
    workspace: Workspace,
    skill: ExternalSkill,
    skills_dir: Path,
    dry_run: bool,
) -> bool:
    """Vendor one external skill from a single immutable source snapshot."""

    logger.info("Vendoring %s from %s", skill.name, skill.repo)

    with tempfile.TemporaryDirectory(prefix="agent-sync-skill-") as temporary_directory:
        working_directory = Path(temporary_directory)
        revision = github.resolve_revision(skill.repo)
        source_root = github.download_snapshot(
            skill.repo,
            revision,
            working_directory / "source",
        )

        installer.install_skill(skill, working_directory, source_root)
        installed = installer.locate_installed_skill(working_directory, source_root, skill.name)
        skill_path = installer.read_skill_path(working_directory)

        if skill_path is not None and "/" not in skill_path:
            installer.supplement_root_assets(installed, source_root)

        destination = skills_dir / skill.name
        changed = trees_differ(installed, destination)

        if changed and not dry_run:
            workspace.delete(destination)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(installed, destination)

    return changed


def report_results(results: list[VendorResult], dry_run: bool) -> None:
    """Log the result of each external skill vendoring operation."""

    for result in results:
        if result.changed:
            status = "would update" if dry_run else "updated"
        else:
            status = "unchanged"

        logger.info("  %s (%s): %s", result.skill.name, result.skill.repo, status)

    changed_count = sum(result.changed for result in results)
    verb = "would change" if dry_run else "changed"
    logger.info("%d of %d external skill(s) %s.", changed_count, len(results), verb)
