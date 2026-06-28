import json
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

from agent_sync.models.registry import SkillsRegistry
from agent_sync.utils import fs


@pytest.fixture
def patch_sync_dirs(tmp_path: Path) -> Iterator[Path]:
    """Point the sync at a temporary repository root and restore the default afterward."""

    fs.set_root(tmp_path)

    yield tmp_path

    fs.set_root(Path.cwd())


@pytest.fixture
def skill_file_factory(patch_sync_dirs: Path) -> Callable[..., Path]:
    """Create a .agents/skills/<slug>/SKILL.md under the configured root and return its path."""

    def _build(slug: str, body: str = "Body text.") -> Path:
        skill_dir = patch_sync_dirs / ".agents" / "skills" / slug
        skill_dir.mkdir(parents=True)
        source = skill_dir / "SKILL.md"
        source.write_text(
            f"---\nname: {slug}\ndescription: Does a thing.\n---\n\n# {slug}\n\n{body}\n",
            encoding="utf-8",
        )

        return source

    return _build


@pytest.fixture
def registry_file_factory(patch_sync_dirs: Path) -> Callable[[SkillsRegistry], Path]:
    """Write a skills.json registry from a SkillsRegistry model and return its path."""

    def _build(registry: SkillsRegistry) -> Path:
        path = patch_sync_dirs / "skills.json"
        path.write_text(registry.model_dump_json(), encoding="utf-8")

        return path

    return _build


@pytest.fixture
def skills_lock_factory(patch_sync_dirs: Path) -> Callable[..., Path]:
    """Write a skills-lock.json with a single skill entry and return the lock file's directory."""

    def _build(skill_path: str, key: str = "skill") -> Path:
        (patch_sync_dirs / "skills-lock.json").write_text(
            json.dumps({"skills": {key: {"skillPath": skill_path}}}),
            encoding="utf-8",
        )

        return patch_sync_dirs

    return _build


@pytest.fixture
def skill_tree_factory() -> Callable[[Path, dict[str, str]], Path]:
    """Materialize a directory tree of relative-path -> text-content files and return its base."""

    def _build(base: Path, files: dict[str, str]) -> Path:
        for relative, content in files.items():
            target = base / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")

        return base

    return _build
