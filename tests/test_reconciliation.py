import os

import pytest
from pydantic import ValidationError

from agent_sync.generation.generation import generate_manifest
from agent_sync.mirror import mirror_providers
from agent_sync.models.output import (
    ArtifactKind,
    GeneratedFile,
    GeneratedLink,
    Manifest,
    Provider,
)
from agent_sync.reconciliation import apply_plan, build_plan
from agent_sync.source import load_configuration
from agent_sync.workspace import Workspace


class TestManifest:
    """Verify generated output ownership is unambiguous."""

    def test_duplicate_targets_are_rejected(self, workspace: Workspace) -> None:
        """Test that two outputs cannot own the same target path."""

        output = GeneratedFile(
            target_path=workspace.root / "same",
            content="content\n",
            artifact=ArtifactKind.RULE,
            source_path=workspace.agents_dir / "rules/sample.md",
        )

        with pytest.raises(ValidationError, match="Duplicate generated targets"):
            Manifest(outputs=[output, output])


class TestReconciliation:
    """Verify managed output comparison and mutation behavior."""

    def test_replaces_files_and_directories_with_relative_links(
        self,
        workspace: Workspace,
    ) -> None:
        """Test that link outputs replace either legacy target shape safely."""

        source = workspace.agents_dir / "rules/sample.md"
        source.parent.mkdir()
        source.write_text("source\n")
        file_target = workspace.root / ".claude/rules/sample.md"
        file_target.parent.mkdir(parents=True)
        file_target.write_text("copy\n")
        directory_target = workspace.root / ".cursor/skills/sample"
        directory_target.mkdir(parents=True)
        (directory_target / "SKILL.md").write_text("copy\n")
        manifest = Manifest(
            outputs=[
                GeneratedLink(
                    target_path=file_target,
                    link_target=source,
                    artifact=ArtifactKind.RULE,
                    source_path=source,
                    provider=Provider.CLAUDE,
                ),
                GeneratedLink(
                    target_path=directory_target,
                    link_target=source.parent,
                    artifact=ArtifactKind.SKILL,
                    source_path=source,
                    provider=Provider.CURSOR,
                ),
            ]
        )

        apply_plan(workspace, build_plan(workspace, manifest))

        assert os.readlink(file_target) == "../../.agents/rules/sample.md"
        assert os.readlink(directory_target) == "../../.agents/rules"
        assert source.read_text() == "source\n"

    def test_stale_managed_paths_are_removed_but_unmanaged_codex_rules_remain(
        self,
        workspace: Workspace,
    ) -> None:
        """Test that stale detection respects the managed ownership boundary."""

        claude_rules = workspace.root / ".claude/rules"
        claude_rules.mkdir(parents=True)
        stale_rule = claude_rules / "orphan.md"
        stale_rule.write_text("stale\n")
        duplicate_rule = claude_rules / "orphan 2.md"
        duplicate_rule.write_text("duplicate\n")
        codex_rules = workspace.root / ".codex/rules"
        codex_rules.mkdir(parents=True)
        unmanaged = codex_rules / "custom.rules"
        unmanaged.write_text("allow_rule()\n")

        plan = build_plan(
            workspace,
            generate_manifest(workspace, load_configuration(workspace)),
        )

        assert stale_rule in plan.stale_paths
        assert duplicate_rule in plan.stale_paths
        assert unmanaged not in plan.stale_paths

    def test_removed_sources_prune_dangling_provider_links(
        self,
        workspace: Workspace,
    ) -> None:
        """Test that a removed canonical source prunes its generated links."""

        rules_dir = workspace.agents_dir / "rules"
        rules_dir.mkdir()
        source = rules_dir / "sample.md"
        source.write_text("# Sample\n")
        assert mirror_providers(workspace, dry_run=False) == 0

        source.unlink()

        assert mirror_providers(workspace, dry_run=False) == 0
        assert not (workspace.root / ".claude/rules/sample.md").is_symlink()
        assert not (workspace.root / ".cursor/rules/sample.mdc").is_symlink()

    def test_executable_mode_is_reconciled(self, workspace: Workspace) -> None:
        """Test that generated executable intent participates in comparison."""

        target = workspace.root / "script"
        target.write_text("#!/bin/sh\n")
        target.chmod(0o644)
        output = GeneratedFile(
            target_path=target,
            content="#!/bin/sh\n",
            executable=True,
            artifact=ArtifactKind.HOOK,
            source_path=workspace.agents_dir / "hooks/script",
        )
        plan = build_plan(workspace, Manifest(outputs=[output]))

        assert plan.changes
        apply_plan(workspace, plan)
        assert target.stat().st_mode & 0o111
