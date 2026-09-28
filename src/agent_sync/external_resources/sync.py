import logging
from enum import Enum, auto
from typing import Final

from agent_sync.config import ActionConfig
from agent_sync.external_resources.directories import update_external_directory
from agent_sync.external_resources.skills import update_external_skill
from agent_sync.models.registry import ExternalSkill, ResourcesRegistry
from agent_sync.models.workspace import Workspace
from agent_sync.utils import load_json_model
from agent_sync.workspace import agents_dir

logger: logging.Logger = logging.getLogger(__name__)

EXTERNAL_RESOURCES_FILENAME: Final[str] = "external_resources.json"


class ResourceUpdateStatus(Enum):
    """Describe the result of syncing one external resource."""

    WOULD_UPDATE = auto()
    UPDATED = auto()
    UNCHANGED = auto()


def sync_external_resources(workspace: Workspace, dry_run: bool, config: ActionConfig) -> None:
    """Update all registered external resources from their upstream sources."""

    registry_path = agents_dir(workspace) / EXTERNAL_RESOURCES_FILENAME
    registry = load_json_model(registry_path, ResourcesRegistry)
    if registry is None:
        logger.info("No external-resource registry at %s; nothing to update.", registry_path)
        return

    for resource in registry.resources:
        if not resource.update_on_sync:
            continue

        if isinstance(resource, ExternalSkill):
            changed = update_external_skill(
                workspace, resource, agents_dir(workspace) / "skills", dry_run, config
            )
            name = resource.local_name
        else:
            changed = update_external_directory(workspace, resource, dry_run)
            name = resource.name

        status = ResourceUpdateStatus.UNCHANGED
        if changed:
            status = ResourceUpdateStatus.WOULD_UPDATE if dry_run else ResourceUpdateStatus.UPDATED

        logger.info("  %s (%s): %s", name, resource.repo, status.name.lower().replace("_", " "))
