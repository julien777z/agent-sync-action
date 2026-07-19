import difflib
import logging
import os
from pathlib import Path
from typing import Final

from agent_sync.errors import AgentSyncError
from agent_sync.generation.registry import (
    ARTIFACT_REGISTRY,
    generate_manifest,
    owned_provider_directories,
)
from agent_sync.models.output import (
    Change,
    GeneratedFile,
    GeneratedLink,
    GeneratedOutput,
    Manifest,
    ReconciliationPlan,
)
from agent_sync.providers import PROVIDER_LAYOUTS
from agent_sync.source import load_source_config
from agent_sync.workspace import Workspace

logger = logging.getLogger(__name__)

MAX_DIFF_LINES: Final[int] = 20


def mirror_providers(workspace: Workspace, dry_run: bool) -> bool:
    """Mirror agent sources and report whether a dry run found differences."""

    if not workspace.agents_dir.exists():
        raise AgentSyncError(f"Missing agents directory: {workspace.agents_dir}")

    source_config = load_source_config(workspace)
    manifest = generate_manifest(workspace, source_config)
    plan = build_plan(workspace, manifest)

    if plan.is_clean:
        logger.info("No differences found.")

        return False

    if dry_run:
        report_plan(plan)

        return True

    apply_plan(workspace, plan)

    logger.info(
        "Mirroring complete. %d output(s) written, %d stale path(s) deleted.",
        len(plan.changes),
        len(plan.stale_paths),
    )

    return False


def build_plan(workspace: Workspace, manifest: Manifest) -> ReconciliationPlan:
    """Compare a generated manifest with managed workspace state."""

    stale_paths = find_stale_paths(workspace, manifest)
    changes: list[Change] = []

    for output in manifest.outputs:
        change = compare_output(workspace, output)

        if change is not None:
            changes.append(change)
        elif any(stale_path in output.target_path.parents for stale_path in stale_paths):
            changes.append(Change(output=output, existing=None))

    return ReconciliationPlan(changes=changes, stale_paths=stale_paths)


def compare_output(
    workspace: Workspace,
    output: GeneratedOutput,
) -> Change | None:
    """Return a change when one generated output differs from disk."""

    if isinstance(output, GeneratedLink):
        existing = workspace.read_link(output.target_path)
        expected = os.path.relpath(output.link_target, output.target_path.parent)

        return None if existing == expected else Change(output=output, existing=existing)

    if output.target_path.is_symlink() or output.target_path.is_dir():
        return Change(output=output, existing=None)

    existing = workspace.read_text(output.target_path)
    executable_matches = (
        not output.target_path.exists()
        or bool(output.target_path.stat().st_mode & 0o111) == output.executable
    )

    if existing == output.content and executable_matches:
        return None

    return Change(output=output, existing=existing)


def find_stale_paths(workspace: Workspace, manifest: Manifest) -> list[Path]:
    """Find paths owned by Agent Sync but absent from the generated manifest."""

    expected = {output.target_path for output in manifest.outputs}
    stale: set[Path] = set()

    stale.update(
        blocker
        for output in manifest.outputs
        for blocker in workspace.find_parent_blockers(output.target_path)
    )

    for provider, directory_name in owned_provider_directories():
        directory = PROVIDER_LAYOUTS[provider].root(workspace.root) / directory_name

        if directory.is_symlink() or (directory.exists() and not directory.is_dir()):
            stale.add(directory)
        elif directory.is_dir():
            stale.update(path for path in directory.iterdir() if path not in expected)

    for registration in ARTIFACT_REGISTRY.values():
        for provider, filenames in registration["owned_files"].items():
            root = PROVIDER_LAYOUTS[provider].root(workspace.root)

            stale.update(
                path
                for filename in filenames
                if ((path := root / filename).exists() or path.is_symlink())
                and path not in expected
            )

    return sorted(stale, key=str)


def apply_plan(workspace: Workspace, plan: ReconciliationPlan) -> None:
    """Apply one validated reconciliation plan to disk."""

    for stale_path in plan.stale_paths:
        workspace.delete(stale_path)

        logger.info("deleted: %s", stale_path)

    for change in plan.changes:
        output = change.output

        if isinstance(output, GeneratedFile):
            workspace.replace_text(output.target_path, output.content, output.executable)

            status = "created" if change.existing is None else "updated"
            logger.info("%s: %s", status, output.target_path)
        else:
            workspace.replace_link(output.target_path, output.link_target)

            logger.info(
                "linked: %s -> %s",
                output.target_path,
                os.path.relpath(output.link_target, output.target_path.parent),
            )


def report_plan(plan: ReconciliationPlan) -> None:
    """Log every generated difference and stale managed path."""

    logger.info("Differences detected:")

    for change in plan.changes:
        status = "missing" if change.existing is None else "changed"
        logger.info(
            "  [%s] %s (%s)",
            status,
            change.output.target_path,
            change.output.artifact,
        )

    for stale_path in plan.stale_paths:
        logger.info("  [stale] %s", stale_path)

    for change in plan.changes:
        logger.info("--- %s ---\n%s", change.output.target_path, summarize_change(change))

    for stale_path in plan.stale_paths:
        logger.info("--- %s ---\nwill be deleted", stale_path)


def summarize_change(change: Change) -> str:
    """Render a concise unified diff or symlink target change."""

    if isinstance(change.output, GeneratedLink):
        relative_target = os.path.relpath(
            change.output.link_target,
            change.output.target_path.parent,
        )

        return f"symlink -> {relative_target}"

    existing = change.existing or ""
    expected = change.output.content
    lines = list(
        difflib.unified_diff(
            existing.splitlines(),
            expected.splitlines(),
            fromfile="current",
            tofile="expected",
            lineterm="",
        )
    )

    if not lines:
        return "(trailing newline or executable-mode difference)"

    return "\n".join(lines[:MAX_DIFF_LINES])
