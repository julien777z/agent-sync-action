import pytest

from agent_sync.errors import AgentSyncError
from agent_sync.models.output import Provider
from agent_sync.skill import load_skills
from agent_sync.source import load_source_config
from agent_sync.workspace import Workspace


class TestCanonicalSources:
    """Test that canonical configuration is strict and typed."""

    def test_missing_optional_directories_produce_empty_configuration(
        self,
        workspace: Workspace,
    ) -> None:
        """Test that absent optional configuration is represented explicitly."""

        source_config = load_source_config(workspace)

        assert source_config.settings == {}
        assert source_config.model_overrides == {}

    def test_malformed_json_fails(self, workspace: Workspace) -> None:
        """Test that malformed present JSON cannot be silently ignored."""

        workspace.settings_dir.mkdir()
        (workspace.settings_dir / "claude.json").write_text("{invalid")

        with pytest.raises(AgentSyncError, match="Invalid JSON"):
            load_source_config(workspace)

    def test_unknown_provider_settings_fail(self, workspace: Workspace) -> None:
        """Test that settings for an unsupported provider are rejected."""

        workspace.settings_dir.mkdir()
        (workspace.settings_dir / "unknown.json").write_text("{}")

        with pytest.raises(AgentSyncError, match="Unsupported provider"):
            load_source_config(workspace)

    def test_unused_codex_agent_override_fails(self, workspace: Workspace) -> None:
        """Test that the unsupported Codex agent-model key is rejected."""

        workspace.models_dir.mkdir()
        (workspace.models_dir / "review.json").write_text('{"codex":"unused"}')

        with pytest.raises(AgentSyncError, match="codex"):
            load_source_config(workspace)

    def test_provider_settings_are_typed(self, workspace: Workspace) -> None:
        """Test that supported provider files are indexed by provider enum."""

        workspace.settings_dir.mkdir()
        (workspace.settings_dir / "cursor.json").write_text('{"model":"cursor-model"}')

        source_config = load_source_config(workspace)

        assert source_config.settings[Provider.CURSOR].model == "cursor-model"

    @pytest.mark.parametrize("slug", ["Bad Name", "UPPER", "-leading"])
    def test_invalid_model_slug_fails(self, workspace: Workspace, slug: str) -> None:
        """Test that unsafe model override filenames are rejected."""

        workspace.models_dir.mkdir(exist_ok=True)
        (workspace.models_dir / f"{slug}.json").write_text("{}")

        with pytest.raises(ValueError, match="Invalid slug"):
            load_source_config(workspace)


class TestWorkspace:
    """Test that workspace access observes the filesystem directly."""

    def test_reads_current_disk_state(self, workspace: Workspace) -> None:
        """Test that workspace reads never return stale cached content."""

        path = workspace.root / "state.txt"
        path.write_text("first")

        assert workspace.read_text(path) == "first"

        path.write_text("second")

        assert workspace.read_text(path) == "second"


class TestSkills:
    """Test the public canonical skill loader."""

    def test_loads_native_skill_metadata(self, workspace: Workspace) -> None:
        """Load a valid skill from the canonical agent directory."""

        skill_directory = workspace.agents_dir / "skills/dependency-updates"
        skill_directory.mkdir(parents=True)
        (skill_directory / "SKILL.md").write_text(
            "---\n"
            "name: dependency-updates\n"
            "description: Update repository dependencies.\n"
            "---\n\n"
            "Inspect and update the dependency graph.\n"
        )

        skills = load_skills(workspace)

        assert [skill.slug for skill in skills] == ["dependency-updates"]
