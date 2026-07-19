import difflib
import logging
import os
from pathlib import Path
from typing import Final

from agent_sync.generation.registry import ARTIFACT_REGISTRY, owned_provider_directories
from agent_sync.models.output import (
    Change,
    GeneratedFile,
    GeneratedLink,
    GeneratedOutput,
    Manifest,
    ReconciliationPlan,
)
from agent_sync.models.provider import PROVIDER_LAYOUTS
from agent_sync.workspace import Workspace

logger = logging.getLogger(__name__)

MAX_DIFF_LINES: Final[int] = 20


def build_plan(workspace: Workspace, manifest: Manifest) -> ReconciliationPlan:
    """Compare a generated manifest with managed workspace state."""

    changes = [
        change
        for output in manifest.outputs
        if (change := compare_output(workspace, output)) is not None
    ]
    stale_paths = find_stale_paths(workspace, manifest)

    return ReconciliationPlan(changes=changes, stale_paths=stale_paths)


def compare_output(
    workspace: Workspace,
    output: GeneratedOutput,
) -> Change | None:
    """Return a change when one generated output differs from disk."""

    if isinstance(output, GeneratedLink):
        existing = workspace.read_link(output.target_path)
        expected = expected_link(output)

        return None if existing == expected else Change(output=output, existing=existing)

    existing = workspace.read_text(output.target_path)
    executable_matches = (
        not output.target_path.exists()
        or bool(output.target_path.stat().st_mode & 0o111) == output.executable
    )
    if existing == output.content and executable_matches:
        return None

    return Change(output=output, existing=existing)


def expected_link(output: GeneratedLink) -> str:
    """Return the relative target text for a generated symlink."""

    return os.path.relpath(output.link_target, output.target_path.parent)


def find_stale_paths(workspace: Workspace, manifest: Manifest) -> list[Path]:
    """Find paths owned by Agent Sync but absent from the generated manifest."""

    expected = {output.target_path for output in manifest.outputs}
    stale: set[Path] = set()
    for provider, directory_name in owned_provider_directories():
        directory = PROVIDER_LAYOUTS[provider].root(workspace.root) / directory_name
        if directory.exists():
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
            logger.info("linked: %s -> %s", output.target_path, expected_link(output))


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
        return f"symlink -> {expected_link(change.output)}"

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
