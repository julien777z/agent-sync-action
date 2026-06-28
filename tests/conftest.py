from collections.abc import Iterator
from pathlib import Path

import pytest

from utils import fs


@pytest.fixture
def patch_sync_dirs(tmp_path: Path) -> Iterator[Path]:
    """Point the sync at a temporary repository root and restore the default afterward."""

    fs.set_root(tmp_path)

    yield tmp_path

    fs.set_root(Path.cwd())
