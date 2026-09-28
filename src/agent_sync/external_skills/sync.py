import logging
import os
import shutil
import tempfile
from pathlib import Path
from typing import Final

from agent_sync.document import parse_markdown, render_front_matter
from agent_sync.external_skills import github, installer
from agent_sync.models.document import SkillFrontMatter
from agent_sync.models.registry import ExternalSkill, ExternalSkillResult, SkillsRegistry
from agent_sync.skills import locate_skill_by_name
from agent_sync.utils import load_json_model, trees_differ
from agent_sync.workspace import Workspace

logger = logging.getLogger(__name__)

EXTERNAL_SKILLS_FILENAME: Final[str] = "external_skills.json"


def sync_external_skills(workspace: Workspace, dry_run: bool) -> None:
    """Update external skills or report pending updates."""

    registry_path = workspace.agents_dir / EXTERNAL_SKILLS_FILENAME
    registry = load_json_model(registry_path, SkillsRegistry)

    if registry is None:
        logger.info("No external-skill registry at %s; nothing to update.", registry_path)

        return

    updatable_skills = [skill for skill in registry.skills if skill.update_on_sync]

    if not updatable_skills:
        logger.info("No external skills are enabled for sync; nothing to update.")

        return

    skills_dir = workspace.agents_dir / "skills"
    results = [
        ExternalSkillResult(
            skill=skill,
            changed=update_external_skill(workspace, skill, skills_dir, dry_run),
        )
        for skill in updatable_skills
    ]

    report_results(results, dry_run)


def update_external_skill(
    workspace: Workspace,
    skill: ExternalSkill,
    skills_dir: Path,
    dry_run: bool,
) -> bool:
    """Update one external skill from a single immutable source snapshot."""

    logger.info("Updating %s from %s", skill.local_name, skill.repo)

    with tempfile.TemporaryDirectory(prefix="agent-sync-skill-") as temporary_directory:
        working_directory = Path(temporary_directory)
        revision = github.resolve_revision(skill.repo)
        source_root = github.download_snapshot(
            skill.repo,
            revision,
            working_directory / "source",
        )

        installer.install_skill(skill, working_directory, source_root)
        installed = installer.locate_skill_directory(
            working_directory,
            skill.upstream_skill,
            excluded_root=source_root,
        )
        source_skill = installer.locate_skill_directory(source_root, skill.upstream_skill)

        if source_skill == source_root:
            installer.supplement_root_assets(installed, source_root)

        installer.copy_legal_files(installed, source_root)

        normalize_skill_metadata(installed, skill)

        destination = skills_dir / skill.relative_path
        current = locate_skill_by_name(skills_dir, skill.local_name)
        previous = (
            locate_skill_by_name(skills_dir, skill.name)
            if skill.skill_name_override is not None and skill.name != skill.local_name
            else None
        )
        if current is None:
            current = previous
        elif previous is not None and previous != current:
            raise RuntimeError(
                f"Both '{skill.name}' and '{skill.local_name}' exist; resolve the old skill before syncing"
            )
        if current is not None:
            if current.is_symlink():
                raise RuntimeError(f"Skill directory is a link, not a managed installation: {current}")
            current_document = current / "SKILL.md"
            front_matter, _ = parse_markdown(
                current_document.read_text(encoding="utf-8"),
                SkillFrontMatter,
                str(current_document),
            )
            if (front_matter.metadata or {}).get("source") != f"https://github.com/{skill.repo}":
                raise RuntimeError(f"Skill directory is not managed by {skill.repo}: {current}")
        changed = current not in (None, destination) or trees_differ(installed, destination)

        if changed and not dry_run:
            if destination.exists() or destination.is_symlink():
                if current != destination:
                    raise RuntimeError(f"Skill destination already exists: {destination}")
            for parent in destination.parents:
                if parent == skills_dir:
                    break
                if parent.is_symlink() or (parent / "SKILL.md").exists():
                    raise RuntimeError(f"Skill category is occupied by a skill or link: {parent}")
            if current is not None and current != destination and current in destination.parents:
                raise RuntimeError(f"Skill destination is inside its existing directory: {destination}")

            destination.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(
                prefix=".agent-sync-skill-", dir=destination.parent
            ) as stage_root:
                stage = Path(stage_root)
                staged_skill = stage / "skill"
                old_skill = stage / "old"
                shutil.copytree(installed, staged_skill)
                if current is not None:
                    os.replace(current, old_skill)
                try:
                    os.replace(staged_skill, destination)
                except OSError:
                    if current is not None:
                        os.replace(old_skill, current)
                    raise

            if current is not None and current != destination:
                folder = current.parent
                while folder != skills_dir and folder.is_dir() and not any(folder.iterdir()):
                    folder.rmdir()
                    folder = folder.parent

    return changed


def normalize_skill_metadata(installed: Path, skill: ExternalSkill) -> None:
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
                    "name": skill.local_name,
                    "metadata": metadata,
                }
            ),
            body,
        ),
        encoding="utf-8",
    )

    provider_metadata = installed / "agents"
    if provider_metadata.is_symlink():
        raise RuntimeError(f"Skill provider metadata directory is a link: {provider_metadata}")

    forbidden_metadata = provider_metadata / "openai.yaml"
    if forbidden_metadata.is_symlink() or forbidden_metadata.is_file():
        forbidden_metadata.unlink()
        if not any(provider_metadata.iterdir()):
            provider_metadata.rmdir()


def report_results(results: list[ExternalSkillResult], dry_run: bool) -> None:
    """Log the result of each external skill update."""

    for result in results:
        if result.changed:
            status = "would update" if dry_run else "updated"
        else:
            status = "unchanged"

        logger.info("  %s (%s): %s", result.skill.local_name, result.skill.repo, status)

    changed_count = sum(result.changed for result in results)
    verb = "would change" if dry_run else "changed"
    logger.info("%d of %d external skill(s) %s.", changed_count, len(results), verb)
