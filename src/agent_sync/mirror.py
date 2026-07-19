import logging

from agent_sync.errors import AgentSyncError
from agent_sync.generation.manifest import generate_manifest
from agent_sync.reconciliation import apply_plan, build_plan, report_plan
from agent_sync.source import load_configuration
from agent_sync.workspace import Workspace

logger = logging.getLogger(__name__)


def mirror_providers(workspace: Workspace, dry_run: bool) -> int:
    """Mirror canonical agent sources into every supported provider layout."""

    if not workspace.agents_dir.exists():
        raise AgentSyncError(f"Missing agents directory: {workspace.agents_dir}")

    configuration = load_configuration(workspace)
    manifest = generate_manifest(workspace, configuration)
    plan = build_plan(workspace, manifest)
    if plan.is_clean:
        logger.info("No differences found.")

        return 0

    if dry_run:
        report_plan(plan)

        return 1

    apply_plan(workspace, plan)
    logger.info(
        "Mirroring complete. %d output(s) written, %d stale path(s) deleted.",
        len(plan.changes),
        len(plan.stale_paths),
    )

    return 0
