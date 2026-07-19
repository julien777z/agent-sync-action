from pathlib import Path

from agent_sync.utils import trees_differ
from tests.factories import materialize_tree


class TestTreesDiffer:
    """Test that directory tree comparisons work."""

    def test_detects_changes(
        self,
        tmp_path: Path,
    ) -> None:
        """Test that file content changes alter a directory snapshot."""

        source = tmp_path / "source"
        destination = tmp_path / "destination"
        materialize_tree(source, {"SKILL.md": "new\n"})
        materialize_tree(destination, {"SKILL.md": "old\n"})

        assert trees_differ(source, destination)
