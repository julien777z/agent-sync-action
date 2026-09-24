from pathlib import Path

import pytest
from polyfactory.factories.pydantic_factory import ModelFactory

from agent_sync.document import render_front_matter
from agent_sync.external_skills import github, installer
from agent_sync.generation.context import GenerationContext, load_generation_context
from agent_sync.models.document import RuleFrontMatter, SkillFrontMatter
from agent_sync.models.registry import ExternalSkill, SkillsRegistry
from agent_sync.source import load_source_config
from agent_sync.workspace import Workspace

ROOT_LEVEL_SKILL = ExternalSkill(
    name="local-skill",
    repo="example/repository",
    skill="upstream-skill",
    update_on_sync=True,
)


def load_context(workspace: Workspace) -> GenerationContext:
    """Load generation inputs from one test workspace."""

    return load_generation_context(workspace, load_source_config(workspace))


def stub_root_level_upstream(monkeypatch: pytest.MonkeyPatch) -> None:
    """Serve a synthetic upstream repository whose root is the skill."""

    upstream_document = "---\nname: upstream-skill\ndescription: A skill.\n---\n\nContent.\n"

    def fake_resolve(repository: str) -> str:
        """Return a stable synthetic revision."""

        return "a" * 40

    def fake_download(repository: str, revision: str, destination: Path) -> Path:
        """Create a root-level upstream skill document."""

        source_root = destination / "repository"
        source_root.mkdir(parents=True)
        (source_root / "SKILL.md").write_text(upstream_document)

        return source_root

    def fake_install(installed_skill: ExternalSkill, working_directory: Path, source_root: Path) -> None:
        """Create the installed skill in the staging directory."""

        installed = working_directory / ".staging/skills" / installed_skill.name
        installed.mkdir(parents=True)
        (installed / "SKILL.md").write_text(upstream_document)

    monkeypatch.setattr(github, "resolve_revision", fake_resolve)
    monkeypatch.setattr(github, "download_snapshot", fake_download)
    monkeypatch.setattr(installer, "install_skill", fake_install)


class SkillFrontMatterFactory(ModelFactory[SkillFrontMatter]):
    """Build valid canonical skill metadata."""

    __model__ = SkillFrontMatter

    name = "sample-skill"
    description = "Does a thing."
    disable_model_invocation = False


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
    category = None
    skill_name_override = None
    update_on_sync = True


class SkillsRegistryFactory(ModelFactory[SkillsRegistry]):
    """Build deterministic external-skill registries."""

    __model__ = SkillsRegistry

    version = 1

    @classmethod
    def skills(cls) -> list[ExternalSkill]:
        """Default to an empty external-skill registry."""

        return []


def materialize_skill(
    path: Path,
    front_matter: SkillFrontMatter,
    body: str = "Body text.",
) -> None:
    """Write one generated canonical skill document."""

    path.parent.mkdir(parents=True, exist_ok=True)
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


def materialize_registry(path: Path, registry: SkillsRegistry) -> None:
    """Write one external-skill registry into canonical sources."""

    path.write_text(registry.model_dump_json(), encoding="utf-8")


def materialize_tree(base: Path, files: dict[str, str]) -> None:
    """Write a relative text-file mapping under one directory."""

    for relative, content in files.items():
        target = base / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")


def materialize_every_source_kind(workspace: Workspace, explicit_invocation: bool = False) -> None:
    """Write one canonical source of every kind a provider tree mirrors."""

    materialize_rule(
        workspace.agents_dir / "rules/sample.md",
        RuleFrontMatterFactory.build(name="sample"),
    )

    hook = workspace.agents_dir / "hooks/setup.sh"
    hook.parent.mkdir(parents=True, exist_ok=True)
    hook.write_text("#!/usr/bin/env bash\necho ready\n", encoding="utf-8")

    materialize_skill(
        workspace.agents_dir / "skills/sample/SKILL.md",
        SkillFrontMatterFactory.build(name="sample", disable_model_invocation=explicit_invocation),
    )
