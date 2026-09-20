from pathlib import Path

import pytest

from agent_sync.errors import AgentSyncError
from agent_sync.skills import discover_skill_directories, locate_skill_by_name


class TestSkillTree:
    """Test that walking the canonical skill tree is safe and tolerant where it should be."""

    def test_locating_a_skill_ignores_a_folder_holding_none(self, tmp_path: Path) -> None:
        """Test that an unrelated empty folder does not stop a skill from being found."""

        skills_dir = tmp_path / "skills"
        (skills_dir / "review" / "wanted").mkdir(parents=True)
        (skills_dir / "review" / "wanted" / "SKILL.md").write_text("---\nname: wanted\n---\n")
        (skills_dir / "notes").mkdir()

        assert locate_skill_by_name(skills_dir, "wanted") == skills_dir / "review" / "wanted"
        assert locate_skill_by_name(skills_dir, "absent") is None

    def test_discovery_rejects_a_folder_holding_no_skill(self, tmp_path: Path) -> None:
        """Test that mirroring still refuses a grouping folder that resolves to nothing."""

        skills_dir = tmp_path / "skills"
        (skills_dir / "notes").mkdir(parents=True)

        with pytest.raises(AgentSyncError, match="Missing SKILL.md"):
            discover_skill_directories(skills_dir)

    def test_a_linked_folder_never_recurses(self, tmp_path: Path) -> None:
        """Test that a cycle through a linked folder is refused instead of exhausting the stack."""

        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        (skills_dir / "loop").symlink_to(skills_dir, target_is_directory=True)

        with pytest.raises(AgentSyncError, match="Missing SKILL.md"):
            discover_skill_directories(skills_dir)

        assert locate_skill_by_name(skills_dir, "anything") is None
