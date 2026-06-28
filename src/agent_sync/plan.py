import difflib
import logging
from pathlib import Path

from agent_sync.constants import CODEX_RULE_MARKER, MAX_DIFF_LINES
from agent_sync.loaders import settings_dir
from agent_sync.models.outputs import DiffEntry, OutputFile, OutputKind
from agent_sync.utils import fs
from agent_sync.utils.slugs import NUMBERED_COPY_PATTERN

logger = logging.getLogger(__name__)

SKILL_DIR_KINDS: frozenset[OutputKind] = frozenset(
    {OutputKind.CURSOR_SKILL, OutputKind.CLAUDE_SKILL, OutputKind.CODEX_SKILL}
)


def compute_diffs(outputs: list[OutputFile]) -> list[DiffEntry]:
    """Compare generated outputs against on-disk files and return entries that differ."""

    diffs: list[DiffEntry] = []
    for output in outputs:
        existing: str | bytes | None = (
            fs.read_bytes(output.target_path)
            if isinstance(output.content, bytes)
            else fs.read_text(output.target_path)
        )
        if existing != output.content or missing_exec_bit(output):
            diffs.append(DiffEntry(output=output, existing=existing))

    return diffs


def missing_exec_bit(output: OutputFile) -> bool:
    """Report whether an executable output exists on disk without its exec bit, so write re-applies chmod."""

    target = output.target_path
    if not fs.is_executable_output(target, output.content):
        return False

    return target.exists() and not target.stat().st_mode & 0o111


def compute_stale_paths(
    outputs: list[OutputFile],
    platform_settings: dict[str, dict],
) -> list[Path]:
    """Find generated files/directories that no longer map to .agents sources."""

    expected_paths = {output.target_path for output in outputs}
    expected_skill_dirs = {
        output.target_path.parent for output in outputs if output.kind in SKILL_DIR_KINDS
    }
    stale_paths: set[Path] = set()

    managed_file_globs = (
        (fs.root() / ".cursor" / "rules", "*.mdc"),
        (fs.root() / ".claude" / "rules", "*.md"),
        (fs.root() / ".cursor" / "commands", "*.md"),
        (fs.root() / ".claude" / "commands", "*.md"),
        (fs.root() / ".cursor" / "agents", "*.md"),
        (fs.root() / ".claude" / "agents", "*.md"),
        (fs.root() / ".cursor" / "hooks", "*"),
        (fs.root() / ".claude" / "hooks", "*"),
        (fs.root() / ".cursor" / "skills", "**/*"),
        (fs.root() / ".claude" / "skills", "**/*"),
        (fs.root() / ".codex" / "skills", "**/*"),
    )

    for directory, pattern in managed_file_globs:
        if not directory.exists():
            continue

        for path in directory.glob(pattern):
            if path.is_file() and path not in expected_paths:
                stale_paths.add(path)

    codex_rules_dir = fs.root() / ".codex" / "rules"
    if codex_rules_dir.exists():
        for path in codex_rules_dir.glob("*.rules"):
            if not path.is_file() or path in expected_paths:
                continue
            head = fs.read_text(path)
            if head is not None and head.startswith(CODEX_RULE_MARKER):
                stale_paths.add(path)

    settings_path = fs.root() / ".claude" / "settings.json"
    claude_source = settings_dir() / "claude.json"
    if (
        settings_path.exists()
        and settings_path not in expected_paths
        and ("claude" in platform_settings or not claude_source.exists())
    ):
        stale_paths.add(settings_path)

    for platform in ("codex", "claude", "cursor"):
        skills_subdir = fs.root() / f".{platform}" / "skills"
        if not skills_subdir.exists():
            continue
        for path in skills_subdir.iterdir():
            if path.is_dir() and path not in expected_skill_dirs:
                stale_paths.add(path)

    return sorted(stale_paths, key=str)


def report_diffs(diffs: list[DiffEntry], stale_paths: list[Path]) -> None:
    """Log the table and unified diffs for everything that would change in a dry run."""

    logger.info("Differences detected:")

    for diff in diffs:
        status = "missing" if diff.existing is None else "changed"
        logger.info("  [%s] %s (%s)", status, diff.output.target_path, diff.output.kind)

    for stale_path in stale_paths:
        kind = "directory" if stale_path.is_dir() else "generated"
        logger.info("  [stale] %s (%s)", stale_path, kind)

    for diff in diffs:
        logger.info("--- %s ---\n%s", diff.output.target_path, diff_summary(diff))

    for stale_path in stale_paths:
        logger.info("--- %s ---\nwill be deleted", stale_path)


def diff_summary(diff: DiffEntry) -> str:
    """Produce a unified diff between existing and expected content, or note a binary change."""

    existing = diff.existing
    expected = diff.output.content
    if isinstance(existing, bytes) or isinstance(expected, bytes):
        return "(binary file)"

    existing = existing or ""
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
        if existing != expected:
            return "(trailing newline difference)"

        return "(no changes)"

    return "\n".join(lines[:MAX_DIFF_LINES])


def dedupe_outputs() -> None:
    """Remove OS-created duplicate rule files in the generated Claude/Cursor rule directories."""

    for directory in (fs.root() / ".cursor" / "rules", fs.root() / ".claude" / "rules"):
        dedupe_directory(directory)


def dedupe_directory(directory: Path) -> None:
    """Remove OS-created duplicate files whose name ends with a space and a number (e.g. "name 2.md")."""

    if not directory.exists():
        return

    for path in sorted(directory.iterdir()):
        if path.is_file() and NUMBERED_COPY_PATTERN.search(path.stem):
            path.unlink(missing_ok=True)
            fs.TEXT_CACHE.pop(path, None)
