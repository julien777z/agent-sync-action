from pathlib import Path

import pytest

from agent_sync.workspace import Workspace


def create_workspace(root: Path, output_dirname: str = "") -> Workspace:
    """Create one synthetic consumer workspace with its canonical source directory."""

    resolved = Workspace(root=root, output_dirname=output_dirname)
    resolved.agents_dir.mkdir()

    return resolved


@pytest.fixture
def workspace(tmp_path: Path) -> Workspace:
    """Create an isolated synthetic consumer workspace."""

    return create_workspace(tmp_path)


@pytest.fixture
def relocated_workspace(tmp_path: Path) -> Workspace:
    """Create a workspace whose generated provider trees live under a nested directory."""

    return create_workspace(tmp_path, ".agents/.auto_generated")
