import json
import os
from pathlib import Path
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
from agent_sync.models.providers import ExplicitSkillInvocationPolicy, ProviderLayout
from agent_sync.providers import PROVIDER_LAYOUTS
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
            artifact: set(registration["handlers"]) for artifact, registration in ARTIFACT_REGISTRY.items()
        } == {
            ArtifactKind.SKILL: {Provider.CLAUDE, Provider.CURSOR, Provider.CODEX},
            ArtifactKind.AGENT: {Provider.CLAUDE, Provider.CURSOR},
            ArtifactKind.RULE: {Provider.CLAUDE, Provider.CURSOR, Provider.CODEX},
            ArtifactKind.HOOK: {Provider.CLAUDE, Provider.CURSOR},
            ArtifactKind.SETTING: {Provider.CLAUDE, Provider.CODEX},
        }


class TestSkillGeneration:
    """Test that canonical skills become provider directory links."""

    @pytest.mark.parametrize(
        "relative_path",
        [Path("../openai.yaml"), Path("agents/../../openai.yaml")],
        ids=["parent", "nested-parent"],
    )
    def test_rejects_metadata_path_traversal(self, relative_path: Path) -> None:
        """Test that generated metadata remains within a skill directory."""

        with pytest.raises(ValueError, match="nested relative path"):
            ExplicitSkillInvocationPolicy(relative_path=relative_path, content="policy: {}\n")

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
            output.target_path: output.link_target for output in outputs if isinstance(output, GeneratedLink)
        }

        assert links == {
            workspace.root / ".claude/skills/sample-skill": source.parent,
            workspace.root / ".cursor/skills/sample-skill": source.parent,
            workspace.root / ".codex/skills/sample-skill": source.parent,
        }

    def test_codex_generates_explicit_invocation_policy(
        self,
        workspace: Workspace,
    ) -> None:
        """Test that explicit-only skills receive Codex's native policy."""

        front_matter = SkillFrontMatterFactory.build(disable_model_invocation=True)
        source = workspace.agents_dir / "skills" / front_matter.name / "SKILL.md"
        materialize_skill(source, front_matter)
        references = source.parent / "references"
        references.mkdir()
        reference = references / "provider.md"
        reference.write_text("Provider guidance.\n")

        context = load_context(workspace)
        outputs = generate_skills(context, Provider.CODEX)
        links = {
            output.target_path: output.link_target for output in outputs if isinstance(output, GeneratedLink)
        }
        policy = next(output for output in outputs if isinstance(output, GeneratedFile))
        skill_root = workspace.root / ".codex/skills/sample-skill"

        assert links == {
            skill_root / "SKILL.md": source,
            skill_root / "references": references,
        }
        assert policy.target_path == skill_root / "agents/openai.yaml"
        assert policy.content == "policy:\n  allow_implicit_invocation: false\n"

    def test_rejects_canonical_codex_metadata(self, workspace: Workspace) -> None:
        """Test that provider metadata cannot be stored in canonical skills."""

        front_matter = SkillFrontMatterFactory.build(disable_model_invocation=True)
        source = workspace.agents_dir / "skills" / front_matter.name / "SKILL.md"
        materialize_skill(source, front_matter)
        metadata = source.parent / "agents/openai.yaml"
        metadata.parent.mkdir()
        metadata.write_text("policy: {}\n")

        context = load_context(workspace)

        with pytest.raises(AgentSyncError, match="Generated skill metadata is derived"):
            generate_skills(context, Provider.CODEX)

    def test_rejects_metadata_directory_file_collision(self, workspace: Workspace) -> None:
        """Test that generated metadata cannot replace a canonical file."""

        front_matter = SkillFrontMatterFactory.build(disable_model_invocation=True)
        source = workspace.agents_dir / "skills" / front_matter.name / "SKILL.md"
        materialize_skill(source, front_matter)
        metadata_directory = source.parent / "agents"
        metadata_directory.write_text("Canonical asset.\n")

        context = load_context(workspace)

        with pytest.raises(AgentSyncError, match="requires a directory"):
            generate_skills(context, Provider.CODEX)

    def test_rejects_broken_canonical_codex_metadata(self, workspace: Workspace) -> None:
        """Test that generated metadata cannot replace a dangling symlink."""

        front_matter = SkillFrontMatterFactory.build(disable_model_invocation=True)
        source = workspace.agents_dir / "skills" / front_matter.name / "SKILL.md"
        materialize_skill(source, front_matter)
        metadata = source.parent / "agents/openai.yaml"
        metadata.parent.mkdir()
        metadata.symlink_to("missing-openai.yaml")

        context = load_context(workspace)

        with pytest.raises(AgentSyncError, match="Generated skill metadata is derived"):
            generate_skills(context, Provider.CODEX)

    def test_rejects_nested_metadata_ancestor_collision(
        self,
        monkeypatch: pytest.MonkeyPatch,
        workspace: Workspace,
    ) -> None:
        """Test that generated metadata cannot replace a nested canonical file."""

        front_matter = SkillFrontMatterFactory.build(disable_model_invocation=True)
        source = workspace.agents_dir / "skills" / front_matter.name / "SKILL.md"
        materialize_skill(source, front_matter)
        (source.parent / "agents").write_text("Canonical asset.\n")
        monkeypatch.setitem(
            PROVIDER_LAYOUTS,
            Provider.CODEX,
            ProviderLayout(
                directory=".codex",
                rule_extension=".rules",
                explicit_skill_invocation_policy=ExplicitSkillInvocationPolicy(
                    relative_path=Path("agents/native/openai.yaml"),
                    content="policy: {}\n",
                ),
            ),
        )

        context = load_context(workspace)

        with pytest.raises(AgentSyncError, match="requires a directory"):
            generate_skills(context, Provider.CODEX)

    def test_preserves_nested_metadata_ancestor_assets(
        self,
        monkeypatch: pytest.MonkeyPatch,
        workspace: Workspace,
    ) -> None:
        """Test that nested metadata generation preserves canonical siblings."""

        front_matter = SkillFrontMatterFactory.build(disable_model_invocation=True)
        source = workspace.agents_dir / "skills" / front_matter.name / "SKILL.md"
        materialize_skill(source, front_matter)
        agents_directory = source.parent / "agents"
        agents_directory.mkdir()
        agents_asset = agents_directory / "guide.md"
        agents_asset.write_text("Guide.\n")
        native_directory = agents_directory / "native"
        native_directory.mkdir()
        native_asset = native_directory / "settings.md"
        native_asset.write_text("Settings.\n")
        monkeypatch.setitem(
            PROVIDER_LAYOUTS,
            Provider.CODEX,
            ProviderLayout(
                directory=".codex",
                rule_extension=".rules",
                explicit_skill_invocation_policy=ExplicitSkillInvocationPolicy(
                    relative_path=Path("agents/native/openai.yaml"),
                    content="policy: {}\n",
                ),
            ),
        )

        outputs = generate_skills(load_context(workspace), Provider.CODEX)
        links = {
            output.target_path: output.link_target for output in outputs if isinstance(output, GeneratedLink)
        }
        policy = next(output for output in outputs if isinstance(output, GeneratedFile))
        skill_root = workspace.root / ".codex/skills/sample-skill"

        assert links == {
            skill_root / "SKILL.md": source,
            skill_root / "agents/guide.md": agents_asset,
            skill_root / "agents/native/settings.md": native_asset,
        }
        assert policy.target_path == skill_root / "agents/native/openai.yaml"

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
        (workspace.models_dir / "review.json").write_text('{"claude":"override","cursor":"cursor-model"}')

        context = load_context(workspace)
        outputs = [
            *generate_agents(context, Provider.CLAUDE),
            *generate_agents(context, Provider.CURSOR),
        ]
        files = {output.provider: output.content for output in outputs if isinstance(output, GeneratedFile)}

        assert "model: override" in files[Provider.CLAUDE]
        assert "model: cursor-model" in files[Provider.CURSOR]

        assert all(
            "\n---\n\n<!-- Generated by [Agent Sync Action]"
            "(https://github.com/julien777z/agent-sync-action). "
            "Do not edit this file directly. -->\n\nReview." in content
            for content in files.values()
        )

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
            output for output in outputs if isinstance(output, GeneratedFile) and output.target_path == source
        )

        links = [output for output in outputs if isinstance(output, GeneratedLink)]

        assert source_output.content.startswith("---\ndescription: A rule.\nalwaysApply: true\n---\n")
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
        source.write_text('---\nstarlark: |\n  allow_rule(prefix_rule = ["git", "status"])\n' "---\n")

        context = load_context(workspace)
        outputs = generate_codex_rules(context, Provider.CODEX)

        assert len(outputs) == 1
        assert isinstance(outputs[0], GeneratedFile)
        assert outputs[0].target_path == workspace.root / ".codex/rules/git.rules"

        assert outputs[0].content.startswith(
            "# Generated by [Agent Sync Action]"
            "(https://github.com/julien777z/agent-sync-action). "
            "Do not edit this file directly.\n"
            "# Source: .agents/rules/git.md\n"
        )
        assert 'allow_rule(prefix_rule = ["git", "status"])' in outputs[0].content
        shared_outputs = generate_shared_rule_outputs(context)

        assert len(shared_outputs) == 1
        assert shared_outputs[0].artifact is ArtifactKind.INSTRUCTIONS
        assert not generate_rule_links(context, Provider.CLAUDE)
        assert not generate_rule_links(context, Provider.CURSOR)

    @pytest.mark.parametrize("authored_key", ["globs", "paths"])
    def test_rules_mirror_one_authored_scope_across_provider_keys(
        self,
        workspace: Workspace,
        authored_key: str,
    ) -> None:
        """Test that a scope authored under either key is emitted under both."""

        source = workspace.agents_dir / "rules/python.md"
        source.parent.mkdir(parents=True)
        source.write_text(f'---\n{authored_key}: "**/*.py"\n---\n\n# Rule\n')

        context = load_context(workspace)
        outputs = generate_shared_rule_outputs(context)
        normalized = next(
            output for output in outputs if isinstance(output, GeneratedFile) and output.target_path == source
        )

        assert "globs: '**/*.py'\n" in normalized.content
        assert "paths: '**/*.py'\n" in normalized.content

    def test_rules_scope_annotation_reads_a_paths_only_rule(
        self,
        workspace: Workspace,
    ) -> None:
        """Test that a Claude-style paths scope annotates the root instructions."""

        source = workspace.agents_dir / "rules/python.md"
        source.parent.mkdir(parents=True)
        source.write_text('---\npaths: ["**/*.py", "**/*.pyi"]\nalwaysApply: false\n---\n\n# Rule\n')

        context = load_context(workspace)
        instructions = next(
            output
            for output in generate_shared_rule_outputs(context)
            if isinstance(output, GeneratedFile) and output.artifact is ArtifactKind.INSTRUCTIONS
        )

        assert "> Applies only to files matching: `**/*.py`, `**/*.pyi`" in instructions.content

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
            '{"$comment":"source comment","model":"sonnet",'
            '"permissions":{"allow":["Read"]},'
            '"features":{"default_mode_request_user_input":true,"experimental-feature":false}}'
        )

        outputs = generate_claude_settings(load_context(workspace), Provider.CLAUDE)

        assert len(outputs) == 1
        assert isinstance(outputs[0], GeneratedFile)
        assert json.loads(outputs[0].content) == {
            "$comment": (
                "Generated by [Agent Sync Action]"
                "(https://github.com/julien777z/agent-sync-action). "
                "Do not edit this file directly."
            ),
            "model": "sonnet",
            "permissions": {"allow": ["Read"]},
            "features": {
                "default_mode_request_user_input": True,
                "experimental-feature": False,
            },
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
        settings_path.write_text(
            '{"model":"gpt-5","project_doc_max_bytes":1,'
            '"features":{"default_mode_request_user_input":true}}'
        )

        config_path = workspace.root / ".codex/config.toml"
        config_path.parent.mkdir()
        config_path.write_text('model_reasoning_effort = "high"\n')

        assert mirror_providers(workspace, dry_run=False) is False

        instructions = (workspace.root / "AGENTS.md").read_text()
        capacity = len(instructions.encode("utf-8"))
        canonical = json.loads(settings_path.read_text())
        config_content = config_path.read_text()
        native = tomllib.loads(config_path.read_text())

        assert canonical == {
            "model": "gpt-5",
            "project_doc_max_bytes": capacity,
            "features": {"default_mode_request_user_input": True},
        }

        assert config_content.startswith(
            "# Generated by [Agent Sync Action]"
            "(https://github.com/julien777z/agent-sync-action). "
            "Do not edit this file directly.\n"
        )
        assert native == canonical
        assert "model_reasoning_effort" not in native
        assert mirror_providers(workspace, dry_run=True) is False

    def test_codex_features_accept_arbitrary_names(self, workspace: Workspace) -> None:
        """Test that arbitrary Codex feature names are synchronized unchanged."""

        workspace.settings_dir.mkdir()
        settings_path = workspace.settings_dir / "codex.json"
        settings_path.write_text(
            '{"project_doc_max_bytes":1,"features":'
            '{"default_mode_request_user_input":true,"experimental-feature":false}}'
        )

        assert mirror_providers(workspace, dry_run=False) is False

        canonical = json.loads(settings_path.read_text())
        native = tomllib.loads((workspace.root / ".codex/config.toml").read_text())

        assert canonical["features"] == {
            "default_mode_request_user_input": True,
            "experimental-feature": False,
        }
        assert native["features"] == canonical["features"]
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

        assert os.readlink(workspace.root / ".claude/rules/python.md") == ("../../.agents/rules/python.md")
        assert os.readlink(workspace.root / ".codex/skills/review") == ("../../.agents/skills/review")
        assert mirror_providers(workspace, dry_run=True) is False

    def test_codex_skill_policy_transitions_are_idempotent(self, workspace: Workspace) -> None:
        """Test that invocation-policy changes replace either Codex skill shape."""

        source = workspace.agents_dir / "skills/review/SKILL.md"
        front_matter = SkillFrontMatterFactory.build(name="review")
        materialize_skill(source, front_matter)

        assert mirror_providers(workspace, dry_run=False) is False
        assert (workspace.root / ".codex/skills/review").is_symlink()

        materialize_skill(
            source,
            front_matter.model_copy(update={"disable_model_invocation": True}),
        )

        assert mirror_providers(workspace, dry_run=False) is False

        codex_skill = workspace.root / ".codex/skills/review"
        claude_skill = workspace.root / ".claude/skills/review"
        cursor_skill = workspace.root / ".cursor/skills/review"

        assert claude_skill.is_symlink()
        assert cursor_skill.is_symlink()
        assert "disable-model-invocation: true" in (claude_skill / "SKILL.md").read_text()
        assert "disable-model-invocation: true" in (cursor_skill / "SKILL.md").read_text()
        assert codex_skill.is_dir()
        assert not codex_skill.is_symlink()
        assert (codex_skill / "SKILL.md").is_symlink()
        assert (codex_skill / "agents/openai.yaml").read_text() == (
            "policy:\n  allow_implicit_invocation: false\n"
        )
        assert mirror_providers(workspace, dry_run=True) is False

        materialize_skill(source, front_matter)

        assert mirror_providers(workspace, dry_run=False) is False
        assert codex_skill.is_symlink()
        assert mirror_providers(workspace, dry_run=True) is False
