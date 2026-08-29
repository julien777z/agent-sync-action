import logging
from typing import Final

from agent_sync.models.vendors import VendorRegistry
from agent_sync.utils import load_json_model
from agent_sync.vendors.ecc import install_ecc_vendor
from agent_sync.vendors.skills_cli import install_skills_cli_vendor
from agent_sync.workspace import Workspace

logger = logging.getLogger(__name__)

VENDORS_FILENAME: Final[str] = "vendors.json"


def install_vendors(workspace: Workspace, dry_run: bool) -> bool:
    """Install every enabled vendor and report whether a dry run found changes."""

    registry_path = workspace.agents_dir / VENDORS_FILENAME
    registry = load_json_model(registry_path, VendorRegistry)

    if registry is None:
        logger.info("No vendor registry at %s; nothing to install.", registry_path)

        return False

    vendors = registry.vendors
    differences_found = False

    if vendors.skills_cli is not None and vendors.skills_cli.update_on_sync:
        differences_found |= install_skills_cli_vendor(workspace, vendors.skills_cli, dry_run)

    if vendors.ecc is not None and vendors.ecc.update_on_sync:
        differences_found |= install_ecc_vendor(workspace, vendors.ecc, dry_run)

    return differences_found
