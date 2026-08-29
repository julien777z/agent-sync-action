import logging
import subprocess
from typing import Final

from pydantic import ValidationError

from agent_sync.models.vendors import EccInstallOutput, EccVendor
from agent_sync.workspace import Workspace

logger = logging.getLogger(__name__)

ECC_PACKAGE: Final[str] = "ecc-universal"
INSTALL_STATE_FILENAME: Final[str] = "ecc-install-state.json"


def install_ecc_vendor(workspace: Workspace, vendor: EccVendor, dry_run: bool) -> bool:
    """Install the ECC catalog into canonical sources and report planned operations."""

    assert_target_writes_to_workspace(workspace, vendor)

    command = build_command(vendor, dry_run)
    logger.info("Installing ECC %s into %s", vendor.version, workspace.agents_dirname)

    result = subprocess.run(
        command,
        cwd=workspace.root,
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"`{' '.join(command)}` failed (exit {result.returncode}):\n{result.stdout}\n{result.stderr}"
        )

    logger.info(
        "  ECC %s: %d operation(s) %s.",
        vendor.profile or "custom modules",
        count_operations(result.stdout),
        "planned" if dry_run else "applied",
    )

    if not dry_run:
        discard_install_state(workspace)

    return False


def discard_install_state(workspace: Workspace) -> None:
    """Remove the local install-state file the installer writes beside canonical sources."""

    # It records one machine's install with a timestamp, so keeping it would commit a new
    # revision on every scheduled run. Canonical sources are installed from the registry.
    workspace.delete(workspace.agents_dir / INSTALL_STATE_FILENAME)


def assert_target_writes_to_workspace(workspace: Workspace, vendor: EccVendor) -> None:
    """Reject a target that writes outside the workspace's canonical source directory."""

    target_dirname = vendor.agents_dirname

    if target_dirname is not None and target_dirname != workspace.agents_dirname:
        raise RuntimeError(
            f"ECC target '{vendor.target}' writes to '{target_dirname}', "
            f"but canonical sources are in '{workspace.agents_dirname}'"
        )


def build_command(vendor: EccVendor, dry_run: bool) -> list[str]:
    """Build the ECC selective-install invocation for one vendor configuration."""

    command = [
        "npx",
        "--yes",
        f"{ECC_PACKAGE}@{vendor.version}",
        "install",
        "--target",
        vendor.target,
    ]

    if vendor.profile is not None:
        command += ["--profile", vendor.profile]

    if vendor.modules:
        command += ["--modules", ",".join(vendor.modules)]

    if vendor.skills:
        command += ["--skills", ",".join(vendor.skills)]

    if dry_run:
        command.append("--dry-run")

    return command + ["--json"]


def count_operations(output: str) -> int:
    """Return the number of file operations an install run reported."""

    try:
        return EccInstallOutput.model_validate_json(output).operation_count
    except ValidationError:
        return 0
