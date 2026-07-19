import json
import os
import tomllib

import pytest

from agent_sync.errors import AgentSyncError
from agent_sync.generation.artifact import generate_agents, generate_hooks, generate_skills
from agent_sync.generation.context import GenerationContext, load_generation_context
from agent_sync.generation.registry import ARTIFACT_REGISTRY
from agent_sync.generation.rule import (
    generate_codex_rules,
    generate_rule_links,
    generate_shared_rule_outputs,
)
from agent_sync.generation.setting import generate_claude_settings
from agent_sync.models.output import ArtifactKind, GeneratedFile, GeneratedLink, Provider
from agent_sync.reconciliation import mirror_providers
from agent_sync.source import load_source_config
from agent_sync.workspace import Workspace
from tests.factories import (
    RuleFrontMatterFactory,
    SkillFrontMatterFactory,
    materialize_rule,
    materialize_skill,
)


def load_context(workspace: Workspace) -> GenerationContext:
    """Load generation inputs from one test workspace."""

    return load_generation_context(workspace, load_source_config(workspace))


class TestArtifactRegistry:
    """Test that the provider support matrix is explicit."""

    def test_declares_supported_provider_artifacts(self) -> None:
        """Test that the registry contains the stable provider support matrix."""

        assert {
            artifact: set(registration["handlers"])
            for artifact, registration in ARTIFACT_REGISTRY.items()
        } == {
            ArtifactKind.SKILL: {Provider.CLAUDE, Provider.CURSOR, Provider.CODEX},
            ArtifactKind.AGENT: {Provider.CLAUDE, Provider.CURSOR},
            ArtifactKind.RULE: {Provider.CLAUDE, Provider.CURSOR, Provider.CODEX},
            ArtifactKind.HOOK: {Provider.CLAUDE, Provider.CURSOR},
            ArtifactKind.SETTING: {Provider.CLAUDE, Provider.CODEX},
        }


class TestSkillGeneration:
    """Test that canonical skills become provider directory links."""

    def test_links_every_provider_to_the_canonical_directory(
        self,
        workspace: Workspace,
    ) -> None:
        """Test that all provider skill paths link to one canonical directory."""

        front_matter = SkillFrontMatterFactory.build()
        source = workspace.agents_dir / "skills" / front_matter.name / "SKILL.md"
        materialize_skill(source, front_matter)
        context = load_context(workspace)
        outputs = [output for provider in Provider for output in generate_skills(context, provider)]
        links = {
            output.target_path: output.link_target
            for output in outputs
            if isinstance(output, GeneratedLink)
        }

        assert links == {
            workspace.root / ".claude/skills/sample-skill": source.parent,
            workspace.root / ".cursor/skills/sample-skill": source.parent,
            workspace.root / ".codex/skills/sample-skill": source.parent,
        }

    @pytest.mark.parametrize(
        "front_matter",
        [
            "description: Does a thing.",
            "name: sample-skill",
            "name: another-skill\ndescription: Does a thing.",
            "name: sample-skill\ndescription: '   '",
        ],
        ids=["missing-name", "missing-description", "mismatched-name", "blank-description"],
    )
    def test_rejects_invalid_metadata(
        self,
        workspace: Workspace,
        front_matter: str,
    ) -> None:
        """Test that incomplete or misaligned skill metadata fails generation."""

        skill_dir = workspace.agents_dir / "skills/sample-skill"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(
            f"---\n{front_matter}\n---\n\n# Sample Skill\n",
            encoding="utf-8",
        )

        with pytest.raises(AgentSyncError):
            load_context(workspace)

    def test_rejects_skill_directories_without_skill_documents(
        self,
        workspace: Workspace,
    ) -> None:
        """Test that every canonical skill directory contains its required document."""

        (workspace.agents_dir / "skills/sample-skill").mkdir(parents=True)

        with pytest.raises(AgentSyncError, match="Missing SKILL.md"):
            load_context(workspace)


class TestDocumentGeneration:
    """Test that agents, rules, and hooks use their artifact formats."""

    def test_agent_model_override_precedes_provider_default(
        self,
        workspace: Workspace,
    ) -> None:
        """Test that agent-specific models override provider-wide settings."""

        agents_dir = workspace.agents_dir / "agents"
        agents_dir.mkdir()
        (agents_dir / "review.md").write_text("---\nname: review\n---\n\nReview.\n")
        workspace.settings_dir.mkdir()
        (workspace.settings_dir / "claude.json").write_text('{"model":"default"}')
        workspace.models_dir.mkdir()
        (workspace.models_dir / "review.json").write_text(
            '{"claude":"override","cursor":"cursor-model"}'
        )

        context = load_context(workspace)
        outputs = [
            *generate_agents(context, Provider.CLAUDE),
            *generate_agents(context, Provider.CURSOR),
        ]
        files = {
            output.provider: output.content
            for output in outputs
            if isinstance(output, GeneratedFile)
        }

        assert "model: override" in files[Provider.CLAUDE]
        assert "model: cursor-model" in files[Provider.CURSOR]

    def test_rules_normalize_sources_and_generate_links(
        self,
        workspace: Workspace,
    ) -> None:
        """Test that one normalized rule owns both provider links."""

        source = workspace.agents_dir / "rules/python.md"
        materialize_rule(source, RuleFrontMatterFactory.build(name="removed"))
        context = load_context(workspace)
        outputs = [
            *generate_shared_rule_outputs(context),
            *generate_rule_links(context, Provider.CLAUDE),
            *generate_rule_links(context, Provider.CURSOR),
        ]
        source_output = next(
            output
            for output in outputs
            if isinstance(output, GeneratedFile) and output.target_path == source
        )

        links = [output for output in outputs if isinstance(output, GeneratedLink)]

        assert source_output.content.startswith(
            "---\ndescription: A rule.\nalwaysApply: true\n---\n"
        )
        assert "name:" not in source_output.content
        assert {link.link_target for link in links} == {source}
        assert {link.target_path.suffix for link in links} == {".md", ".mdc"}

    def test_codex_rules_render_starlark_without_markdown_body(
        self,
        workspace: Workspace,
    ) -> None:
        """Test that a Starlark-only rule still generates its Codex output."""

        rules_dir = workspace.agents_dir / "rules"
        rules_dir.mkdir()
        source = rules_dir / "git.md"
        source.write_text(
            '---\nstarlark: |\n  allow_rule(prefix_rule = ["git", "status"])\n' "---\n"
        )

        context = load_context(workspace)
        outputs = generate_codex_rules(context, Provider.CODEX)

        assert len(outputs) == 1
        assert isinstance(outputs[0], GeneratedFile)
        assert outputs[0].target_path == workspace.root / ".codex/rules/git.rules"
        assert 'allow_rule(prefix_rule = ["git", "status"])' in outputs[0].content
        shared_outputs = generate_shared_rule_outputs(context)

        assert len(shared_outputs) == 1
        assert shared_outputs[0].artifact is ArtifactKind.INSTRUCTIONS
        assert not generate_rule_links(context, Provider.CLAUDE)
        assert not generate_rule_links(context, Provider.CURSOR)

    def test_hooks_preserve_executable_intent(self, workspace: Workspace) -> None:
        """Test that shell and shebang hooks are marked executable."""

        hooks_dir = workspace.agents_dir / "hooks"
        hooks_dir.mkdir()
        (hooks_dir / "check").write_text("#!/usr/bin/env python3\nprint('ok')\n")

        context = load_context(workspace)
        outputs = [
            *generate_hooks(context, Provider.CLAUDE),
            *generate_hooks(context, Provider.CURSOR),
        ]

        assert outputs
        assert all(isinstance(output, GeneratedFile) and output.executable for output in outputs)


class TestSettingsGeneration:
    """Test that synchronized settings fully own generated provider files."""

    def test_claude_settings_render_complete_json(self, workspace: Workspace) -> None:
        """Test that Claude settings preserve validated provider keys."""

        workspace.settings_dir.mkdir()
        (workspace.settings_dir / "claude.json").write_text(
            '{"model":"sonnet","permissions":{"allow":["Read"]}}'
        )

        outputs = generate_claude_settings(load_context(workspace), Provider.CLAUDE)

        assert len(outputs) == 1
        assert isinstance(outputs[0], GeneratedFile)
        assert json.loads(outputs[0].content) == {
            "model": "sonnet",
            "permissions": {"allow": ["Read"]},
        }

    def test_codex_capacity_overwrites_existing_toml(
        self,
        workspace: Workspace,
    ) -> None:
        """Test that generated instructions determine Codex document capacity."""

        materialize_rule(
            workspace.agents_dir / "rules/project.md",
            RuleFrontMatterFactory.build(name="removed"),
            body="# Project Rules\n\nKeep changes focused.",
        )

        workspace.settings_dir.mkdir(parents=True)
        settings_path = workspace.settings_dir / "codex.json"
        settings_path.write_text('{"model":"gpt-5","project_doc_max_bytes":1}')

        config_path = workspace.root / ".codex/config.toml"
        config_path.parent.mkdir()
        config_path.write_text('model_reasoning_effort = "high"\n')

        assert mirror_providers(workspace, dry_run=False) is False

        instructions = (workspace.root / "AGENTS.md").read_text()
        capacity = len(instructions.encode("utf-8"))
        canonical = json.loads(settings_path.read_text())
        native = tomllib.loads(config_path.read_text())

        assert canonical["project_doc_max_bytes"] == capacity
        assert native["project_doc_max_bytes"] == capacity
        assert "model_reasoning_effort" not in native
        assert mirror_providers(workspace, dry_run=True) is False

    def test_invalid_existing_toml_is_overwritten(self, workspace: Workspace) -> None:
        """Test that existing Codex content never affects generated settings."""

        workspace.settings_dir.mkdir()
        (workspace.settings_dir / "codex.json").write_text('{"project_doc_max_bytes":1}')

        config_path = workspace.root / ".codex/config.toml"
        config_path.parent.mkdir()
        config_path.write_text("invalid = [\n")

        assert mirror_providers(workspace, dry_run=False) is False
        assert tomllib.loads(config_path.read_text())["project_doc_max_bytes"] > 0


class TestMirrorIntegration:
    """Test that complete mirroring converges on committed relative links."""

    def test_fresh_mirror_is_idempotent(
        self,
        workspace: Workspace,
    ) -> None:
        """Test that mirroring writes relative links and reaches a clean dry run."""

        materialize_rule(
            workspace.agents_dir / "rules/python.md",
            RuleFrontMatterFactory.build(name="removed"),
        )

        skill_front_matter = SkillFrontMatterFactory.build(name="review")
        materialize_skill(
            workspace.agents_dir / "skills/review/SKILL.md",
            skill_front_matter,
        )

        assert mirror_providers(workspace, dry_run=False) is False

        assert os.readlink(workspace.root / ".claude/rules/python.md") == (
            "../../.agents/rules/python.md"
        )
        assert os.readlink(workspace.root / ".codex/skills/review") == (
            "../../.agents/skills/review"
        )
        assert mirror_providers(workspace, dry_run=True) is False
