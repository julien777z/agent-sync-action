from agent_sync.generate import assemble_agents_instructions


class AgentSyncValidationError(ValueError):
    """Raised when canonical agent sources cannot produce valid outputs."""


def validate_codex_instruction_capacity(settings: dict[str, object]) -> None:
    """Require the configured Codex document capacity to fit generated instructions."""

    configured = settings.get("project_doc_max_bytes")
    assert isinstance(configured, int)
    required = len(assemble_agents_instructions().encode("utf-8"))
    if required > configured:
        raise AgentSyncValidationError(
            ".agents/settings/codex.json project_doc_max_bytes "
            f"({configured}) is smaller than generated AGENTS.md ({required} bytes)"
        )
