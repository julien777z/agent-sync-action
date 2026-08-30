import logging
import subprocess
from typing import Final

from agent_sync.models.vendors.ecc import EccVendor
from agent_sync.models.vendors.lock import VendorInstallResult
from agent_sync.vendors.ecc import command
from agent_sync.vendors.reconcile import relative_installed_paths
from agent_sync.workspace import Workspace

logger = logging.getLogger(__name__)

INSTALL_STATE_FILENAME: Final[str] = "ecc-install-state.json"


def install_ecc_vendor(workspace: Workspace, vendor: EccVendor, dry_run: bool) -> VendorInstallResult:
    """Install the ECC catalog into canonical sources and report what it wrote."""

    assert_target_writes_to_workspace(workspace, vendor)

    invocation = command.build_command(vendor, dry_run)
    logger.info("Installing ECC %s into %s", vendor.version, workspace.agents_dirname)

    result = subprocess.run(
        invocation,
        cwd=workspace.root,
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"`{' '.join(invocation)}` failed (exit {result.returncode}):"
            f"\n{result.stdout}\n{result.stderr}"
        )

    destinations = command.installed_destinations(result.stdout)
    logger.info(
        "  ECC %s: %d operation(s) %s.",
        vendor.profile or "custom modules",
        len(destinations),
        "planned" if dry_run else "applied",
    )

    if not dry_run:
        discard_install_state(workspace)

    return VendorInstallResult(paths=relative_installed_paths(workspace, destinations))


def assert_target_writes_to_workspace(workspace: Workspace, vendor: EccVendor) -> None:
    """Reject a target that writes outside the workspace's canonical source directory."""

    target_dirname = vendor.agents_dirname

    if target_dirname is not None and target_dirname != workspace.agents_dirname:
        raise RuntimeError(
            f"ECC target '{vendor.target}' writes to '{target_dirname}', "
            f"but canonical sources are in '{workspace.agents_dirname}'"
        )


def discard_install_state(workspace: Workspace) -> None:
    """Remove the timestamped machine-local install state the installer writes."""

    workspace.delete(workspace.agents_dir / INSTALL_STATE_FILENAME)
