from agent_sync.generation.registry import ARTIFACT_REGISTRY
from agent_sync.models.output import ArtifactKind, Provider


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
