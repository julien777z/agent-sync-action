import os

import pytest
from pydantic import ValidationError

from agent_sync.generation.registry import generate_manifest, owned_provider_directories
from agent_sync.models.output import (
    ArtifactKind,
    GeneratedFile,
    GeneratedLink,
    Manifest,
    Provider,
)
from agent_sync.providers import PROVIDER_LAYOUTS
from agent_sync.reconciliation import apply_plan, build_plan, mirror_providers
from agent_sync.source import load_source_config
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

    def test_stale_provider_paths_are_removed(
        self,
        workspace: Workspace,
    ) -> None:
        """Test that stale detection makes provider directories match the manifest."""

        claude_rules = workspace.root / ".claude/rules"
        claude_rules.mkdir(parents=True)
        stale_rule = claude_rules / "orphan.md"
        stale_rule.write_text("stale\n")

        stale_directory = claude_rules / "custom"
        stale_directory.mkdir()
        (stale_directory / "rule.md").write_text("stale\n")

        duplicate_rule = claude_rules / "orphan 2.md"
        duplicate_rule.write_text("duplicate\n")

        codex_rules = workspace.root / ".codex/rules"
        codex_rules.mkdir(parents=True)
        stale_codex_rule = codex_rules / "custom.rules"
        stale_codex_rule.write_text("allow_rule()\n")

        plan = build_plan(
            workspace,
            generate_manifest(workspace, load_source_config(workspace)),
        )

        assert stale_rule in plan.stale_paths
        assert stale_directory in plan.stale_paths
        assert duplicate_rule in plan.stale_paths
        assert stale_codex_rule in plan.stale_paths

    @pytest.mark.parametrize(
        ("provider", "directory_name"),
        owned_provider_directories(),
    )
    def test_registry_directories_are_fully_owned(
        self,
        workspace: Workspace,
        provider: Provider,
        directory_name: str,
    ) -> None:
        """Test that every registry-owned directory removes unknown entries."""

        directory = PROVIDER_LAYOUTS[provider].root(workspace.root) / directory_name
        directory.mkdir(parents=True)
        stale_path = directory / "unregistered"
        stale_path.write_text("stale\n")

        plan = build_plan(
            workspace,
            generate_manifest(workspace, load_source_config(workspace)),
        )

        assert stale_path in plan.stale_paths

    def test_settings_without_sources_are_removed(self, workspace: Workspace) -> None:
        """Test that provider settings cannot outlive their source configuration."""

        stale_settings = [
            workspace.root / ".claude/settings.json",
            workspace.root / ".codex/config.toml",
        ]
        for path in stale_settings:
            path.parent.mkdir(exist_ok=True)
            path.write_text("stale\n")

        plan = build_plan(
            workspace,
            generate_manifest(workspace, load_source_config(workspace)),
        )

        assert set(stale_settings) <= set(plan.stale_paths)

    def test_removed_sources_prune_dangling_provider_links(
        self,
        workspace: Workspace,
    ) -> None:
        """Test that a removed canonical source prunes its generated links."""

        rules_dir = workspace.agents_dir / "rules"
        rules_dir.mkdir()
        source = rules_dir / "sample.md"
        source.write_text("# Sample\n")

        assert mirror_providers(workspace, dry_run=False) is False

        source.unlink()

        assert mirror_providers(workspace, dry_run=False) is False
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
