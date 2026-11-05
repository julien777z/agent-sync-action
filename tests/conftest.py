import json
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Final

import pytest
from pydantic import BaseModel, ConfigDict, JsonValue

from agent_sync.models.settings import Workspace
from agent_sync.reconciliation import mirror_harnesses
from agent_sync.workspace import agents_dir
from tests.factories import HooksConfigFactory, materialize_hooks

HOOK_PAYLOADS_PATH: Final[Path] = Path(__file__).parent / "test_generation/hook_payloads.json"

type HookPayload = dict[str, JsonValue]


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
def hooked_workspace(workspace: Workspace) -> Workspace:
    """Create a Git workspace whose registered hooks are mirrored to every harness."""

    subprocess.run(["git", "init", "--quiet", str(workspace.root)], check=True)
    (workspace.root / "sub").mkdir()
    materialize_hooks(workspace, HooksConfigFactory.build())

    mirror_harnesses(workspace, dry_run=False)

    return workspace


@pytest.fixture
def load_hook_payload() -> Callable[..., HookPayload]:
    """Load a recorded harness hook input with its paths placed under a workspace root."""

    def _build(*, name: str, root: Path) -> HookPayload:
        payloads: dict[str, HookPayload] = json.loads(
            HOOK_PAYLOADS_PATH.read_text().replace("<root>", str(root))
        )

        return payloads[name]

    return _build


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
