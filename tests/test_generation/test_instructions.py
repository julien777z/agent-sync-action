import json
import tomllib

import pytest

from agent_sync.config import CodexSettings
from agent_sync.reconciliation import mirror_providers
from agent_sync.workspace import Workspace
from tests.factories import materialize_every_source_kind


class TestUnmanagedInstructions:
    """Test mirroring with repository-owned root instructions."""

    @pytest.mark.parametrize("output_dirname", ["", ".generated"], ids=["root", "relocated"])
    @pytest.mark.parametrize("capacity", [None, 65536], ids=["default-capacity", "explicit-capacity"])
    def test_preserves_instructions_and_configured_capacity(
        self, workspace: Workspace, output_dirname: str, capacity: int | None
    ) -> None:
        """Test that root files stay untouched while configured provider settings are mirrored."""

        workspace = workspace.model_copy(
            update={"generate_agents_md": False, "output_dirname": output_dirname}
        )
        materialize_every_source_kind(workspace)
        instructions = workspace.root / "AGENTS.md"
        instructions.write_text("Repository-owned instructions.\n")
        claude_instructions = workspace.root / "CLAUDE.md"
        claude_instructions.write_text("Repository-owned Claude guidance.\n")
        workspace.settings_dir.mkdir()
        settings = CodexSettings(
            model="gpt-5",
            features={"default_mode_request_user_input": True},
            project_doc_max_bytes=capacity,
        ).model_dump(exclude_none=True)

        settings_path = workspace.settings_dir / "codex.json"
        settings_path.write_text(json.dumps(settings))
        originals = {path: path.read_bytes() for path in (instructions, claude_instructions, settings_path)}

        assert mirror_providers(workspace, dry_run=True) is True
        assert all(path.read_bytes() == content for path, content in originals.items())
        assert mirror_providers(workspace, dry_run=False) is False
        assert instructions.read_bytes() == originals[instructions]
        assert claude_instructions.read_bytes() == originals[claude_instructions]
        assert json.loads(settings_path.read_text()) == settings
        assert tomllib.loads((workspace.output_root / ".codex/config.toml").read_text()) == settings
        assert (workspace.output_root / ".codex/skills/sample/SKILL.md").is_file()
        assert mirror_providers(workspace, dry_run=True) is False
