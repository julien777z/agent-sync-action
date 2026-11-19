import importlib.util
import os
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Final

import pytest
from pydantic import BaseModel, ConfigDict

from agent_sync.models.settings import Workspace
from agent_sync.workspace import agents_dir

UPSTREAM_COMMIT: Final[list[str]] = [
    "git",
    "-c",
    "user.name=Upstream",
    "-c",
    "user.email=upstream@example.invalid",
    "commit",
]
RACER_COMMIT: Final[list[str]] = [
    "git",
    "-c",
    "user.name=Racer",
    "-c",
    "user.email=racer@example.invalid",
    "commit",
]

RACING_HOOK: Final[str] = """#!{interpreter}
import subprocess
from pathlib import Path

races = Path({races!r})
racer = Path({racer!r})
remaining = int(races.read_text())

if remaining:
    races.write_text(str(remaining - 1))
    prepared = subprocess.run(
        ["git", "rev-list", "--count", "origin/main..HEAD"], cwd=racer, check=True, capture_output=True, text=True
    ).stdout.strip()

    if prepared == "0":
        (racer / "competing.txt").write_text(str(remaining))
        subprocess.run(["git", "add", "competing.txt"], cwd=racer, check=True)
        subprocess.run([*{racer_commit!r}, "--quiet", "-m", "compete"], cwd=racer, check=True)

    subprocess.run(["git", "push", "--quiet", "origin", "HEAD:main"], cwd=racer, check=True)
"""


def stage_output_directory(action_path: Path, agents_dir: str, output_dir: str) -> None:
    """Stage everything under the generated output directory."""

    subprocess.run(["git", "add", "--all", output_dir], check=True)


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


@pytest.fixture
def served_github(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Serve local repositories wherever git is asked for a GitHub URL, with or without credentials."""

    served_root = tmp_path / "served"
    served_root.mkdir()
    served_url = f"url.{served_root.as_uri()}/.insteadOf"

    monkeypatch.setenv("GIT_CONFIG_COUNT", "3")
    monkeypatch.setenv("GIT_CONFIG_KEY_0", served_url)
    monkeypatch.setenv("GIT_CONFIG_VALUE_0", "https://github.com/")
    monkeypatch.setenv("GIT_CONFIG_KEY_1", served_url)
    monkeypatch.setenv("GIT_CONFIG_VALUE_1", f"https://x-access-token:{os.environ['GH_TOKEN']}@github.com/")
    monkeypatch.setenv("GIT_CONFIG_KEY_2", "protocol.file.allow")
    monkeypatch.setenv("GIT_CONFIG_VALUE_2", "always")

    return served_root


class GitHubUpstream(BaseModel):
    """A local repository served in place of one GitHub repository, pinned at one commit."""

    model_config = ConfigDict(frozen=True)

    repository: str
    revision: str


@pytest.fixture
def github_upstream(served_github: Path) -> GitHubUpstream:
    """Serve a committed local repository in place of one GitHub repository."""

    upstream = served_github / "example" / "skills.git"
    upstream.mkdir(parents=True)
    (upstream / "SKILL.md").write_text("---\nname: example\n---\n")
    (upstream / "LICENSE").write_text("Example license\n")

    for command in (
        ["git", "init", "--quiet"],
        ["git", "add", "."],
        [*UPSTREAM_COMMIT, "--quiet", "-m", "init"],
    ):
        subprocess.run(command, cwd=upstream, check=True)

    revision = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=upstream, check=True, capture_output=True, text=True
    ).stdout.strip()

    return GitHubUpstream(repository="example/skills", revision=revision)


class RacingSyncCheckout(BaseModel):
    """A checkout whose remote gains competing commits just before each of its next pushes."""

    model_config = ConfigDict(frozen=True)

    checkout: Path
    remote: Path
    racer: Path
    races: Path

    def prepare_race_commit(self, relative_path: str, content: str, message: str) -> None:
        """Commit one file in the racing clone, for the next race to push in place of its own commit."""

        (self.racer / relative_path).parent.mkdir(parents=True, exist_ok=True)
        (self.racer / relative_path).write_text(content)

        subprocess.run(["git", "add", relative_path], cwd=self.racer, check=True)
        subprocess.run([*RACER_COMMIT, "--quiet", "-m", message], cwd=self.racer, check=True)


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
def racing_sync_checkout(
    tmp_path: Path, served_github: Path, persist_script: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> RacingSyncCheckout:
    """Enter a synced checkout, with mirrored output to persist, whose GitHub remote another clone pushes to."""

    remote = served_github / f"{os.environ['GITHUB_REPOSITORY']}.git"
    remote.mkdir(parents=True)
    subprocess.run(["git", "init", "--quiet", "--bare", "--initial-branch=main"], cwd=remote, check=True)

    checkout = tmp_path / "checkout"
    racer = tmp_path / "racer"

    subprocess.run(["git", "clone", "--quiet", str(remote), str(checkout)], check=True)

    (checkout / "README.md").write_text("Example\n")
    subprocess.run(["git", "add", "README.md"], cwd=checkout, check=True)
    subprocess.run([*UPSTREAM_COMMIT, "--quiet", "-m", "initial"], cwd=checkout, check=True)
    subprocess.run(["git", "push", "--quiet", "origin", "HEAD:main"], cwd=checkout, check=True)

    subprocess.run(["git", "clone", "--quiet", str(remote), str(racer)], check=True)

    races = tmp_path / "races"
    races.write_text("0")

    hook = checkout / ".git" / "hooks" / "pre-push"
    hook.write_text(
        RACING_HOOK.format(
            interpreter=sys.executable, races=str(races), racer=str(racer), racer_commit=RACER_COMMIT
        )
    )
    hook.chmod(0o755)

    output = checkout / "generated"
    output.mkdir()
    (output / "mirror.md").write_text((checkout / "README.md").read_text())

    monkeypatch.chdir(checkout)
    monkeypatch.setattr(persist_script, "stage_generated_paths", stage_output_directory)

    return RacingSyncCheckout(checkout=checkout, remote=remote, racer=racer, races=races)
