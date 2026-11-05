from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import tempfile
from typing import Final, TypedDict, cast

EDITED_FILE_HEADERS: Final[tuple[str, ...]] = ("*** Add File: ", "*** Update File: ")
MOVED_FILE_HEADER: Final[str] = "*** Move to: "
EDIT_TOOL_NAMES: Final[frozenset[str]] = frozenset({"Edit", "Write", "MultiEdit", "NotebookEdit"})


class AgentSyncBlock(TypedDict):
    """Describe the harness-neutral facts added to every hook input."""

    harness: str
    project_dir: str
    edited_files: list[str]


def read_project_dir(cwd: str) -> str:
    """Return the project directory containing a working directory."""

    result = subprocess.run(
        ["git", "-C", cwd, "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        return os.path.abspath(cwd)

    return result.stdout.strip()


def read_patch_paths(patch: str) -> list[str]:
    """Return the files an apply_patch body leaves edited."""

    paths: list[str] = []

    for line in patch.splitlines():
        if line.startswith(MOVED_FILE_HEADER) and paths:
            paths[-1] = line.removeprefix(MOVED_FILE_HEADER).strip()
        elif line.startswith(EDITED_FILE_HEADERS):
            paths.append(line.partition(": ")[2].strip())

    return paths


def read_edited_files(payload: dict[str, object], cwd: str) -> list[str]:
    """Return the files a tool call edited."""

    tool_input = payload.get("tool_input", {})

    if not isinstance(tool_input, dict):
        raise ValueError("tool_input must be an object")

    fields = cast("dict[str, object]", tool_input)
    tool_name = payload.get("tool_name")
    patch = fields.get("command")
    candidates = [payload.get("file_path")]

    if tool_name in EDIT_TOOL_NAMES:
        candidates.extend([fields.get("file_path"), fields.get("notebook_path")])

    if tool_name == "apply_patch" and isinstance(patch, str):
        candidates.extend(read_patch_paths(patch))

    paths = [
        os.path.normpath(os.path.join(cwd, path)) for path in candidates if isinstance(path, str) and path
    ]

    return list(dict.fromkeys(paths))


def annotate_hook_input(raw_input: bytes, harness: str) -> bytes:
    """Return the hook input with the agent_sync block added."""

    payload: object = json.loads(raw_input)

    if not isinstance(payload, dict):
        raise ValueError("hook input must be an object")

    fields = cast("dict[str, object]", payload)
    cwd = fields.get("cwd", os.getcwd())

    if not isinstance(cwd, str):
        raise ValueError("cwd must be a string")

    block = AgentSyncBlock(
        harness=harness,
        project_dir=read_project_dir(cwd),
        edited_files=read_edited_files(fields, cwd),
    )

    return json.dumps({**fields, "agent_sync": block}).encode()


def run_hook(harness: str, command: str) -> None:
    """Replace this process with the hook command."""

    raw_input = sys.stdin.buffer.read()

    try:
        hook_input = annotate_hook_input(raw_input, harness)
    except (ValueError, RecursionError, OSError):
        hook_input = raw_input

    stdin = tempfile.TemporaryFile()
    stdin.write(hook_input)
    stdin.seek(0)

    os.dup2(stdin.fileno(), 0)

    signal.signal(signal.SIGPIPE, signal.SIG_DFL)
    signal.signal(signal.SIGXFSZ, signal.SIG_DFL)

    os.execvp("sh", ["sh", "-c", command])


if __name__ == "__main__":
    run_hook(sys.argv[1], sys.argv[2])
