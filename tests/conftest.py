import importlib.util
import subprocess
import sys
from pathlib import Path
from types import ModuleType

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
    """Create a workspace whose generated harness trees live under a nested directory."""

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


class RacingSyncCheckout(BaseModel):
    """A checkout whose remote gains a competing commit just before each of its next pushes."""

    model_config = ConfigDict(frozen=True)

    checkout: Path
    remote: Path
    races: Path


RACING_HOOK = """#!{interpreter}
import subprocess
from pathlib import Path

races = Path({races!r})
remaining = int(races.read_text())

if remaining:
    races.write_text(str(remaining - 1))
    racer = Path({racer!r})
    (racer / "competing.txt").write_text(str(remaining))
    subprocess.run(["git", "add", "competing.txt"], cwd=racer, check=True)
    subprocess.run(
        ["git", "-c", "user.name=Racer", "-c", "user.email=racer@example.invalid", "commit", "--quiet", "-m", "compete"],
        cwd=racer,
        check=True,
    )
    subprocess.run(["git", "push", "--quiet", "origin", "HEAD:main"], cwd=racer, check=True)
"""


@pytest.fixture
def persist_script() -> ModuleType:
    """Load the checked-in persistence script as a module."""

    script = Path(".github/scripts/persist_changes.py").resolve()
    spec = importlib.util.spec_from_file_location("persist_changes", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    return module


@pytest.fixture
def racing_sync_checkout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> RacingSyncCheckout:
    """Create a synced checkout whose GitHub remote is a local bare repository another clone pushes to."""

    served_root = tmp_path / "served"
    remote = served_root / "example" / "sync.git"
    remote.mkdir(parents=True)
    subprocess.run(["git", "init", "--quiet", "--bare", "--initial-branch=main"], cwd=remote, check=True)

    checkout = tmp_path / "checkout"
    racer = tmp_path / "racer"
    commit = ["git", "-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "--quiet"]

    subprocess.run(["git", "clone", "--quiet", str(remote), str(checkout)], check=True)
    (checkout / "README.md").write_text("Example\n")
    subprocess.run(["git", "add", "README.md"], cwd=checkout, check=True)
    subprocess.run([*commit, "-m", "initial"], cwd=checkout, check=True)
    subprocess.run(["git", "push", "--quiet", "origin", "HEAD:main"], cwd=checkout, check=True)

    subprocess.run(["git", "clone", "--quiet", str(remote), str(racer)], check=True)

    races = tmp_path / "races"
    races.write_text("0")
    hook = checkout / ".git" / "hooks" / "pre-push"
    hook.write_text(RACING_HOOK.format(interpreter=sys.executable, races=str(races), racer=str(racer)))
    hook.chmod(0o755)

    monkeypatch.setenv("GITHUB_REPOSITORY", "example/sync")
    monkeypatch.setenv("GH_TOKEN", "test-token")
    monkeypatch.setenv("GIT_CONFIG_COUNT", "2")
    monkeypatch.setenv("GIT_CONFIG_KEY_0", f"url.{served_root.as_uri()}/.insteadOf")
    monkeypatch.setenv("GIT_CONFIG_VALUE_0", "https://x-access-token:test-token@github.com/")
    monkeypatch.setenv("GIT_CONFIG_KEY_1", "protocol.file.allow")
    monkeypatch.setenv("GIT_CONFIG_VALUE_1", "always")

    return RacingSyncCheckout(checkout=checkout, remote=remote, races=races)
