from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from typing import TypedDict, cast

ADDED_FILE_HEADER = "*** Add File: "
UPDATED_FILE_HEADER = "*** Update File: "
MOVED_FILE_HEADER = "*** Move to: "


class AgentSyncBlock(TypedDict):
    """Describe the harness-neutral facts added to every hook input."""

    harness: str
    project_dir: str
    edited_files: list[str]


def read_project_dir(cwd: str) -> str:
    """Return the Git root containing a directory, or the directory itself outside a repository."""

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
    """Return the files an apply_patch body adds, updates or moves to, excluding deletions."""

    paths: list[str] = []

    for line in patch.splitlines():
        if line.startswith(MOVED_FILE_HEADER) and paths:
            paths[-1] = line[len(MOVED_FILE_HEADER) :].strip()
        elif line.startswith(ADDED_FILE_HEADER) or line.startswith(UPDATED_FILE_HEADER):
            paths.append(line.split(": ", 1)[1].strip())

    return paths


def read_edited_files(payload: dict[str, object], cwd: str) -> list[str]:
    """Return the absolute, normalized and deduplicated files a tool call edited."""

    tool_input = payload.get("tool_input", {})

    if not isinstance(tool_input, dict):
        raise ValueError("tool_input must be an object")

    fields = cast("dict[str, object]", tool_input)
    candidates = [fields.get("file_path"), fields.get("notebook_path"), payload.get("file_path")]
    patch = fields.get("command")

    if payload.get("tool_name") == "apply_patch" and isinstance(patch, str):
        candidates.extend(read_patch_paths(patch))

    paths = [
        os.path.normpath(os.path.join(cwd, path)) for path in candidates if isinstance(path, str) and path
    ]

    return list(dict.fromkeys(paths))


def annotate_hook_input(raw_input: bytes, harness: str) -> bytes:
    """Return the hook input with the agent_sync block added beside every original key."""

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
    """Replace this process with the hook command, reading the annotated or original input."""

    raw_input = sys.stdin.buffer.read()

    try:
        hook_input = annotate_hook_input(raw_input, harness)
    except (ValueError, RecursionError, OSError, subprocess.SubprocessError):
        hook_input = raw_input

    stdin = tempfile.TemporaryFile()
    stdin.write(hook_input)
    stdin.seek(0)

    os.dup2(stdin.fileno(), 0)

    os.execvp("sh", ["sh", "-c", command])


if __name__ == "__main__":
    run_hook(sys.argv[1], sys.argv[2])
