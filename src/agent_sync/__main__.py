import argparse
import logging
from typing import Literal

from pydantic import BaseModel, ConfigDict

from agent_sync.errors import AgentSyncError
from agent_sync.mirror import mirror_providers
from agent_sync.vendor.vendor import vendor_skills
from agent_sync.workspace import Workspace

logger = logging.getLogger(__name__)


class CliArguments(BaseModel):
    """Validate parsed command-line arguments before dispatch."""

    model_config = ConfigDict(extra="forbid", strict=True)

    command: Literal["mirror-providers", "vendor-skills"]
    root: str | None
    agents_dir: str | None
    dry_run: bool


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
        description="Mirror canonical agent sources and vendor registered skills.",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    mirror_parser = commands.add_parser(
        "mirror-providers",
        help="Mirror canonical sources into provider configuration paths.",
    )
    add_workspace_arguments(mirror_parser)

    vendor_parser = commands.add_parser(
        "vendor-skills",
        help="Vendor registered external skills into canonical sources.",
    )
    add_workspace_arguments(vendor_parser)

    return parser


if __name__ == "__main__":
    parser = create_parser()
    parsed = CliArguments.model_validate(vars(parser.parse_args()))
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    workspace = Workspace.resolve(parsed.root, parsed.agents_dir)

    try:
        match parsed.command:
            case "mirror-providers":
                differences_found = mirror_providers(workspace, parsed.dry_run)
            case "vendor-skills":
                differences_found = vendor_skills(workspace, parsed.dry_run)
        exit_code = 1 if differences_found else 0
    except (AgentSyncError, OSError, RuntimeError) as exc:
        logger.error("%s", exc)
        exit_code = 2

    raise SystemExit(exit_code)
