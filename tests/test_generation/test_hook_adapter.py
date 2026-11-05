import ast
import json
import os
import shutil
import signal
import subprocess
import time
from collections.abc import Callable
from pathlib import Path

import pytest

from agent_sync.generation.artifact import HOOK_ADAPTER_SOURCE
from agent_sync.models.output import Harness
from agent_sync.models.settings import Workspace
from agent_sync.reconciliation import mirror_harnesses
from tests.conftest import HookPayload
from tests.factories import HooksConfigFactory, materialize_hooks


def run_adapter(
    workspace: Workspace, harness: Harness, command: str, hook_input: bytes, cwd: Path
) -> subprocess.CompletedProcess[bytes]:
    """Run one harness's generated adapter with a hook command and stdin."""

    adapter = harness.root(workspace.root) / "hooks/agent_sync_adapter.py"

    return subprocess.run(
        ["python3", str(adapter), harness.value, command],
        input=hook_input,
        cwd=cwd,
        capture_output=True,
        timeout=20,
        check=False,
    )


def find_processes(marker: str) -> list[int]:
    """Return the IDs of running processes whose command line contains a marker."""

    processes: list[int] = []

    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue

        try:
            command_line = (entry / "cmdline").read_bytes()
        except OSError:
            continue

        if marker.encode() in command_line:
            processes.append(int(entry.name))

    return processes


def terminate_hook_command(shell_path: str, command: str, hook: Path, environment: dict[str, str]) -> int:
    """Start a hook command as a harness does, terminate its shell and count the processes left."""

    ready = Path(f"{hook}.ready")
    ready.unlink(missing_ok=True)

    process = subprocess.Popen(
        [shell_path, "-c", command], stdin=subprocess.DEVNULL, cwd=hook.parent, env=environment
    )

    deadline = time.monotonic() + 20

    while not ready.exists() and time.monotonic() < deadline:
        time.sleep(0.05)

    process.send_signal(signal.SIGTERM)
    process.wait(timeout=20)

    survivors = find_processes(str(hook))

    for survivor in survivors:
        os.kill(survivor, signal.SIGKILL)

    return len(survivors)


class TestHookAdapter:
    """Test that the generated hook adapter annotates input and hands control to the hook."""

    @pytest.mark.parametrize(
        ("payload_name", "harness", "edited_files"),
        [
            ("claude-edit", Harness.CLAUDE_CODE, ["sub/note.txt"]),
            ("claude-write", Harness.CLAUDE_CODE, ["sub/new.txt"]),
            ("claude-notebook-edit", Harness.CLAUDE_CODE, ["sub/book.ipynb"]),
            ("claude-session-start", Harness.CLAUDE_CODE, []),
            ("codex-apply-patch", Harness.CODEX, ["sub/added.txt", "sub/note.txt", "moved/new.txt"]),
            ("cursor-post-tool-use", Harness.CURSOR, ["sub/note.txt"]),
            ("cursor-after-file-edit", Harness.CURSOR, ["sub/note.txt"]),
        ],
        ids=[
            "claude-edit",
            "claude-write",
            "claude-notebook-edit",
            "claude-non-edit",
            "codex-apply-patch",
            "cursor-post-tool-use",
            "cursor-file-edit",
        ],
    )
    async def test_adds_shared_block_beside_original_input(
        self,
        hooked_workspace: Workspace,
        load_hook_payload: Callable[..., HookPayload],
        payload_name: str,
        harness: Harness,
        edited_files: list[str],
    ) -> None:
        """Test that each harness's input keeps every key and gains its project and edited files."""

        root = hooked_workspace.root.resolve()
        payload = load_hook_payload(name=payload_name, root=root)

        result = run_adapter(hooked_workspace, harness, "cat", json.dumps(payload).encode(), root / "sub")

        assert result.returncode == 0
        assert json.loads(result.stdout) == {
            **payload,
            "agent_sync": {
                "harness": harness.value,
                "project_dir": str(root),
                "edited_files": [str(root / path) for path in edited_files],
            },
        }

    @pytest.mark.parametrize(
        "hook_input",
        [
            b"",
            b"{invalid",
            b"[]",
            b"null",
            b'{"cwd": ".", "tool_input": "text"}',
            b'{"cwd": 3}',
        ],
        ids=["empty", "invalid", "array", "null", "string-tool-input", "numeric-cwd"],
    )
    async def test_unreadable_input_reaches_hook_unchanged(
        self, hooked_workspace: Workspace, hook_input: bytes
    ) -> None:
        """Test that input the adapter cannot annotate still runs the hook with the original bytes."""

        result = run_adapter(hooked_workspace, Harness.CODEX, "cat", hook_input, hooked_workspace.root)

        assert result.returncode == 0
        assert result.stdout == hook_input

    async def test_large_input_to_hook_ignoring_stdin(self, hooked_workspace: Workspace) -> None:
        """Test that input beyond a pipe buffer completes when the hook never reads it."""

        hook_input = json.dumps({"cwd": str(hooked_workspace.root), "prompt": "x" * 200_000}).encode()

        result = run_adapter(hooked_workspace, Harness.CLAUDE_CODE, "true", hook_input, hooked_workspace.root)

        assert result.returncode == 0

    async def test_hook_output_streams_with_its_exit_code(self, hooked_workspace: Workspace) -> None:
        """Test that hook output arrives while it runs and its exit status and stderr pass through."""

        adapter = Harness.CLAUDE_CODE.root(hooked_workspace.root) / "hooks/agent_sync_adapter.py"
        command = "printf 'first\\n'; printf 'warning\\n' >&2; sleep 1; exit 3"

        process = subprocess.Popen(
            ["python3", str(adapter), Harness.CLAUDE_CODE.value, command],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=hooked_workspace.root,
        )

        assert process.stdout is not None
        assert process.stderr is not None
        assert process.stdout.readline() == b"first\n"
        assert process.poll() is None
        assert process.wait(timeout=20) == 3
        assert process.stderr.read() == b"warning\n"

    @pytest.mark.parametrize("shell", ["dash", "bash"])
    async def test_termination_leaves_no_extra_process(
        self, hooked_workspace: Workspace, tmp_path: Path, shell: str
    ) -> None:
        """Test that terminating the registered command leaves only what the bare hook command leaves."""

        shell_path = shutil.which(shell)
        assert shell_path is not None

        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        (bin_dir / "sh").symlink_to(shell_path)

        hook = hooked_workspace.root / ".agents/hooks/session/start.py"
        config = HooksConfigFactory.build()
        canonical_command = f"python3 {hook}"
        config.hooks["SessionStart"][0].hooks[0].command = canonical_command
        materialize_hooks(hooked_workspace, config)
        hook.write_text("import time\nopen(__file__ + '.ready', 'w').close()\ntime.sleep(30)\n")

        mirror_harnesses(hooked_workspace, dry_run=False)

        settings = json.loads((hooked_workspace.root / ".claude/settings.json").read_text())
        registered_command = settings["hooks"]["SessionStart"][0]["hooks"][0]["command"]
        environment = {**os.environ, "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}"}

        bare_survivors = terminate_hook_command(shell_path, canonical_command, hook, environment)
        adapted_survivors = terminate_hook_command(shell_path, registered_command, hook, environment)

        assert adapted_survivors == bare_survivors
        assert shell != "bash" or adapted_survivors == 0

    async def test_adapter_syntax_supports_python_39(self) -> None:
        """Test that the packaged adapter parses with the oldest supported host Python grammar."""

        ast.parse(HOOK_ADAPTER_SOURCE.read_text(encoding="utf-8"), feature_version=(3, 9))
