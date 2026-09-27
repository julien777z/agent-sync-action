from pathlib import Path
from typing import Literal

import pytest

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

    @pytest.mark.parametrize(
        "extra_kind",
        ["dangling-link", "directory-link", "empty-directory"],
        ids=["dangling-link", "directory-link", "empty-directory"],
    )
    def test_detects_extra_entry(
        self,
        tmp_path: Path,
        extra_kind: Literal["dangling-link", "directory-link", "empty-directory"],
    ) -> None:
        """Test that links and empty directories count as tree differences."""

        source = tmp_path / "source"
        destination = tmp_path / "destination"
        materialize_tree(source, {"guide.md": "same"})
        materialize_tree(destination, {"guide.md": "same"})
        extra = destination / "extra"
        if extra_kind == "empty-directory":
            extra.mkdir()
        elif extra_kind == "directory-link":
            target = tmp_path / "target"
            target.mkdir()
            extra.symlink_to(target, target_is_directory=True)
        else:
            extra.symlink_to("missing")

        assert trees_differ(source, destination)
