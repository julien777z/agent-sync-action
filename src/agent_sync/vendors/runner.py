import logging
from typing import Final

from agent_sync.models.vendors.lock import VendorInstallResult
from agent_sync.models.vendors.registry import VendorRegistry, Vendors
from agent_sync.utils import load_json_model
from agent_sync.vendors.ecc.install import install_ecc_vendor
from agent_sync.vendors.reconcile import reconcile_installed_paths
from agent_sync.vendors.skills_cli.sync import install_skills_cli_vendor
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

    results = run_vendors(workspace, registry.vendors, dry_run)
    differences_found = any(result.differences_found for result in results.values())
    installed = {name: result.paths for name, result in results.items()}

    return reconcile_installed_paths(workspace, installed, declared_vendors(registry.vendors), dry_run) or (
        differences_found
    )


def declared_vendors(vendors: Vendors) -> set[str]:
    """Return the name of every vendor the registry declares."""

    return {
        name
        for name, vendor in (("skills-cli", vendors.skills_cli), ("ecc", vendors.ecc))
        if vendor is not None
    }


def run_vendors(workspace: Workspace, vendors: Vendors, dry_run: bool) -> dict[str, VendorInstallResult]:
    """Install every vendor enabled for sync and return what each one wrote."""

    results: dict[str, VendorInstallResult] = {}

    if vendors.skills_cli is not None and vendors.skills_cli.update_on_sync:
        results["skills-cli"] = install_skills_cli_vendor(workspace, vendors.skills_cli, dry_run)

    if vendors.ecc is not None and vendors.ecc.update_on_sync:
        results["ecc"] = install_ecc_vendor(workspace, vendors.ecc, dry_run)

    return results
