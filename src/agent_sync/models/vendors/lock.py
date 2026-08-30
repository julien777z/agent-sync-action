import logging

from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)


class VendorInstallResult(BaseModel):
    """What one vendor installed and whether a dry run found changes."""

    model_config = ConfigDict(frozen=True)

    differences_found: bool = False
    paths: list[str] = Field(default_factory=list[str])


class VendorLockEntry(BaseModel):
    """The repository-relative paths one vendor installed."""

    model_config = ConfigDict(extra="forbid", strict=True)

    paths: list[str] = Field(default_factory=list[str])


class VendorLock(BaseModel):
    """The .agents/vendors.lock.json record of installed vendor paths."""

    model_config = ConfigDict(extra="forbid", strict=True)

    version: int = 1
    vendors: dict[str, VendorLockEntry] = Field(default_factory=dict[str, VendorLockEntry])
