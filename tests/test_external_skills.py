import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from agent_sync.external_skills import (
    ExternalSkill,
    SkillsRegistry,
    load_registry,
    read_skill_path,
    snapshot_tree,
    trees_differ,
)
from agent_sync.utils import fs


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

    def test_missing_registry_returns_none(self, tmp_path: Path) -> None:
        """Test that an absent registry file yields None so the refresh is a no-op."""

        fs.set_root(tmp_path)

        assert load_registry(tmp_path / "skills.json") is None

    def test_valid_registry_parses(self, tmp_path: Path) -> None:
        """Test that a well-formed registry parses into typed entries."""

        fs.set_root(tmp_path)
        path = tmp_path / "skills.json"
        path.write_text(
            json.dumps(
                {
                    "version": 1,
                    "skills": [{"name": "security-audit", "repo": "cloudflare/security-audit-skill"}],
                }
            ),
            encoding="utf-8",
        )

        registry = load_registry(path)

        assert isinstance(registry, SkillsRegistry)
        assert registry.skills[0].repo == "cloudflare/security-audit-skill"

    def test_invalid_registry_raises(self, tmp_path: Path) -> None:
        """Test that a registry with an unknown field raises a clear error instead of silently passing."""

        fs.set_root(tmp_path)
        path = tmp_path / "skills.json"
        path.write_text(json.dumps({"version": 1, "skills": [{"name": "x"}]}), encoding="utf-8")

        with pytest.raises(ValueError):
            load_registry(path)


class TestReadSkillPath:
    """Test resolving the upstream skillPath from a temp install's skills-lock.json."""

    def test_returns_sole_entry_regardless_of_key(self, tmp_path: Path) -> None:
        """Test that the single lock entry's skillPath is returned even when its key differs from the local name."""

        fs.set_root(tmp_path)
        (tmp_path / "skills-lock.json").write_text(
            json.dumps({"skills": {"upstream-slug": {"skillPath": "skills/x/SKILL.md"}}}),
            encoding="utf-8",
        )

        assert read_skill_path(tmp_path) == "skills/x/SKILL.md"

    def test_root_level_skill_path_reported(self, tmp_path: Path) -> None:
        """Test that a repo-root skillPath (no slash) is reported so asset supplementation can trigger."""

        fs.set_root(tmp_path)
        (tmp_path / "skills-lock.json").write_text(
            json.dumps({"skills": {"security-audit": {"skillPath": "SKILL.md"}}}),
            encoding="utf-8",
        )

        assert read_skill_path(tmp_path) == "SKILL.md"


class TestTreeComparison:
    """Test the directory snapshot/compare helpers used to detect skill changes."""

    def test_identical_trees_do_not_differ(self, tmp_path: Path) -> None:
        """Test that two directories with the same files and content compare equal."""

        source = tmp_path / "a"
        dest = tmp_path / "b"
        for base in (source, dest):
            (base / "references").mkdir(parents=True)
            (base / "SKILL.md").write_text("same\n", encoding="utf-8")
            (base / "references" / "details.md").write_text("detail\n", encoding="utf-8")

        assert not trees_differ(source, dest)

    def test_changed_content_differs(self, tmp_path: Path) -> None:
        """Test that differing file content is detected as a change."""

        source = tmp_path / "a"
        dest = tmp_path / "b"
        source.mkdir()
        dest.mkdir()
        (source / "SKILL.md").write_text("new\n", encoding="utf-8")
        (dest / "SKILL.md").write_text("old\n", encoding="utf-8")

        assert trees_differ(source, dest)

    def test_missing_dest_is_a_change(self, tmp_path: Path) -> None:
        """Test that a not-yet-vendored skill (no destination) counts as a change."""

        source = tmp_path / "a"
        source.mkdir()
        (source / "SKILL.md").write_text("content\n", encoding="utf-8")

        assert snapshot_tree(tmp_path / "missing") == {}
        assert trees_differ(source, tmp_path / "missing")
