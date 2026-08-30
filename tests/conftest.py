from collections.abc import Callable
from pathlib import Path

import pytest

from agent_sync.workspace import Workspace


@pytest.fixture
def create_workspace(tmp_path: Path) -> Callable[..., Workspace]:
    """Build a workspace whose canonical directory carries the given name."""

    def _create(agents_dirname: str = ".agents") -> Workspace:
        """Create one isolated synthetic consumer workspace."""

        resolved = Workspace(root=tmp_path, agents_dirname=agents_dirname)
        resolved.agents_dir.mkdir()

        return resolved

    return _create


@pytest.fixture
def workspace(create_workspace: Callable[..., Workspace]) -> Workspace:
    """Create an isolated synthetic consumer workspace."""

    return create_workspace()
