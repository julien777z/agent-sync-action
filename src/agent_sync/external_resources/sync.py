import logging
from typing import Final

from agent_sync.external_resources.directories import update_external_directory
from agent_sync.external_resources.skills import update_external_skill
from agent_sync.models.registry import ExternalSkill, ResourcesRegistry
from agent_sync.utils import load_json_model
from agent_sync.workspace import Workspace

logger: logging.Logger = logging.getLogger(__name__)

EXTERNAL_RESOURCES_FILENAME: Final[str] = "external_resources.json"


def sync_external_resources(workspace: Workspace, dry_run: bool) -> None:
    """Update all registered external resources from their upstream sources."""

    registry_path = workspace.agents_dir / EXTERNAL_RESOURCES_FILENAME
    registry = load_json_model(registry_path, ResourcesRegistry)
    if registry is None:
        logger.info("No external-resource registry at %s; nothing to update.", registry_path)
        return

    for resource in registry.resources:
        if not resource.update_on_sync:
            continue

        if isinstance(resource, ExternalSkill):
            changed = update_external_skill(workspace, resource, workspace.agents_dir / "skills", dry_run)
            name = resource.local_name
        else:
            changed = update_external_directory(workspace, resource, dry_run)
            name = resource.name

        status = "would update" if dry_run and changed else "updated" if changed else "unchanged"
        logger.info("  %s (%s): %s", name, resource.repo, status)
