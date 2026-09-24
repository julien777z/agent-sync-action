from pathlib import Path

import pytest
from pydantic import ValidationError

from agent_sync.models.registry import ExternalSkill, SkillsRegistry


class TestExternalSkillModel:
    """Test that external-skill registry validation and defaults work."""

    def test_upstream_slug_defaults_to_local_name(self) -> None:
        """Test that an omitted upstream slug uses the local skill name."""

        skill = ExternalSkill(
            name="sample-skill",
            repo="example/sample-skill",
            update_on_sync=True,
        )

        assert skill.upstream_skill == "sample-skill"

    @pytest.mark.parametrize("name", ["Bad Name", "UPPER", "-leading", "sample\n"])
    def test_invalid_skill_names_fail(self, name: str) -> None:
        """Test that unsafe external skill names are rejected."""

        with pytest.raises(ValidationError):
            ExternalSkill(name=name, repo="example/sample", update_on_sync=True)

    @pytest.mark.parametrize("skill", ["Bad Name", "UPPER", "../escape"])
    def test_invalid_upstream_skill_names_fail(self, skill: str) -> None:
        """Test that unsafe upstream skill selectors are rejected."""

        with pytest.raises(ValidationError):
            ExternalSkill(
                name="sample",
                repo="example/sample",
                skill=skill,
                update_on_sync=True,
            )

    @pytest.mark.parametrize(
        ("category", "expected"),
        [(None, Path("sample")), ("review", Path("review/sample")), ("web/react", Path("web/react/sample"))],
    )
    def test_category_places_the_skill(self, category: str | None, expected: Path) -> None:
        """Test that the declared folder becomes the skill's path under the skills directory."""

        skill = ExternalSkill(name="sample", repo="example/sample", category=category, update_on_sync=True)

        assert skill.relative_path == expected

    @pytest.mark.parametrize(
        "category", ["", "Review", "../escape", "review/", "/review", "review//web", "a b"]
    )
    def test_invalid_categories_fail(self, category: str) -> None:
        """Test that unsafe or malformed grouping folders are rejected."""

        with pytest.raises(ValidationError):
            ExternalSkill(name="sample", repo="example/sample", category=category, update_on_sync=True)

    def test_old_folder_key_is_rejected(self) -> None:
        with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
            ExternalSkill.model_validate(
                {"name": "sample", "repo": "example/sample", "folder": "review", "update_on_sync": True}
            )

    def test_old_name_override_key_is_rejected(self) -> None:
        with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
            ExternalSkill.model_validate(
                {
                    "name": "sample",
                    "repo": "example/sample",
                    "name_override": "renamed",
                    "update_on_sync": True,
                }
            )

    @pytest.mark.parametrize("skill_name_override", ["Bad Name", "UPPER", "../escape"])
    def test_invalid_skill_name_overrides_fail(self, skill_name_override: str) -> None:
        with pytest.raises(ValidationError):
            ExternalSkill(
                name="sample",
                repo="example/sample",
                skill_name_override=skill_name_override,
                update_on_sync=True,
            )

    def test_update_on_sync_is_required(self) -> None:
        """Test that every registry entry chooses its update behavior explicitly."""

        with pytest.raises(ValidationError, match="update_on_sync"):
            ExternalSkill.model_validate({"name": "sample", "repo": "example/sample"})

    def test_duplicate_local_skill_names_fail(self) -> None:
        """Test that entries cannot silently overwrite one local skill directory."""

        with pytest.raises(ValidationError, match="names must be unique"):
            SkillsRegistry(
                skills=[
                    ExternalSkill(
                        name="sample",
                        repo="example/first",
                        update_on_sync=True,
                    ),
                    ExternalSkill(
                        name="sample",
                        repo="example/second",
                        update_on_sync=True,
                    ),
                ]
            )

    def test_override_name_sets_local_path_without_changing_upstream_selector(self) -> None:
        skill = ExternalSkill(
            name="no-ai-slop",
            repo="example/writing",
            skill_name_override="no-text-ai-slop",
            category="review",
            update_on_sync=True,
        )

        assert skill.upstream_skill == "no-ai-slop"
        assert skill.local_name == "no-text-ai-slop"
        assert skill.relative_path == Path("review/no-text-ai-slop")

    def test_duplicate_override_names_fail(self) -> None:
        with pytest.raises(ValidationError, match="names must be unique"):
            SkillsRegistry(
                skills=[
                    ExternalSkill(
                        name="original", repo="example/one", skill_name_override="shared", update_on_sync=True
                    ),
                    ExternalSkill(name="shared", repo="example/two", update_on_sync=True),
                ]
            )
