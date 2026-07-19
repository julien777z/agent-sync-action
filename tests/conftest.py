from pathlib import Path

import pytest

from agent_sync.workspace import Workspace


@pytest.fixture
def workspace(tmp_path: Path) -> Workspace:
    """Create an isolated synthetic consumer workspace."""

    resolved = Workspace(root=tmp_path)
    resolved.agents_dir.mkdir()

    return resolved
