import subprocess
from pathlib import Path

import pytest
from pydantic import BaseModel, ConfigDict

from agent_sync.models.settings import Workspace
from agent_sync.workspace import agents_dir


def create_workspace(root: Path, output_dirname: str = "") -> Workspace:
    """Create one synthetic consumer workspace with its canonical source directory."""

    resolved = Workspace(root=root, output_dirname=output_dirname)
    agents_dir(resolved).mkdir()

    return resolved


@pytest.fixture
def workspace(tmp_path: Path) -> Workspace:
    """Create an isolated synthetic consumer workspace."""

    return create_workspace(tmp_path)


@pytest.fixture
def relocated_workspace(tmp_path: Path) -> Workspace:
    """Create a workspace whose generated provider trees live under a nested directory."""

    return create_workspace(tmp_path, ".agents/.auto_generated")


class GitHubUpstream(BaseModel):
    """A local repository served in place of one GitHub repository, pinned at one commit."""

    model_config = ConfigDict(frozen=True)

    repository: str
    revision: str


@pytest.fixture
def github_upstream(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> GitHubUpstream:
    """Serve a committed local repository wherever git is asked for its GitHub URL."""

    served_root = tmp_path / "served"
    upstream = served_root / "example" / "skills.git"
    upstream.mkdir(parents=True)
    (upstream / "SKILL.md").write_text("---\nname: example\n---\n")
    (upstream / "LICENSE").write_text("Example license\n")

    for command in (
        ["git", "init", "--quiet"],
        ["git", "add", "."],
        [
            "git",
            "-c",
            "user.name=Upstream",
            "-c",
            "user.email=upstream@example.invalid",
            "commit",
            "--quiet",
            "-m",
            "init",
        ],
    ):
        subprocess.run(command, cwd=upstream, check=True)

    revision = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=upstream, check=True, capture_output=True, text=True
    ).stdout.strip()

    monkeypatch.setenv("GIT_CONFIG_COUNT", "2")
    monkeypatch.setenv("GIT_CONFIG_KEY_0", f"url.{served_root.as_uri()}/.insteadOf")
    monkeypatch.setenv("GIT_CONFIG_VALUE_0", "https://github.com/")
    monkeypatch.setenv("GIT_CONFIG_KEY_1", "protocol.file.allow")
    monkeypatch.setenv("GIT_CONFIG_VALUE_1", "always")

    return GitHubUpstream(repository="example/skills", revision=revision)
