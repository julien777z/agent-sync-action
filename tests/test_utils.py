from collections.abc import Callable
from pathlib import Path

from agent_sync.utils import trees_differ


def test_tree_comparison_detects_changes(
    tmp_path: Path,
    skill_tree_factory: Callable[[Path, dict[str, str]], Path],
) -> None:
    """Test that file content changes alter a directory snapshot."""

    source = skill_tree_factory(tmp_path / "source", {"SKILL.md": "new\n"})
    destination = skill_tree_factory(tmp_path / "destination", {"SKILL.md": "old\n"})

    assert trees_differ(source, destination)
