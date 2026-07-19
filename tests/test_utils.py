from collections.abc import Callable
from pathlib import Path

from agent_sync.utils import trees_differ


class TestTreesDiffer:
    """Test that directory tree comparisons work."""

    def test_detects_changes(
        self,
        tmp_path: Path,
        skill_tree_factory: Callable[[Path, dict[str, str]], Path],
    ) -> None:
        """Test that file content changes alter a directory snapshot."""

        source = skill_tree_factory(tmp_path / "source", {"SKILL.md": "new\n"})
        destination = skill_tree_factory(tmp_path / "destination", {"SKILL.md": "old\n"})

        assert trees_differ(source, destination)
