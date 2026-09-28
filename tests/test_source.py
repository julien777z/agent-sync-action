import pytest

from agent_sync.models.output import Provider
from agent_sync.models.settings import Workspace
from agent_sync.source import load_source_config
from agent_sync.utils import AgentSyncError
from agent_sync.workspace import models_dir, settings_dir


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

        settings_dir(workspace).mkdir()
        (settings_dir(workspace) / "claude.json").write_text("{invalid")

        with pytest.raises(AgentSyncError, match="Invalid JSON"):
            load_source_config(workspace)

    def test_unknown_provider_settings_fail(self, workspace: Workspace) -> None:
        """Test that settings for an unsupported provider are rejected."""

        settings_dir(workspace).mkdir()
        (settings_dir(workspace) / "unknown.json").write_text("{}")

        with pytest.raises(AgentSyncError, match="Unsupported provider"):
            load_source_config(workspace)

    def test_unused_codex_agent_override_fails(self, workspace: Workspace) -> None:
        """Test that the unsupported Codex agent-model key is rejected."""

        models_dir(workspace).mkdir()
        (models_dir(workspace) / "review.json").write_text('{"codex":"unused"}')

        with pytest.raises(AgentSyncError, match="codex"):
            load_source_config(workspace)

    def test_provider_settings_are_typed(self, workspace: Workspace) -> None:
        """Test that supported provider files are indexed by provider enum."""

        settings_dir(workspace).mkdir()
        (settings_dir(workspace) / "cursor.json").write_text('{"model":"cursor-model"}')

        source_config = load_source_config(workspace)

        assert source_config.settings[Provider.CURSOR].model == "cursor-model"

    @pytest.mark.parametrize("slug", ["Bad Name", "UPPER", "-leading"])
    def test_invalid_model_slug_fails(self, workspace: Workspace, slug: str) -> None:
        """Test that unsafe model override filenames are rejected."""

        models_dir(workspace).mkdir(exist_ok=True)
        (models_dir(workspace) / f"{slug}.json").write_text("{}")

        with pytest.raises(ValueError, match="Invalid slug"):
            load_source_config(workspace)
