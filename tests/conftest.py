import json
from collections.abc import Callable
from pathlib import Path
from typing import Protocol

import pytest

from agent_sync.models.registry import SkillsRegistry
from agent_sync.workspace import Workspace


class SkillFileFactory(Protocol):
    """Describe a builder for canonical skill documents."""

    def __call__(self, slug: str, body: str = "Body text.") -> Path:
        """Build one canonical skill document."""

        ...


class RuleFileFactory(Protocol):
    """Describe a builder for canonical rule documents."""

    def __call__(
        self,
        slug: str,
        body: str = "# Rule\n\nAlways be ruling.",
        front_matter: str | None = "name: removed\ndescription: A rule.",
    ) -> Path:
        """Build one canonical rule document."""

        ...


class SkillsLockFactory(Protocol):
    """Describe a builder for one installer lock file."""

    def __call__(self, skill_path: str, key: str = "skill") -> Path:
        """Build one installer lock file."""

        ...


@pytest.fixture
def workspace(tmp_path: Path) -> Workspace:
    """Create an isolated synthetic consumer workspace."""

    resolved = Workspace(root=tmp_path)
    resolved.agents_dir.mkdir()

    return resolved


@pytest.fixture
def skill_file_factory(workspace: Workspace) -> SkillFileFactory:
    """Create canonical skill documents in the synthetic workspace."""

    def _build(slug: str, body: str = "Body text.") -> Path:
        """Build one skill document."""

        skill_dir = workspace.agents_dir / "skills" / slug
        skill_dir.mkdir(parents=True)
        source = skill_dir / "SKILL.md"
        source.write_text(
            f"---\nname: {slug}\ndescription: Does a thing.\n---\n\n# {slug}\n\n{body}\n",
            encoding="utf-8",
        )

        return source

    return _build


@pytest.fixture
def rule_file_factory(workspace: Workspace) -> RuleFileFactory:
    """Create canonical rule documents in the synthetic workspace."""

    def _build(
        slug: str,
        body: str = "# Rule\n\nAlways be ruling.",
        front_matter: str | None = "name: removed\ndescription: A rule.",
    ) -> Path:
        """Build one rule document."""

        rules_dir = workspace.agents_dir / "rules"
        rules_dir.mkdir(parents=True, exist_ok=True)
        source = rules_dir / f"{slug}.md"
        header = f"---\n{front_matter}\n---\n\n" if front_matter else ""
        source.write_text(f"{header}{body}\n", encoding="utf-8")

        return source

    return _build


@pytest.fixture
def registry_file_factory(workspace: Workspace) -> Callable[[SkillsRegistry], Path]:
    """Write a typed external-skill registry into canonical sources."""

    def _build(registry: SkillsRegistry) -> Path:
        """Build one external-skill registry."""

        path = workspace.agents_dir / "skills.json"
        path.write_text(registry.model_dump_json(), encoding="utf-8")

        return path

    return _build


@pytest.fixture
def skills_lock_factory(tmp_path: Path) -> SkillsLockFactory:
    """Write one installer lock entry into a temporary working directory."""

    def _build(skill_path: str, key: str = "skill") -> Path:
        """Build one installer lock file."""

        (tmp_path / "skills-lock.json").write_text(
            json.dumps({"skills": {key: {"skillPath": skill_path}}}),
            encoding="utf-8",
        )

        return tmp_path

    return _build


@pytest.fixture
def skill_tree_factory() -> Callable[[Path, dict[str, str]], Path]:
    """Create a comparable skill directory tree."""

    def _build(base: Path, files: dict[str, str]) -> Path:
        """Build one skill directory tree."""

        for relative, content in files.items():
            target = base / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")

        return base

    return _build
