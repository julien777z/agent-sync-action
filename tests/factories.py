import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from shlex import quote
from typing import Literal

import pytest
from polyfactory.factories.pydantic_factory import ModelFactory

from agent_sync.config import ActionConfig
from agent_sync.document import render_front_matter
from agent_sync.external_resources import directories, skills
from agent_sync.generation.context import load_generation_context
from agent_sync.models.generation import GenerationContext
from agent_sync.models.hooks import CommandHook, HookMatcher, HooksConfig
from agent_sync.models.document import RuleFrontMatter, SkillFrontMatter
from agent_sync.models.output import Harness
from agent_sync.models.registry import ExternalDirectory, ExternalSkill, ResourcesRegistry
from agent_sync.source import load_source_config
from agent_sync.models.settings import Workspace
from agent_sync.workspace import agents_dir, output_root

ROOT_LEVEL_SKILL: ExternalSkill = ExternalSkill(
    kind="skill",
    name="local-skill",
    repo="example/repository",
    skill="upstream-skill",
    update_on_sync=True,
)


def load_context(workspace: Workspace) -> GenerationContext:
    """Load generation inputs from one test workspace."""

    return load_generation_context(workspace, load_source_config(workspace))


def stub_skill_upstream(
    monkeypatch: pytest.MonkeyPatch,
    upstream_document: str | None = None,
    root_license: str | None = None,
    installed_license: str | None = None,
    installed_license_kind: Literal["file", "link", "directory"] = "file",
    nested_skill: bool = False,
) -> None:
    """Serve a synthetic upstream repository containing the requested skill."""

    if upstream_document is None:
        upstream_document = "---\nname: upstream-skill\ndescription: A skill.\n---\n\nContent.\n"

    def fake_resolve(repository: str) -> str:
        """Return a stable synthetic revision."""

        return "a" * 40

    def fake_download(repository: str, revision: str, destination: Path) -> Path:
        """Create an upstream skill document at the selected source location."""

        source_root = destination / "repository"
        source_root.mkdir(parents=True)
        source_skill = source_root / "upstream-skill" if nested_skill else source_root
        source_skill.mkdir(parents=True, exist_ok=True)
        (source_skill / "SKILL.md").write_text(upstream_document)
        if root_license is not None:
            (source_root / "LICENSE").write_text(root_license)

        return source_root

    def fake_install(
        installed_skill: ExternalSkill,
        working_directory: Path,
        source_root: Path,
        config: ActionConfig,
    ) -> None:
        """Create the installed skill in the staging directory."""

        installed = working_directory / ".staging/skills" / installed_skill.name
        installed.mkdir(parents=True)
        (installed / "SKILL.md").write_text(upstream_document)
        if installed_license is not None:
            if installed_license_kind == "link":
                (installed / "asset.txt").write_text(installed_license)
                (installed / "LICENSE").symlink_to("asset.txt")
            elif installed_license_kind == "directory":
                (installed / "LICENSE").mkdir()
            else:
                (installed / "LICENSE").write_text(installed_license)

    monkeypatch.setattr(skills, "resolve_revision", fake_resolve)
    monkeypatch.setattr(skills, "download_snapshot", fake_download)
    monkeypatch.setattr(skills, "install_skill", fake_install)


def stub_external_directory_upstream(
    monkeypatch: pytest.MonkeyPatch,
    resource: ExternalDirectory,
    files: dict[str, str],
    root_license: str | None = None,
    snapshot_path: str | None = None,
    links: dict[str, str] | None = None,
) -> None:
    """Serve a synthetic upstream reference directory from an immutable snapshot."""

    def fake_resolve(repository: str) -> str:
        """Return a stable synthetic revision."""

        return "a" * 40

    def fake_download(repository: str, revision: str, destination: Path) -> Path:
        """Materialize the selected directory in a synthetic snapshot."""

        root = destination / "repository"
        materialize_tree(root / (snapshot_path or resource.source_path), files)
        for link, target in (links or {}).items():
            link_path = root / link
            link_path.parent.mkdir(parents=True, exist_ok=True)
            link_path.symlink_to(target, target_is_directory=True)
        if root_license is not None:
            (root / "LICENSE").write_text(root_license, encoding="utf-8")
        return root

    monkeypatch.setattr(directories, "resolve_revision", fake_resolve)
    monkeypatch.setattr(directories, "download_snapshot", fake_download)


class SkillFrontMatterFactory(ModelFactory[SkillFrontMatter]):
    """Build valid canonical skill metadata."""

    __model__ = SkillFrontMatter

    name = "sample-skill"
    description = "Does a thing."
    disable_model_invocation = False


class RuleFrontMatterFactory(ModelFactory[RuleFrontMatter]):
    """Build canonical rule metadata with deterministic defaults."""

    __model__ = RuleFrontMatter

    description = "A rule."
    paths = None
    always_apply = True
    starlark = None


class HooksConfigFactory(ModelFactory[HooksConfig]):
    """Build shared lifecycle registration with deterministic matcher groups."""

    __model__ = HooksConfig

    description = "Workspace initialization"

    @classmethod
    def hooks(cls) -> dict[str, list[HookMatcher]]:
        """Register one command for session startup and resume."""

        return {
            "SessionStart": [
                HookMatcher(
                    hooks=[
                        CommandHook(
                            type="command",
                            command='python3 "$(git rev-parse --show-toplevel)/.agents/hooks/session/start.py"',
                            timeout=3,
                        )
                    ]
                )
            ]
        }


def adapted_hook_command(workspace: Workspace, harness: Harness, command: str) -> str:
    """Return the registered form of a canonical hook command for one harness."""

    adapter = harness.root(output_root(workspace)) / "hooks/agent_sync_adapter.py"

    return (
        f'exec python3 "$(git rev-parse --show-toplevel)"/{quote(adapter.relative_to(workspace.root).as_posix())} '
        f"{harness.value} {quote(command)}"
    )


def materialize_hooks(workspace: Workspace, config: HooksConfig) -> None:
    """Write shared lifecycle registration and its nested script resources."""

    materialize_tree(
        agents_dir(workspace) / "hooks",
        {
            "hooks.json": config.model_dump_json(by_alias=True, exclude_none=True),
            "session/start.py": "#!/usr/bin/env python3\nfrom helpers import context\nprint(context())\n",
            "session/helpers.py": (
                "from pathlib import Path\n\ndef context():\n"
                "    return (Path(__file__).parent / 'resources/context.md').read_text().strip()\n"
            ),
            "session/resources/context.md": "Workspace context.\n",
        },
    )


class ExternalSkillFactory(ModelFactory[ExternalSkill]):
    """Build valid external-skill registrations."""

    __model__ = ExternalSkill

    kind = "skill"
    name = "sample"
    repo = "example/repository"
    skill = None
    category = None
    skill_name_override = None
    update_on_sync = True


class ExternalResourceFactory(ModelFactory[ExternalDirectory]):
    """Build valid external-reference registrations."""

    __model__ = ExternalDirectory

    kind = "directory"
    name = "sample-reference"
    repo = "example/reference"
    source_path = "guides"
    update_on_sync = True


class ResourcesRegistryFactory(ModelFactory[ResourcesRegistry]):
    """Build deterministic external-reference registries."""

    __model__ = ResourcesRegistry

    version = 1

    @classmethod
    def resources(cls) -> list[ExternalSkill | ExternalDirectory]:
        """Default to an empty external-resource registry."""

        return []


def materialize_skill(
    path: Path,
    front_matter: SkillFrontMatter,
    body: str = "Body text.",
) -> None:
    """Write one generated canonical skill document."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        render_front_matter(front_matter, f"# {front_matter.name}\n\n{body}"),
        encoding="utf-8",
    )


def materialize_rule(
    path: Path,
    front_matter: RuleFrontMatter,
    body: str = "# Rule\n\nAlways be ruling.",
) -> None:
    """Write one generated canonical rule document."""

    raw_front_matter = front_matter.model_dump(
        by_alias=True,
        exclude_defaults=True,
        exclude_none=True,
    )

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_front_matter(raw_front_matter, body), encoding="utf-8")


def materialize_registry(path: Path, registry: ResourcesRegistry) -> None:
    """Write one external registry into canonical sources."""

    path.write_text(registry.model_dump_json(), encoding="utf-8")


def run_cli(arguments: list[str]) -> subprocess.CompletedProcess[str]:
    """Run the package script with its real command-line boundary."""

    return subprocess.run(
        [sys.executable, "-m", "agent_sync", *arguments],
        capture_output=True,
        text=True,
        check=False,
    )


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


def materialize_tree(base: Path, files: dict[str, str]) -> None:
    """Write a relative text-file mapping under one directory."""

    for relative, content in files.items():
        target = base / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")


def materialize_every_source_kind(workspace: Workspace, explicit_invocation: bool = False) -> None:
    """Write one canonical source of every kind a harness tree mirrors."""

    materialize_rule(
        agents_dir(workspace) / "rules/sample.md",
        RuleFrontMatterFactory.build(name="sample", always_apply=False),
    )

    materialize_hooks(workspace, HooksConfigFactory.build())

    materialize_skill(
        agents_dir(workspace) / "skills/sample/SKILL.md",
        SkillFrontMatterFactory.build(name="sample", disable_model_invocation=explicit_invocation),
    )
