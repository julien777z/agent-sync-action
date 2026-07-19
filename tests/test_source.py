import pytest

from agent_sync.errors import AgentSyncError
from agent_sync.models.output import Provider
from agent_sync.source import load_configuration
from agent_sync.workspace import Workspace


class TestCanonicalSources:
    """Verify canonical configuration is strict and typed."""

    def test_missing_optional_directories_produce_empty_configuration(
        self,
        workspace: Workspace,
    ) -> None:
        """Test that absent optional configuration is represented explicitly."""

        configuration = load_configuration(workspace)

        assert configuration.settings == {}
        assert configuration.model_overrides == {}

    def test_malformed_json_fails(self, workspace: Workspace) -> None:
        """Test that malformed present JSON cannot be silently ignored."""

        workspace.settings_dir.mkdir()
        (workspace.settings_dir / "claude.json").write_text("{invalid")

        with pytest.raises(AgentSyncError, match="Invalid JSON"):
            load_configuration(workspace)

    def test_unknown_provider_settings_fail(self, workspace: Workspace) -> None:
        """Test that settings for an unsupported provider are rejected."""

        workspace.settings_dir.mkdir()
        (workspace.settings_dir / "unknown.json").write_text("{}")

        with pytest.raises(AgentSyncError, match="Unsupported provider"):
            load_configuration(workspace)

    def test_unused_codex_agent_override_fails(self, workspace: Workspace) -> None:
        """Test that the unsupported Codex agent-model key is rejected."""

        workspace.models_dir.mkdir()
        (workspace.models_dir / "review.json").write_text('{"codex":"unused"}')

        with pytest.raises(AgentSyncError, match="codex"):
            load_configuration(workspace)

    def test_provider_settings_are_typed(self, workspace: Workspace) -> None:
        """Test that supported provider files are indexed by provider enum."""

        workspace.settings_dir.mkdir()
        (workspace.settings_dir / "cursor.json").write_text('{"model":"cursor-model"}')

        configuration = load_configuration(workspace)

        assert configuration.settings[Provider.CURSOR].model == "cursor-model"

    @pytest.mark.parametrize("slug", ["Bad Name", "UPPER", "-leading"])
    def test_invalid_model_slug_fails(self, workspace: Workspace, slug: str) -> None:
        """Test that unsafe model override filenames are rejected."""

        workspace.models_dir.mkdir(exist_ok=True)
        (workspace.models_dir / f"{slug}.json").write_text("{}")

        with pytest.raises(ValueError, match="Invalid slug"):
            load_configuration(workspace)


def test_workspace_reads_current_disk_state(workspace: Workspace) -> None:
    """Test that workspace reads never return stale cached content."""

    path = workspace.root / "state.txt"
    path.write_text("first")
    assert workspace.read_text(path) == "first"

    path.write_text("second")

    assert workspace.read_text(path) == "second"
