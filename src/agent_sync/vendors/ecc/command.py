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


def count_operations(output: str) -> int:
    """Return the number of file operations an install run reported."""

    try:
        return EccInstallOutput.model_validate_json(output).operation_count
    except ValidationError:
        return 0
