import os


from agent_sync.reconciliation import mirror_providers
from agent_sync.workspace import Workspace
from tests.factories import (
    RuleFrontMatterFactory,
    SkillFrontMatterFactory,
    materialize_rule,
    materialize_skill,
)


class TestMirrorIntegration:
    """Test that complete mirroring converges on provider outputs."""

    def test_fresh_mirror_is_idempotent(
        self,
        workspace: Workspace,
    ) -> None:
        """Test that mirroring writes rules and skill links, then reaches a clean dry run."""

        materialize_rule(
            workspace.agents_dir / "rules/python.md",
            RuleFrontMatterFactory.build(name="removed", always_apply=False),
        )

        skill_front_matter = SkillFrontMatterFactory.build(name="review")
        materialize_skill(
            workspace.agents_dir / "skills/review/SKILL.md",
            skill_front_matter,
        )

        assert mirror_providers(workspace, dry_run=False) is False

        assert (workspace.root / ".claude/rules/python.md").is_symlink()
        assert (workspace.root / ".cursor/rules/python.mdc").is_symlink()
        assert os.readlink(workspace.root / ".codex/skills/review") == ("../../.agents/skills/review")
        assert mirror_providers(workspace, dry_run=True) is False

    def test_mirroring_preserves_canonical_rule_format(self, workspace: Workspace) -> None:
        """Leave repository formatting in the source while adding only the missing scope."""

        source = workspace.agents_dir / "rules/python.md"
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
        assert "globs:\n- '**/*.py'" in claude.read_text()
        assert "paths:\n- '**/*.py'" in claude.read_text()
        assert "Use typed values." in claude.read_text()
        assert cursor.is_symlink()
        assert cursor.resolve() == source
        assert mirror_providers(workspace, dry_run=True) is False

    def test_existing_files_become_links_when_both_scopes_are_authored(self, workspace: Workspace) -> None:
        """Test that adding the second scope replaces a generated file with a link."""

        source = workspace.agents_dir / "rules/python.md"
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
            relocated_workspace.agents_dir / "skills/review/SKILL.md",
            SkillFrontMatterFactory.build(name="review"),
        )
        materialize_rule(
            relocated_workspace.agents_dir / "rules/python.md",
            RuleFrontMatterFactory.build(name="removed", always_apply=False),
        )
        materialize_rule(
            relocated_workspace.agents_dir / "rules/typescript.md",
            RuleFrontMatterFactory.build(name="removed", starlark="allow_rule()"),
        )

        agents_dir = relocated_workspace.agents_dir / "agents"
        agents_dir.mkdir()
        (agents_dir / "review.md").write_text("---\nname: review\n---\n\nReview.\n")

        hooks_dir = relocated_workspace.agents_dir / "hooks"
        hooks_dir.mkdir()
        (hooks_dir / "check").write_text("#!/usr/bin/env python3\nprint('ok')\n")

        relocated_workspace.settings_dir.mkdir()
        (relocated_workspace.settings_dir / "claude.json").write_text('{"model":"default"}')
        (relocated_workspace.settings_dir / "codex.json").write_text(
            '{"model":"gpt-5","project_doc_max_bytes":1}'
        )

        assert mirror_providers(relocated_workspace, dry_run=False) is False

        output_root = relocated_workspace.output_root

        assert (output_root / ".claude/skills/review").is_symlink()
        assert (output_root / ".claude/rules/python.md").is_symlink()
        assert (output_root / ".claude/rules/python.md").resolve() == (
            relocated_workspace.agents_dir / "rules/python.md"
        )
        assert (output_root / ".codex/rules/typescript.rules").is_file()
        assert (output_root / ".claude/agents/review.md").is_file()
        assert (output_root / ".claude/hooks/check").is_file()
        assert (output_root / ".claude/settings.json").is_file()
        assert (output_root / ".codex/config.toml").is_file()
        assert (relocated_workspace.root / "AGENTS.md").is_file()
        assert not (relocated_workspace.root / ".claude").exists()
        assert mirror_providers(relocated_workspace, dry_run=True) is False

    def test_explicit_skill_remains_a_canonical_link(self, workspace: Workspace) -> None:
        source = workspace.agents_dir / "skills/review/SKILL.md"
        front_matter = SkillFrontMatterFactory.build(name="review", disable_model_invocation=True)
        materialize_skill(source, front_matter)

        assert mirror_providers(workspace, dry_run=False) is False
        for provider in (".claude", ".codex", ".cursor"):
            skill = workspace.root / provider / "skills/review"
            assert skill.is_symlink()
            assert "disable-model-invocation: true" in (skill / "SKILL.md").read_text()
        assert mirror_providers(workspace, dry_run=True) is False
