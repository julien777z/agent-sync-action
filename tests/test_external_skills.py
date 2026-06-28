import json
from collections.abc import Callable
from pathlib import Path

import pytest
from pydantic import ValidationError

from agent_sync.external_skills import (
    load_registry,
    read_skill_path,
    snapshot_tree,
    trees_differ,
)
from agent_sync.models.registry import ExternalSkill, SkillsRegistry


class TestExternalSkillModel:
    """Test the external-skill registry model contract."""

    def test_upstream_skill_defaults_to_name(self) -> None:
        """Test that upstream_skill falls back to the local name when skill is omitted."""

        skill = ExternalSkill(name="security-audit", repo="cloudflare/security-audit-skill")

        assert skill.upstream_skill == "security-audit"

    def test_explicit_skill_overrides_name(self) -> None:
        """Test that an explicit skill slug is used as the upstream identifier."""

        skill = ExternalSkill(name="local-name", repo="owner/repo", skill="upstream-name")

        assert skill.upstream_skill == "upstream-name"

    @pytest.mark.parametrize("bad_name", ["Bad Name", "UPPER", "has space", "-leading"], ids=lambda n: n)
    def test_invalid_name_rejected(self, bad_name: str) -> None:
        """Test that names which are not safe slugs are rejected."""

        with pytest.raises(ValidationError):
            ExternalSkill(name=bad_name, repo="owner/repo")

    def test_unknown_field_rejected(self) -> None:
        """Test that an unexpected field on a registry entry is rejected."""

        with pytest.raises(ValidationError):
            ExternalSkill.model_validate({"name": "x", "repo": "o/r", "unexpected": True})


class TestLoadRegistry:
    """Test loading and validating the external-skill registry file."""

    def test_missing_registry_returns_none(self, patch_sync_dirs: Path) -> None:
        """Test that an absent registry file yields None so the refresh is a no-op."""

        assert load_registry(patch_sync_dirs / "skills.json") is None

    def test_valid_registry_parses(self, registry_file_factory: Callable[[SkillsRegistry], Path]) -> None:
        """Test that a well-formed registry parses into typed entries."""

        registry = SkillsRegistry(
            skills=[ExternalSkill(name="security-audit", repo="cloudflare/security-audit-skill")]
        )
        path = registry_file_factory(registry)

        loaded = load_registry(path)

        assert isinstance(loaded, SkillsRegistry)
        assert loaded.skills[0].repo == "cloudflare/security-audit-skill"

    def test_invalid_registry_raises(self, patch_sync_dirs: Path) -> None:
        """Test that a registry with a malformed entry raises a clear error instead of silently passing."""

        path = patch_sync_dirs / "skills.json"
        path.write_text(json.dumps({"version": 1, "skills": [{"name": "x"}]}), encoding="utf-8")

        with pytest.raises(ValueError):
            load_registry(path)


class TestReadSkillPath:
    """Test resolving the upstream skillPath from a temp install's skills-lock.json."""

    def test_returns_sole_entry_regardless_of_key(self, skills_lock_factory: Callable[..., Path]) -> None:
        """Test that the single lock entry's skillPath is returned even when its key differs from the local name."""

        lock_dir = skills_lock_factory("skills/x/SKILL.md", key="upstream-slug")

        assert read_skill_path(lock_dir) == "skills/x/SKILL.md"

    def test_root_level_skill_path_reported(self, skills_lock_factory: Callable[..., Path]) -> None:
        """Test that a repo-root skillPath (no slash) is reported so asset supplementation can trigger."""

        lock_dir = skills_lock_factory("SKILL.md", key="security-audit")

        assert read_skill_path(lock_dir) == "SKILL.md"


class TestTreeComparison:
    """Test the directory snapshot/compare helpers used to detect skill changes."""

    def test_identical_trees_do_not_differ(
        self, tmp_path: Path, skill_tree_factory: Callable[[Path, dict[str, str]], Path]
    ) -> None:
        """Test that two directories with the same files and content compare equal."""

        files = {"SKILL.md": "same\n", "references/details.md": "detail\n"}
        source = skill_tree_factory(tmp_path / "a", files)
        dest = skill_tree_factory(tmp_path / "b", files)

        assert not trees_differ(source, dest)

    def test_changed_content_differs(
        self, tmp_path: Path, skill_tree_factory: Callable[[Path, dict[str, str]], Path]
    ) -> None:
        """Test that differing file content is detected as a change."""

        source = skill_tree_factory(tmp_path / "a", {"SKILL.md": "new\n"})
        dest = skill_tree_factory(tmp_path / "b", {"SKILL.md": "old\n"})

        assert trees_differ(source, dest)

    def test_missing_dest_is_a_change(
        self, tmp_path: Path, skill_tree_factory: Callable[[Path, dict[str, str]], Path]
    ) -> None:
        """Test that a not-yet-vendored skill (no destination) counts as a change."""

        source = skill_tree_factory(tmp_path / "a", {"SKILL.md": "content\n"})

        assert snapshot_tree(tmp_path / "missing") == {}
        assert trees_differ(source, tmp_path / "missing")
