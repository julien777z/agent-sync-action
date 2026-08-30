import logging

from pydantic import BaseModel, ConfigDict, Field

from agent_sync.models.vendors.ecc import EccVendor
from agent_sync.models.vendors.skills_cli import SkillsCliVendor

logger = logging.getLogger(__name__)


class Vendors(BaseModel):
    """The third-party systems Agent Sync can install from."""

    model_config = ConfigDict(extra="forbid", strict=True, populate_by_name=True)

    skills_cli: SkillsCliVendor | None = Field(
        default=None,
        validation_alias="skills-cli",
        serialization_alias="skills-cli",
    )
    ecc: EccVendor | None = None


class VendorRegistry(BaseModel):
    """The .agents/vendors.json vendor registry."""

    model_config = ConfigDict(extra="forbid", strict=True)

    version: int = 1
    vendors: Vendors = Field(default_factory=Vendors)
