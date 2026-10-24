from agent_sync.generation.registry import ARTIFACT_REGISTRY
from agent_sync.models.output import ArtifactKind, Harness


class TestArtifactRegistry:
    """Test that the harness support matrix is explicit."""

    def test_declares_supported_harness_artifacts(self) -> None:
        """Test that the registry contains the stable harness support matrix."""

        assert {
            artifact: set(registration["handlers"]) for artifact, registration in ARTIFACT_REGISTRY.items()
        } == {
            ArtifactKind.SKILL: {Harness.CLAUDE, Harness.CURSOR, Harness.CODEX},
            ArtifactKind.AGENT: {Harness.CLAUDE, Harness.CURSOR},
            ArtifactKind.RULE: {Harness.CLAUDE, Harness.CURSOR, Harness.CODEX},
            ArtifactKind.HOOK: {Harness.CLAUDE, Harness.CURSOR, Harness.CODEX},
            ArtifactKind.SETTING: {Harness.CLAUDE, Harness.CODEX},
        }
