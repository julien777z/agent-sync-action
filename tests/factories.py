from pathlib import Path

from polyfactory.factories.pydantic_factory import ModelFactory

from agent_sync.document import render_front_matter
from agent_sync.models.document import RuleFrontMatter, SkillFrontMatter
from agent_sync.models.registry import (
    ExternalSkill,
    SkillLockEntry,
    SkillsLock,
    SkillsRegistry,
)
from agent_sync.workspace import Workspace


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


class ExternalSkillFactory(ModelFactory[ExternalSkill]):
    """Build valid external-skill registrations."""

    __model__ = ExternalSkill

    name = "sample"
    repo = "example/repository"
    skill = None
    automatic_updates = True


class SkillsRegistryFactory(ModelFactory[SkillsRegistry]):
    """Build deterministic external-skill registries."""

    __model__ = SkillsRegistry

    version = 1

    @classmethod
    def skills(cls) -> list[ExternalSkill]:
        """Default to an empty external-skill registry."""

        return []


class SkillLockEntryFactory(ModelFactory[SkillLockEntry]):
    """Build deterministic installer lock entries."""

    __model__ = SkillLockEntry

    skill_path = "skills/sample/SKILL.md"


class SkillsLockFactory(ModelFactory[SkillsLock]):
    """Build deterministic installer lock files."""

    __model__ = SkillsLock

    @classmethod
    def skills(cls) -> dict[str, SkillLockEntry]:
        """Build one default installer lock entry."""

        return {"skill": SkillLockEntryFactory.build()}


def materialize_skill(
    workspace: Workspace,
    slug: str,
    body: str = "Body text.",
) -> Path:
    """Write one generated canonical skill document."""

    front_matter = SkillFrontMatterFactory.build(name=slug)
    skill_dir = workspace.agents_dir / "skills" / slug
    skill_dir.mkdir(parents=True)
    source = skill_dir / "SKILL.md"
    source.write_text(
        render_front_matter(front_matter, f"# {slug}\n\n{body}"),
        encoding="utf-8",
    )

    return source


def materialize_rule(
    workspace: Workspace,
    slug: str,
    body: str = "# Rule\n\nAlways be ruling.",
) -> Path:
    """Write one generated canonical rule document."""

    front_matter = RuleFrontMatterFactory.build(name="removed")
    raw_front_matter = front_matter.model_dump(
        by_alias=True,
        exclude_defaults=True,
        exclude_none=True,
    )
    rules_dir = workspace.agents_dir / "rules"
    rules_dir.mkdir(parents=True, exist_ok=True)
    source = rules_dir / f"{slug}.md"
    source.write_text(render_front_matter(raw_front_matter, body), encoding="utf-8")

    return source


def materialize_registry(workspace: Workspace, registry: SkillsRegistry) -> None:
    """Write one external-skill registry into canonical sources."""

    path = workspace.agents_dir / "skills.json"
    path.write_text(registry.model_dump_json(), encoding="utf-8")


def materialize_skills_lock(directory: Path, lock: SkillsLock) -> None:
    """Write one installer lock file."""

    (directory / "skills-lock.json").write_text(
        lock.model_dump_json(by_alias=True),
        encoding="utf-8",
    )


def materialize_tree(base: Path, files: dict[str, str]) -> None:
    """Write a relative text-file mapping under one directory."""

    for relative, content in files.items():
        target = base / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
