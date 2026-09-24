import pytest

from agent_sync.errors import AgentSyncError
from agent_sync.generation.artifact import generate_skills
from agent_sync.models.output import GeneratedLink, Provider
from agent_sync.workspace import Workspace
from tests.factories import SkillFrontMatterFactory, load_context, materialize_skill


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
            output.target_path: output.link_target for output in outputs if isinstance(output, GeneratedLink)
        }

        assert links == {
            workspace.root / ".claude/skills/sample-skill": source.parent,
            workspace.root / ".cursor/skills/sample-skill": source.parent,
            workspace.root / ".codex/skills/sample-skill": source.parent,
        }

    def test_a_grouped_skill_still_mirrors_at_its_slug(
        self,
        workspace: Workspace,
    ) -> None:
        """Test that a skill inside a grouping folder links from the flat provider path."""

        front_matter = SkillFrontMatterFactory.build()
        source = workspace.agents_dir / "skills" / "doctors" / front_matter.name / "SKILL.md"
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

    def test_a_grouping_folder_does_not_namespace_a_skill(
        self,
        workspace: Workspace,
    ) -> None:
        """Test that the same slug in two grouping folders is rejected rather than silently shadowed."""

        front_matter = SkillFrontMatterFactory.build()
        skills_dir = workspace.agents_dir / "skills"
        materialize_skill(skills_dir / "doctors" / front_matter.name / "SKILL.md", front_matter)
        materialize_skill(skills_dir / "git" / front_matter.name / "SKILL.md", front_matter)

        with pytest.raises(AgentSyncError, match="defined twice"):
            load_context(workspace)

    def test_a_folder_holding_no_skill_is_rejected(
        self,
        workspace: Workspace,
    ) -> None:
        """Test that a directory with neither a SKILL.md nor a nested skill is still an error."""

        (workspace.agents_dir / "skills" / "doctors" / "references").mkdir(parents=True)

        with pytest.raises(AgentSyncError, match="Missing SKILL.md"):
            load_context(workspace)

    def test_explicit_only_skill_links_to_one_canonical_directory(self, workspace: Workspace) -> None:
        front_matter = SkillFrontMatterFactory.build(disable_model_invocation=True)
        source = workspace.agents_dir / "skills" / front_matter.name / "SKILL.md"
        materialize_skill(source, front_matter)

        outputs = [
            output for provider in Provider for output in generate_skills(load_context(workspace), provider)
        ]
        assert all(isinstance(output, GeneratedLink) for output in outputs)
        assert {output.link_target for output in outputs if isinstance(output, GeneratedLink)} == {
            source.parent
        }
        assert {output.provider for output in outputs} == set(Provider)

    @pytest.mark.parametrize("as_symlink", [False, True], ids=["file", "symlink"])
    def test_rejects_provider_metadata_in_canonical_skill(
        self, workspace: Workspace, as_symlink: bool
    ) -> None:
        front_matter = SkillFrontMatterFactory.build()
        source = workspace.agents_dir / "skills" / front_matter.name / "SKILL.md"
        materialize_skill(source, front_matter)
        metadata = source.parent / "agents/openai.yaml"
        metadata.parent.mkdir()
        if as_symlink:
            metadata.symlink_to("missing-openai.yaml")
        else:
            metadata.write_text("policy: {}\n")

        with pytest.raises(AgentSyncError, match="Repository skills cannot contain"):
            load_context(workspace)

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
