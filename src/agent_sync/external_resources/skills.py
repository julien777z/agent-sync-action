import logging
import tempfile
from pathlib import Path
from typing import Final

from agent_sync.config import ActionConfig
from agent_sync.document import parse_markdown, render_front_matter
from agent_sync.external_resources.github import copy_legal_files, download_snapshot, resolve_revision
from agent_sync.external_resources.installer import (
    install_skill,
    locate_skill_directory,
    supplement_root_assets,
)
from agent_sync.models.document import SkillFrontMatter, SkillMetadataUpdate
from agent_sync.models.registry import ExternalSkill
from agent_sync.models.settings import Workspace
from agent_sync.skills import locate_skill_by_name
from agent_sync.utils import replace_tree, trees_differ

logger: logging.Logger = logging.getLogger(__name__)
UPSTREAM_SHORT_DESCRIPTION_KEY: Final[str] = "agent_sync_upstream_short_description"
LOCAL_SHORT_DESCRIPTION_KEY: Final[str] = "agent_sync_local_short_description"


def update_external_skill(
    workspace: Workspace,
    skill: ExternalSkill,
    skills_dir: Path,
    dry_run: bool,
    config: ActionConfig,
) -> bool:
    """Update one external skill from a single immutable source snapshot."""

    logger.info("Updating %s from %s", skill.local_name, skill.repo)

    with tempfile.TemporaryDirectory(prefix="agent-sync-skill-") as temporary_directory:
        working_directory = Path(temporary_directory)
        revision = resolve_revision(skill.repo)
        source_root = download_snapshot(
            skill.repo,
            revision,
            working_directory / "source",
        )

        install_skill(skill, working_directory, source_root, config)

        installed = locate_skill_directory(
            working_directory,
            skill.upstream_skill,
            excluded_root=source_root,
        )
        source_skill = locate_skill_directory(source_root, skill.upstream_skill)

        if source_skill == source_root:
            supplement_root_assets(installed, source_root)

        copy_legal_files(installed, source_root, overwrite_existing=True)

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

        short_description: str | None = None
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

            local_summary = (front_matter.model_extra or {}).get("short_description")
            current_metadata = front_matter.metadata or {}

            if (
                isinstance(local_summary, str)
                and UPSTREAM_SHORT_DESCRIPTION_KEY not in current_metadata
                and LOCAL_SHORT_DESCRIPTION_KEY not in current_metadata
            ):
                raise RuntimeError(
                    f"Skill summary origin is unknown: {current_document}. "
                    f"Set metadata.{LOCAL_SHORT_DESCRIPTION_KEY}: true to keep the local summary, "
                    "or remove short_description to use the upstream value."
                )

            upstream_summary = current_metadata.get(UPSTREAM_SHORT_DESCRIPTION_KEY)
            locally_authored = current_metadata.get(LOCAL_SHORT_DESCRIPTION_KEY) is True

            if isinstance(local_summary, str) and (locally_authored or local_summary != upstream_summary):
                short_description = local_summary

        normalize_skill_metadata(installed, skill, short_description)

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

            replace_tree(installed, destination, current)

            if current is not None and current != destination:
                folder = current.parent
                while folder != skills_dir and folder.is_dir() and not any(folder.iterdir()):
                    folder.rmdir()

                    folder = folder.parent

    return changed


def normalize_skill_metadata(
    installed: Path, skill: ExternalSkill, short_description: str | None = None
) -> None:
    """Rewrite installed skill metadata for its local canonical directory."""

    document = installed / "SKILL.md"
    content = document.read_text(encoding="utf-8")
    front_matter, body = parse_markdown(content, SkillFrontMatter, str(document))
    metadata = dict(front_matter.metadata or {})
    metadata["source"] = f"https://github.com/{skill.repo}"

    upstream_summary = (front_matter.model_extra or {}).get("short_description")

    if isinstance(upstream_summary, str):
        metadata[UPSTREAM_SHORT_DESCRIPTION_KEY] = upstream_summary
    else:
        metadata.pop(UPSTREAM_SHORT_DESCRIPTION_KEY, None)

    if short_description is not None:
        metadata[LOCAL_SHORT_DESCRIPTION_KEY] = True
    else:
        metadata.pop(LOCAL_SHORT_DESCRIPTION_KEY, None)

    updates = SkillMetadataUpdate(name=skill.local_name, metadata=metadata)

    if short_description is not None:
        updates["short_description"] = short_description

    document.write_text(
        render_front_matter(
            front_matter.model_copy(update=updates),
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
