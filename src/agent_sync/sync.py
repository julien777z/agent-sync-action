import argparse
import logging

from agent_sync.generate import generate_outputs
from agent_sync.loaders import load_agent_model_overrides, load_platform_settings
from agent_sync.plan import compute_diffs, compute_stale_paths, dedupe_outputs, report_diffs
from agent_sync.utils import fs

logger = logging.getLogger(__name__)


def run_sync(dry_run: bool) -> int:
    """Sync .agents into the Claude/Cursor/Codex folders for the configured root."""

    if not fs.agents_dir().exists():
        logger.error("Missing agents directory: %s", fs.agents_dir())

        return 2

    platform_settings = load_platform_settings()
    agent_model_overrides = load_agent_model_overrides()
    outputs = generate_outputs(platform_settings, agent_model_overrides)
    diffs = compute_diffs(outputs)
    stale_paths = compute_stale_paths(outputs, platform_settings)

    if not diffs and not stale_paths:
        logger.info("No differences found.")

        return 0

    if dry_run:
        report_diffs(diffs, stale_paths)

        return 1

    for diff in diffs:
        fs.write_text(diff.output.target_path, diff.output.content)
        status = "created" if diff.existing is None else "updated"
        logger.info("%s: %s", status, diff.output.target_path)

    for stale_path in stale_paths:
        fs.delete_path(stale_path)
        logger.info("deleted: %s", stale_path)

    dedupe_outputs()

    logger.info(
        "Sync complete. %d file(s) written, %d stale path(s) deleted.",
        len(diffs),
        len(stale_paths),
    )

    return 0


def main() -> int:
    """Disperse .agents into the Claude/Cursor/Codex folders for a configured root."""

    parser = argparse.ArgumentParser(
        prog="agent_sync.sync",
        description="Disperse .agents into Claude/Cursor/Codex folders.",
    )
    fs.add_root_arguments(parser)
    parser.add_argument("--dry-run", action="store_true", help="Report diffs without writing.")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    fs.set_root_from_args(args)

    return run_sync(dry_run=args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
