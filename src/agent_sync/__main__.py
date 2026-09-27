import argparse
import logging

from pydantic import ValidationError

from agent_sync.config import ActionConfig
from agent_sync.errors import AgentSyncError
from agent_sync.external_resources.sync import sync_external_resources
from agent_sync.models.workspace import CliArguments
from agent_sync.reconciliation import mirror_providers
from agent_sync.workspace import resolve_workspace

logger: logging.Logger = logging.getLogger(__name__)


def add_workspace_arguments(parser: argparse.ArgumentParser) -> None:
    """Add common workspace and dry-run options to a command parser."""

    parser.add_argument(
        "--root",
        default=None,
        help="Repository root (default: $AGENT_SYNC_ROOT or cwd).",
    )

    parser.add_argument(
        "--agents-dir",
        default=None,
        help="Canonical source directory (default: $AGENT_SYNC_AGENTS_DIR or .agents).",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report changes without writing.",
    )


def create_parser() -> argparse.ArgumentParser:
    """Create the Agent Sync command-line parser."""

    parser = argparse.ArgumentParser(
        prog="agent-sync",
        description="Mirror canonical agent sources and vendor registered skills and resources.",
    )

    commands = parser.add_subparsers(dest="command", required=True)

    mirror_parser = commands.add_parser(
        "mirror-providers",
        help="Mirror canonical sources into provider configuration paths.",
    )
    add_workspace_arguments(mirror_parser)

    mirror_parser.add_argument(
        "--output-dir",
        default=None,
        help=(
            "Directory that holds generated provider trees, relative to the root "
            "(default: $AGENT_SYNC_OUTPUT_DIR or the root itself)."
        ),
    )

    resource_parser = commands.add_parser(
        "vendor-resources",
        help="Vendor registered external skills and reference directories into canonical sources.",
    )
    add_workspace_arguments(resource_parser)

    return parser


if __name__ == "__main__":
    parser = create_parser()
    parsed = CliArguments.model_validate(vars(parser.parse_args()))
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    try:
        config = ActionConfig()
        workspace = resolve_workspace(parsed.root, parsed.agents_dir, parsed.output_dir, config)

        match parsed.command:
            case "mirror-providers":
                differences_found = mirror_providers(workspace, parsed.dry_run)
            case "vendor-resources":
                sync_external_resources(workspace, parsed.dry_run, config)
                differences_found = False

        exit_code = 1 if differences_found else 0
    except (AgentSyncError, OSError, RuntimeError, ValidationError) as exc:
        logger.error("%s", exc)
        exit_code = 2

    raise SystemExit(exit_code)
