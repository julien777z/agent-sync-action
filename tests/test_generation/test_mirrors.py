import os
import json

import pytest

from agent_sync.reconciliation import mirror_providers
from agent_sync.models.settings import Workspace
from agent_sync.models.output import Provider
from agent_sync.utils import AgentSyncError
from agent_sync.workspace import agents_dir, output_root, settings_dir
from tests.factories import (
    RuleFrontMatterFactory,
    SkillFrontMatterFactory,
    HooksConfigFactory,
    materialize_hooks,
    materialize_rule,
    materialize_skill,
)


class TestMirrorIntegration:
    """Test that complete mirroring converges on provider outputs."""

    @pytest.mark.parametrize("output_dirname", ["", ".generated"], ids=["root", "relocated"])
    async def test_shared_hook_lifecycle(self, workspace: Workspace, output_dirname: str) -> None:
        """Test that hook registration and nested resources converge and are removed with their sources."""

        workspace = Workspace(root=workspace.root, output_dirname=output_dirname)
        config = HooksConfigFactory.build()
        materialize_hooks(workspace, config)
        canonical = agents_dir(workspace) / "hooks/hooks.json"
        original = canonical.read_bytes()
        generated = output_root(workspace)

        assert mirror_providers(workspace, dry_run=True) is True
        assert not (generated / ".codex").exists()
        assert mirror_providers(workspace, dry_run=False) is False

        expected = config.model_dump(by_alias=True, exclude_none=True)["hooks"]
        codex = json.loads((generated / ".codex/hooks.json").read_text())
        claude = json.loads((generated / ".claude/settings.json").read_text())

        assert codex["hooks"] == claude["hooks"] == expected
        assert config.description in codex["description"]
        assert not (generated / ".cursor/hooks/hooks.json").exists()
        assert not (generated / ".claude/hooks/hooks.json").exists()
        assert not (generated / ".codex/hooks/hooks.json").exists()

        for provider in Provider:
            target = provider.root(generated) / "hooks/session/start.py"
            support = provider.root(generated) / "hooks/session/resources/context.md"

            assert target.read_bytes() == (canonical.parent / "session/start.py").read_bytes()
            assert target.stat().st_mode & 0o111
            assert support.read_bytes() == (canonical.parent / "session/resources/context.md").read_bytes()
            assert not support.stat().st_mode & 0o111

        assert canonical.read_bytes() == original
        assert mirror_providers(workspace, dry_run=True) is False

        canonical.unlink()
        (canonical.parent / "session/start.py").unlink()
        (canonical.parent / "session/resources/context.md").unlink()

        assert mirror_providers(workspace, dry_run=True) is True
        assert mirror_providers(workspace, dry_run=False) is False
        assert not (generated / ".codex/hooks.json").exists()
        assert not (generated / ".claude/settings.json").exists()
        assert all(not (provider.root(generated) / "hooks/session").exists() for provider in Provider)
        assert mirror_providers(workspace, dry_run=True) is False

    @pytest.mark.parametrize(
        "document",
        [
            "{invalid",
            '{"hooks":{"UnknownEvent":[]}}',
            '{"hooks":{"Stop":[{"hooks":[{"type":"prompt","prompt":"Check"}]}]}}',
            '{"hooks":{"Stop":[{"hooks":[{"type":"command"}]}]}}',
            '{"hooks":{"Stop":[{"hooks":[{"type":"command","command":"check","timeout":0}]}]}}',
            '{"hooks":{"Stop":[{"hooks":[{"type":"command","command":"check","extra":true}]}]}}',
            '{"hooks":{"Stop":[{"hooks":[]}]}}',
        ],
        ids=[
            "malformed",
            "unknown-event",
            "unsupported-handler",
            "missing-command",
            "timeout",
            "extra",
            "empty",
        ],
    )
    async def test_invalid_hooks_preserve_outputs(self, workspace: Workspace, document: str) -> None:
        """Test that invalid shared definitions fail before changing existing generated outputs."""

        materialize_hooks(workspace, HooksConfigFactory.build())
        mirror_providers(workspace, dry_run=False)
        target = workspace.root / ".codex/hooks.json"
        original = target.read_bytes()
        canonical = agents_dir(workspace) / "hooks/hooks.json"
        canonical.write_text(document)

        with pytest.raises(AgentSyncError, match="Invalid JSON|Invalid source"):
            mirror_providers(workspace, dry_run=False)

        assert target.read_bytes() == original

    @pytest.mark.parametrize("kind", ["file", "directory", "registration", "root"])
    async def test_hook_symlinks_fail(self, workspace: Workspace, kind: str) -> None:
        """Test that hook source links cannot read or traverse other trees."""

        materialize_hooks(workspace, HooksConfigFactory.build())
        hooks = agents_dir(workspace) / "hooks"

        if kind == "root":
            target = hooks.with_name("hook-sources")
            hooks.rename(target)
            hooks.symlink_to(target, target_is_directory=True)
        elif kind == "registration":
            target = hooks / "registration.json"
            (hooks / "hooks.json").rename(target)
            (hooks / "hooks.json").symlink_to(target)
        else:
            target = hooks / ("session" if kind == "directory" else "session/start.py")
            (hooks / "linked").symlink_to(target, target_is_directory=kind == "directory")

        with pytest.raises(AgentSyncError, match="not symlinks"):
            mirror_providers(workspace, dry_run=False)

        assert not (workspace.root / ".codex").exists()

    def test_fresh_mirror_is_idempotent(
        self,
        workspace: Workspace,
    ) -> None:
        """Test that mirroring writes rules and skill links, then reaches a clean dry run."""

        materialize_rule(
            agents_dir(workspace) / "rules/python.md",
            RuleFrontMatterFactory.build(name="removed", always_apply=False),
        )

        skill_front_matter = SkillFrontMatterFactory.build(name="review")
        materialize_skill(
            agents_dir(workspace) / "skills/review/SKILL.md",
            skill_front_matter,
        )

        assert mirror_providers(workspace, dry_run=False) is False

        assert (workspace.root / ".claude/rules/python.md").is_symlink()
        assert (workspace.root / ".cursor/rules/python.mdc").is_symlink()
        assert os.readlink(workspace.root / ".codex/skills/review") == ("../../.agents/skills/review")
        assert mirror_providers(workspace, dry_run=True) is False

    def test_mirroring_preserves_canonical_rule_format(self, workspace: Workspace) -> None:
        """Leave repository formatting in the source while adding only the missing scope."""

        source = agents_dir(workspace) / "rules/python.md"
        source.parent.mkdir()
        original = (
            '---\ndescription: "Python guidance"\nalwaysApply: false\nglobs:\n'
            '    - "**/*.py"\n---\n\n# Python\n\nUse typed values.\n'
        )
        source.write_text(original)

        assert mirror_providers(workspace, dry_run=False) is False
        assert source.read_text() == original
        claude = workspace.root / ".claude/rules/python.md"
        cursor = workspace.root / ".cursor/rules/python.mdc"
        assert claude.is_file() and not claude.is_symlink()
        assert "paths:\n- '**/*.py'" in claude.read_text()
        assert "globs:" not in claude.read_text()
        assert "Use typed values." in claude.read_text()
        assert cursor.is_symlink()
        assert cursor.resolve() == source
        assert mirror_providers(workspace, dry_run=True) is False

    def test_existing_files_become_links_when_both_scopes_are_authored(self, workspace: Workspace) -> None:
        """Test that adding the second scope replaces a generated file with a link."""

        source = agents_dir(workspace) / "rules/python.md"
        source.parent.mkdir()
        source.write_text('---\nglobs: "**/*.py"\nalwaysApply: false\n---\n\n# Rule\n')
        assert mirror_providers(workspace, dry_run=False) is False
        claude = workspace.root / ".claude/rules/python.md"
        assert claude.is_file() and not claude.is_symlink()

        source.write_text('---\nglobs: "**/*.py"\npaths: "**/*.py"\nalwaysApply: false\n---\n\n# Rule\n')
        original = source.read_bytes()
        assert mirror_providers(workspace, dry_run=False) is False
        assert claude.is_symlink() and claude.resolve() == source
        assert (workspace.root / ".cursor/rules/python.mdc").is_symlink()
        assert source.read_bytes() == original
        assert mirror_providers(workspace, dry_run=True) is False

    def test_output_directory_holds_every_generated_provider_tree(
        self,
        relocated_workspace: Workspace,
    ) -> None:
        """Test that a configured output directory receives every provider artifact."""

        materialize_skill(
            agents_dir(relocated_workspace) / "skills/review/SKILL.md",
            SkillFrontMatterFactory.build(name="review"),
        )
        materialize_rule(
            agents_dir(relocated_workspace) / "rules/python.md",
            RuleFrontMatterFactory.build(name="removed", always_apply=False),
        )
        materialize_rule(
            agents_dir(relocated_workspace) / "rules/typescript.md",
            RuleFrontMatterFactory.build(name="removed", starlark="allow_rule()"),
        )

        agent_sources = agents_dir(relocated_workspace) / "agents"
        agent_sources.mkdir()
        (agent_sources / "review.md").write_text("---\nname: review\n---\n\nReview.\n")

        hooks_dir = agents_dir(relocated_workspace) / "hooks"
        hooks_dir.mkdir()
        (hooks_dir / "check").write_text("#!/usr/bin/env python3\nprint('ok')\n")

        settings_dir(relocated_workspace).mkdir()
        (settings_dir(relocated_workspace) / "claude.json").write_text('{"model":"default"}')
        (settings_dir(relocated_workspace) / "codex.json").write_text(
            '{"model":"gpt-5","project_doc_max_bytes":1}'
        )

        assert mirror_providers(relocated_workspace, dry_run=False) is False

        generated_root = output_root(relocated_workspace)

        assert (generated_root / ".claude/skills/review").is_symlink()
        assert (generated_root / ".claude/rules/python.md").is_symlink()
        assert (generated_root / ".claude/rules/python.md").resolve() == (
            agents_dir(relocated_workspace) / "rules/python.md"
        )
        assert (generated_root / ".codex/rules/typescript.rules").is_file()
        assert (generated_root / ".claude/agents/review.md").is_file()
        assert (generated_root / ".claude/hooks/check").is_file()
        assert (generated_root / ".claude/settings.json").is_file()
        assert (generated_root / ".codex/config.toml").is_file()
        assert (relocated_workspace.root / "AGENTS.md").is_file()
        assert not (relocated_workspace.root / ".claude").exists()
        assert mirror_providers(relocated_workspace, dry_run=True) is False

    def test_explicit_skill_remains_a_canonical_link(self, workspace: Workspace) -> None:
        source = agents_dir(workspace) / "skills/review/SKILL.md"
        front_matter = SkillFrontMatterFactory.build(name="review", disable_model_invocation=True)
        materialize_skill(source, front_matter)

        assert mirror_providers(workspace, dry_run=False) is False
        for provider in (".claude", ".codex", ".cursor"):
            skill = workspace.root / provider / "skills/review"
            assert skill.is_symlink()
            assert "disable-model-invocation: true" in (skill / "SKILL.md").read_text()
        assert mirror_providers(workspace, dry_run=True) is False
