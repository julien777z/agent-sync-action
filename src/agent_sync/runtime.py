import argparse

from agent_sync.external_skills import run_refresh
from agent_sync.sync import run_sync
from agent_sync.utils import fs
from agent_sync.utils.console import configure_logging


def main() -> int:
    """Dispatch the `sync` and `refresh` subcommands against a configured repository root."""

    parser = argparse.ArgumentParser(prog="agent_sync", description="Disperse .agents and refresh skills.sh skills.")
    subcommands = parser.add_subparsers(dest="command", required=True)

    sync_parser = subcommands.add_parser("sync", help="Disperse .agents into Claude/Cursor/Codex folders.")
    fs.add_root_arguments(sync_parser)
    sync_parser.add_argument("--dry-run", action="store_true", help="Report diffs without writing.")

    refresh_parser = subcommands.add_parser("refresh", help="Install/update external skills from the registry.")
    fs.add_root_arguments(refresh_parser)
    refresh_parser.add_argument("--dry-run", action="store_true", help="Report changes without writing.")

    args = parser.parse_args()

    configure_logging()
    fs.set_root_from_args(args)

    if args.command == "sync":
        return run_sync(dry_run=args.dry_run)

    return run_refresh(dry_run=args.dry_run)
