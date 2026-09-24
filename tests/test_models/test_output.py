import pytest

from agent_sync.models.output import Provider


class TestProvider:
    """Test that provider output contracts belong to their enum members."""

    @pytest.mark.parametrize(
        ("provider", "extension"),
        [
            (Provider.CLAUDE, ".md"),
            (Provider.CURSOR, ".mdc"),
            (Provider.CODEX, ".rules"),
        ],
        ids=[provider.value for provider in Provider],
    )
    def test_rule_extension(self, provider: Provider, extension: str) -> None:
        """Test that each provider exposes its own rule extension."""

        assert provider.rule_extension == extension
