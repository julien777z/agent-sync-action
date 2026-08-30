import logging
from typing import Final

from pydantic import ValidationError

from agent_sync.models.vendors.ecc import EccInstallOutput, EccVendor

logger = logging.getLogger(__name__)

ECC_PACKAGE: Final[str] = "ecc-universal"


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


def installed_destinations(output: str) -> list[str]:
    """Return every destination an install run reported writing to."""

    try:
        return EccInstallOutput.model_validate_json(output).destination_paths
    except ValidationError:
        return []
