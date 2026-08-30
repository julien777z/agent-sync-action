from pathlib import Path

from polyfactory.factories.pydantic_factory import ModelFactory

from agent_sync.config import ACTION_CONFIG
from agent_sync.document import render_front_matter
from agent_sync.models.document import RuleFrontMatter, SkillFrontMatter
from agent_sync.models.vendors.ecc import EccVendor
from agent_sync.models.vendors.registry import VendorRegistry, Vendors
from agent_sync.models.vendors.skills_cli import SkillsCliVendor, VendoredSkill

SOURCE_SKILL = "---\nname: sample\ndescription: A skill.\n---\n\nContent.\n"


class SkillFrontMatterFactory(ModelFactory[SkillFrontMatter]):
    """Build valid canonical skill metadata."""

    __model__ = SkillFrontMatter

    name = "sample-skill"
    description = "Does a thing."


class RuleFrontMatterFactory(ModelFactory[RuleFrontMatter]):
    """Build canonical rule metadata with deterministic defaults."""

    __model__ = RuleFrontMatter

    description = "A rule."
    globs = None
    always_apply = True
    starlark = None


class VendoredSkillFactory(ModelFactory[VendoredSkill]):
    """Build valid vendored-skill registrations."""

    __model__ = VendoredSkill

    name = "sample"
    repo = "example/repository"
    skill = None
    skills_path = None
    update_on_sync = True


class SkillsCliVendorFactory(ModelFactory[SkillsCliVendor]):
    """Build deterministic skills.sh CLI vendor configurations."""

    __model__ = SkillsCliVendor

    update_on_sync = True
    cli_version = ACTION_CONFIG.skills_cli_version

    @classmethod
    def skills(cls) -> list[VendoredSkill]:
        """Default to a vendor with no registered skills."""

        return []


class EccVendorFactory(ModelFactory[EccVendor]):
    """Build deterministic ECC vendor configurations."""

    __model__ = EccVendor

    update_on_sync = True
    version = ACTION_CONFIG.ecc_version
    target = "antigravity"
    profile = "core"

    @classmethod
    def modules(cls) -> list[str]:
        """Default to a profile-only ECC selection."""

        return []

    @classmethod
    def skills(cls) -> list[str]:
        """Default to a profile-only ECC selection."""

        return []


class VendorRegistryFactory(ModelFactory[VendorRegistry]):
    """Build deterministic vendor registries."""

    __model__ = VendorRegistry

    version = 1

    @classmethod
    def vendors(cls) -> Vendors:
        """Default to a registry declaring no vendors."""

        return Vendors()


def materialize_skill(
    path: Path,
    front_matter: SkillFrontMatter,
    body: str = "Body text.",
) -> None:
    """Write one generated canonical skill document."""

    path.parent.mkdir(parents=True)
    path.write_text(
        render_front_matter(front_matter, f"# {front_matter.name}\n\n{body}"),
        encoding="utf-8",
    )


def materialize_rule(
    path: Path,
    front_matter: RuleFrontMatter,
    body: str = "# Rule\n\nAlways be ruling.",
) -> None:
    """Write one generated canonical rule document."""

    raw_front_matter = front_matter.model_dump(
        by_alias=True,
        exclude_defaults=True,
        exclude_none=True,
    )

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_front_matter(raw_front_matter, body), encoding="utf-8")


def materialize_registry(path: Path, registry: VendorRegistry) -> None:
    """Write one vendor registry into canonical sources."""

    path.write_text(registry.model_dump_json(by_alias=True), encoding="utf-8")


def materialize_tree(base: Path, files: dict[str, str]) -> None:
    """Write a relative text-file mapping under one directory."""

    for relative, content in files.items():
        target = base / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
