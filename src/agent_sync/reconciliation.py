import difflib
import logging
import os
import re
from pathlib import Path
from typing import Final

from agent_sync.generation.rule import CODEX_RULE_MARKER
from agent_sync.models.output import (
    Change,
    GeneratedFile,
    GeneratedLink,
    GeneratedOutput,
    Manifest,
    Provider,
    ReconciliationPlan,
)
from agent_sync.models.provider import PROVIDER_LAYOUTS
from agent_sync.workspace import Workspace

logger = logging.getLogger(__name__)

MAX_DIFF_LINES: Final[int] = 20
NUMBERED_COPY_PATTERN: Final[re.Pattern[str]] = re.compile(r" \d+$")


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
    managed_directories = (
        (Provider.CLAUDE, "rules"),
        (Provider.CURSOR, "rules"),
        (Provider.CLAUDE, "commands"),
        (Provider.CURSOR, "commands"),
        (Provider.CLAUDE, "agents"),
        (Provider.CURSOR, "agents"),
        (Provider.CLAUDE, "hooks"),
        (Provider.CURSOR, "hooks"),
    )
    for provider, dirname in managed_directories:
        directory = PROVIDER_LAYOUTS[provider].root(workspace.root) / dirname
        if not directory.exists():
            continue

        for path in directory.iterdir():
            if (path.is_file() or path.is_symlink()) and path not in expected:
                stale.add(path)
            if dirname == "rules" and NUMBERED_COPY_PATTERN.search(path.stem):
                stale.add(path)

    for provider in Provider:
        skills_dir = PROVIDER_LAYOUTS[provider].root(workspace.root) / "skills"
        if not skills_dir.exists():
            continue

        for path in skills_dir.iterdir():
            if (path.is_dir() or path.is_symlink()) and path not in expected:
                stale.add(path)

    codex_rules_dir = PROVIDER_LAYOUTS[Provider.CODEX].root(workspace.root) / "rules"
    if codex_rules_dir.exists():
        for path in codex_rules_dir.glob("*.rules"):
            content = workspace.read_text(path)
            if (
                path not in expected
                and content is not None
                and content.startswith(CODEX_RULE_MARKER)
            ):
                stale.add(path)

    claude_settings = PROVIDER_LAYOUTS[Provider.CLAUDE].root(workspace.root) / "settings.json"
    if claude_settings.exists() and claude_settings not in expected:
        stale.add(claude_settings)

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
