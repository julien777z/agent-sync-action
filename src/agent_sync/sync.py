import argparse
import logging

from agent_sync.generate import generate_outputs
from agent_sync.loaders import (
    McpConfigError,
    load_agent_model_overrides,
    load_mcp_config,
    load_platform_settings,
)
from agent_sync.mcp import McpGenerationError
from agent_sync.codex import CodexGenerationError
from agent_sync.plan import (
    compute_diffs,
    compute_stale_paths,
    dedupe_outputs,
    expected_link_text,
    report_diffs,
)
from agent_sync.utils import fs
from agent_sync.validation import AgentSyncValidationError, validate_codex_instruction_capacity

logger = logging.getLogger(__name__)


def run_sync(dry_run: bool) -> int:
    """Sync .agents into the Claude/Cursor/Codex folders for the configured root."""

    if not fs.agents_dir().exists():
        logger.error("Missing agents directory: %s", fs.agents_dir())

        return 2

    platform_settings = load_platform_settings()
    agent_model_overrides = load_agent_model_overrides()
    try:
        codex_settings = platform_settings.get("codex")
        if codex_settings is not None:
            validate_codex_instruction_capacity(codex_settings)
        mcp_config = load_mcp_config()
        outputs = generate_outputs(platform_settings, agent_model_overrides, mcp_config)
    except (AgentSyncValidationError, CodexGenerationError, McpConfigError, McpGenerationError) as exc:
        logger.error("%s", exc)

        return 2
    diffs = compute_diffs(outputs)
    stale_paths = compute_stale_paths(outputs, platform_settings)

    if not diffs and not stale_paths:
        logger.info("No differences found.")

        return 0

    if dry_run:
        report_diffs(diffs, stale_paths)

        return 1

    for diff in diffs:
        if diff.output.link_target is not None:
            continue
        fs.write(diff.output.target_path, diff.output.content)
        status = "created" if diff.existing is None else "updated"
        logger.info("%s: %s", status, diff.output.target_path)

    for diff in diffs:
        if diff.output.link_target is None:
            continue
        fs.write_symlink(diff.output.target_path, diff.output.link_target)
        logger.info("linked: %s -> %s", diff.output.target_path, expected_link_text(diff.output))

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
