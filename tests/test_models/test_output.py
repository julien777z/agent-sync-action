import pytest

from agent_sync.models.output import Harness


class TestHarness:
    """Test that harness output contracts belong to their enum members."""

    @pytest.mark.parametrize(
        ("harness", "extension"),
        [
            (Harness.CLAUDE_CODE, ".md"),
            (Harness.CURSOR, ".mdc"),
            (Harness.CODEX, ".rules"),
        ],
        ids=[harness.value for harness in Harness],
    )
    def test_rule_extension(self, harness: Harness, extension: str) -> None:
        """Test that each harness exposes its own rule extension."""

        assert harness.rule_extension == extension
