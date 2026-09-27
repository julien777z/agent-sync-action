import json
import tomllib

import pytest

from agent_sync.models.settings import CodexSettings
from agent_sync.reconciliation import mirror_providers
from agent_sync.models.workspace import Workspace
from agent_sync.workspace import agents_dir, output_root, settings_dir


class TestInstructions:
    """Exercise generated root guidance and its ownership boundary."""

    @pytest.mark.parametrize("output_dirname", ["", ".generated"], ids=["root", "relocated"])
    def test_orders_sources_and_keeps_scoped_bodies_in_mirrors(
        self, workspace: Workspace, output_dirname: str
    ) -> None:
        """Keep global, always-on, project, and pointers in that order."""

        workspace = workspace.model_copy(update={"output_dirname": output_dirname})
        (agents_dir(workspace) / "global.md").write_text("---\ndescription: global\n---\n\nGlobal text.\n")
        rules = agents_dir(workspace) / "rules"
        rules.mkdir()
        (rules / "always.md").write_text("---\nalwaysApply: true\n---\n\nAlways text.\n")
        (rules / "scoped.md").write_text(
            "---\ndescription: Work on Python.\nglobs: '**/*.py'\nalwaysApply: false\n---\n\nScoped text.\n"
        )
        (rules / "topic.md").write_text(
            "---\ndescription: working on deployments\nalwaysApply: false\n---\n\nTopic text.\n"
        )
        (agents_dir(workspace) / "project.md").write_text("---\ndescription: project\n---\n\nProject text.\n")
        settings_dir(workspace).mkdir()
        settings_path = settings_dir(workspace) / "codex.json"
        settings_path.write_text(json.dumps(CodexSettings(model="gpt-5").model_dump(exclude_none=True)))
        (workspace.root / "CLAUDE.md").write_text("Claude instructions.\n")

        assert mirror_providers(workspace, dry_run=False) is False
        content = (workspace.root / "AGENTS.md").read_text()
        assert content.index("Global text.") < content.index("Always text.")
        assert content.index("Always text.") < content.index("Project text.")
        assert content.index("Project text.") < content.index("## Scoped rules")
        assert "Scoped text." not in content
        assert "Topic text." not in content
        assert "Read `.agents/rules/topic.md` when its topic is relevant: working on deployments" in content
        assert (output_root(workspace) / ".claude/rules/scoped.md").is_file()
        assert not (output_root(workspace) / ".claude/rules/scoped.md").is_symlink()
        assert (output_root(workspace) / ".cursor/rules/topic.mdc").is_file()
        assert not (output_root(workspace) / ".claude/rules/always.md").exists()
        assert (workspace.root / "CLAUDE.md").read_text() == "Claude instructions.\n"
        config = tomllib.loads((output_root(workspace) / ".codex/config.toml").read_text())
        assert config["project_doc_max_bytes"] == len(content.encode("utf-8"))
        assert mirror_providers(workspace, dry_run=True) is False

    @pytest.mark.parametrize("filename", ["global.md", "project.md"])
    def test_each_root_source_works_alone(self, workspace: Workspace, filename: str) -> None:
        """Generate instructions from either optional root document."""

        (agents_dir(workspace) / filename).write_text("---\ndescription: root\n---\n\nRoot text.\n")
        assert mirror_providers(workspace, dry_run=False) is False
        assert "Root text." in (workspace.root / "AGENTS.md").read_text()

    @pytest.mark.parametrize("always_apply", [True, False], ids=["always-on", "scoped"])
    def test_rules_generate_without_root_sources(self, workspace: Workspace, always_apply: bool) -> None:
        """Create root instructions from either class of rule alone."""

        rules = agents_dir(workspace) / "rules"
        rules.mkdir()
        (rules / "sample.md").write_text(
            f"---\ndescription: Sample topic.\nalwaysApply: {str(always_apply).lower()}\n---\n\nSample body.\n"
        )
        assert mirror_providers(workspace, dry_run=False) is False
        content = (workspace.root / "AGENTS.md").read_text()
        assert ("Sample body." in content) is always_apply
        assert ("Read `.agents/rules/sample.md`" in content) is not always_apply
        assert (workspace.root / ".claude/rules/sample.md").is_file() is not always_apply

    def test_no_source_removes_only_generated_instructions(self, workspace: Workspace) -> None:
        """Remove a stale generated file while preserving user-owned guidance."""

        instructions = workspace.root / "AGENTS.md"
        (agents_dir(workspace) / "project.md").write_text("Project text.\n")
        assert mirror_providers(workspace, dry_run=False) is False
        (agents_dir(workspace) / "project.md").unlink()
        assert mirror_providers(workspace, dry_run=True) is True
        assert instructions.exists()
        assert mirror_providers(workspace, dry_run=False) is False
        assert not instructions.exists()
        instructions.write_text("User guidance.\n")
        assert mirror_providers(workspace, dry_run=False) is False
        assert instructions.read_text() == "User guidance.\n"

    def test_no_source_preserves_explicit_codex_capacity(self, workspace: Workspace) -> None:
        """Leave an explicit capacity alone when no document is generated."""

        settings_dir(workspace).mkdir()
        (settings_dir(workspace) / "codex.json").write_text('{"project_doc_max_bytes":65536}')
        assert mirror_providers(workspace, dry_run=False) is False
        config = tomllib.loads((workspace.root / ".codex/config.toml").read_text())
        assert config["project_doc_max_bytes"] == 65536
        assert not (workspace.root / "AGENTS.md").exists()

    def test_instructions_create_codex_capacity_without_settings(self, workspace: Workspace) -> None:
        """Size the generated Codex document without requiring a settings source."""

        (agents_dir(workspace) / "project.md").write_text("Project text.\n")
        assert mirror_providers(workspace, dry_run=False) is False
        instructions = (workspace.root / "AGENTS.md").read_bytes()
        config = tomllib.loads((workspace.root / ".codex/config.toml").read_text())
        assert config["project_doc_max_bytes"] == len(instructions)
        assert mirror_providers(workspace, dry_run=True) is False

    def test_removing_last_source_restores_source_codex_capacity(self, workspace: Workspace) -> None:
        """A generated capacity does not persist after its document disappears."""

        project = agents_dir(workspace) / "project.md"
        project.write_text("Project text.\n")
        settings_dir(workspace).mkdir()
        settings_path = settings_dir(workspace) / "codex.json"
        settings_path.write_text('{"project_doc_max_bytes":1234}')
        assert mirror_providers(workspace, dry_run=False) is False
        assert (
            tomllib.loads((workspace.root / ".codex/config.toml").read_text())["project_doc_max_bytes"]
            != 1234
        )
        project.unlink()
        assert mirror_providers(workspace, dry_run=False) is False
        assert (
            tomllib.loads((workspace.root / ".codex/config.toml").read_text())["project_doc_max_bytes"]
            == 1234
        )
        assert settings_path.read_text() == '{"project_doc_max_bytes":1234}'

    def test_configured_source_directory_appears_in_pointers(self, workspace: Workspace) -> None:
        """Point Codex at the actual canonical rule path."""

        workspace = workspace.model_copy(update={"agents_dirname": "guidance"})
        rules = agents_dir(workspace) / "rules"
        rules.mkdir(parents=True)
        (rules / "sample.md").write_text(
            "---\ndescription: Sample topic.\nalwaysApply: false\n---\n\nSample body.\n"
        )
        assert mirror_providers(workspace, dry_run=False) is False
        content = (workspace.root / "AGENTS.md").read_text()
        assert "Canonical guidance lives in `guidance/`." in content
        assert "Read `guidance/rules/sample.md`" in content

    def test_omitted_rule_scope_defaults_to_always_on(self, workspace: Workspace) -> None:
        """Keep the production front-matter default visible in a generation test."""

        rules = agents_dir(workspace) / "rules"
        rules.mkdir()
        (rules / "sample.md").write_text("# Sample body\n")
        assert mirror_providers(workspace, dry_run=False) is False
        content = (workspace.root / "AGENTS.md").read_text()
        assert "# Sample body" in content
        assert "Read `.agents/rules/sample.md`" not in content
        assert not (workspace.root / ".claude/rules/sample.md").exists()
