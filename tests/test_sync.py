import json
from collections.abc import Callable
from pathlib import Path

import pytest
from pydantic import ValidationError

from agent_sync import generate, plan
from agent_sync.constants import CODEX_MCP_END_MARKER, CODEX_MCP_START_MARKER
from agent_sync.loaders import McpConfigError, load_mcp_config
from agent_sync.mcp import McpGenerationError, generate_codex_config
from agent_sync.models.json_types import JsonObject
from agent_sync.models.mcp import McpConfig
from agent_sync.models.outputs import OutputFile, OutputKind
from agent_sync.sync import run_sync
from agent_sync.utils import fs


# pylint: disable-next=too-few-public-methods
class TestGenerateHookOutputs:
    """Test that hook outputs and stale paths are generated correctly."""

    def test_stale_cursor_hook_when_source_removed(self, patch_sync_dirs: Path) -> None:
        """Test that a generated Cursor hook is stale without its source."""

        cursor_hooks_dir = patch_sync_dirs / ".cursor" / "hooks"
        cursor_hooks_dir.mkdir(parents=True)
        stale_file = cursor_hooks_dir / "orphan.sh"
        stale_file.write_text("#!/usr/bin/env bash\necho stale\n", encoding="utf-8")

        outputs = generate.generate_hook_outputs()
        stale_paths = plan.compute_stale_paths(outputs, {})

        assert stale_file in stale_paths


class TestGenerateSkillOutputs:
    """Test that skill sources disperse into the expected Claude/Cursor/Codex files."""

    def test_generate_skill_outputs_targets_codex_skill_md(
        self, patch_sync_dirs: Path, skill_file_factory: Callable[..., Path]
    ) -> None:
        """Test that a canonical skill renders as a valid Codex skill."""

        skill_file_factory("my-skill")

        outputs = generate.generate_skill_outputs()
        codex_output = next(output for output in outputs if output.kind == OutputKind.CODEX_SKILL)

        assert codex_output.target_path == (
            patch_sync_dirs / ".codex" / "skills" / "my-skill" / "SKILL.md"
        )
        assert 'name: "my-skill"' in codex_output.content
        assert 'description: "Does a thing."' in codex_output.content
        assert "# my-skill" in codex_output.content

    def test_generate_skill_outputs_copies_nested_assets(
        self, patch_sync_dirs: Path, skill_file_factory: Callable[..., Path]
    ) -> None:
        """Test that nested skill assets disperse to every platform."""

        skill_file_factory("vendored")
        references = patch_sync_dirs / ".agents" / "skills" / "vendored" / "references"
        references.mkdir()
        (references / "details.md").write_text("Detail content.\n", encoding="utf-8")

        outputs = generate.generate_skill_outputs()
        asset_targets = {
            output.target_path
            for output in outputs
            if output.kind.endswith("_skill_asset")
        }

        for platform in ("claude", "cursor", "codex"):
            base = patch_sync_dirs / f".{platform}" / "skills" / "vendored"
            assert base / "references" / "details.md" in asset_targets

    def test_binary_skill_asset_kept_as_bytes(
        self, patch_sync_dirs: Path, skill_file_factory: Callable[..., Path]
    ) -> None:
        """Test that a non-UTF-8 skill asset is carried as bytes instead of crashing dispersal."""

        skill_file_factory("vendored")
        asset = patch_sync_dirs / ".agents" / "skills" / "vendored" / "logo.png"
        payload = b"\x89PNG\r\n\x1a\n\xff\xfe\x00"
        asset.write_bytes(payload)

        outputs = generate.generate_skill_outputs()
        binary_outputs = [output for output in outputs if output.source_path == asset]

        assert binary_outputs
        assert all(output.content == payload for output in binary_outputs)


class TestComputeStalePaths:
    """Test that stale generated files are detected correctly against current sources."""

    def test_marks_orphan_rule_as_stale_and_keeps_managed(
        self,
        patch_sync_dirs: Path,
    ) -> None:
        """Test that orphan rules are stale while expected rules remain."""

        claude_rules_dir = patch_sync_dirs / ".claude" / "rules"
        claude_rules_dir.mkdir(parents=True)
        orphan_rule = claude_rules_dir / "orphan.md"
        orphan_rule.write_text("legacy\n", encoding="utf-8")
        managed_rule = claude_rules_dir / "managed.md"
        managed_rule.write_text("managed\n", encoding="utf-8")

        expected_output = OutputFile(
            target_path=managed_rule,
            content="managed\n",
            kind=OutputKind.CLAUDE_RULE,
            slug="managed",
            source_path=None,
        )
        stale_paths = plan.compute_stale_paths([expected_output], {})

        assert orphan_rule in stale_paths
        assert managed_rule not in stale_paths

    def test_vendored_skill_dir_is_not_stale(
        self, patch_sync_dirs: Path, skill_file_factory: Callable[..., Path]
    ) -> None:
        """Test that sourced skill directories remain while orphans are stale."""

        skill_file_factory("security-audit")
        outputs = generate.generate_skill_outputs()

        for output in outputs:
            fs.write(output.target_path, output.content)

        orphan_dir = patch_sync_dirs / ".claude" / "skills" / "left-over"
        orphan_dir.mkdir(parents=True)
        (orphan_dir / "SKILL.md").write_text("stale\n", encoding="utf-8")

        stale_paths = plan.compute_stale_paths(outputs, {})

        assert orphan_dir in stale_paths
        assert (
            patch_sync_dirs / ".claude" / "skills" / "security-audit"
            not in stale_paths
        )

    def test_orphan_settings_removed_only_when_source_absent(
        self,
        patch_sync_dirs: Path,
    ) -> None:
        """Test that Claude settings become stale only after source removal."""

        settings_path = patch_sync_dirs / ".claude" / "settings.json"
        settings_path.parent.mkdir(parents=True)
        settings_path.write_text("{}\n", encoding="utf-8")

        stale_without_source = plan.compute_stale_paths([], {})

        assert settings_path in stale_without_source

        source = patch_sync_dirs / ".agents" / "settings" / "claude.json"
        source.parent.mkdir(parents=True)
        source.write_text("{ invalid", encoding="utf-8")

        stale_with_unparsed_source = plan.compute_stale_paths([], {})

        assert settings_path not in stale_with_unparsed_source


class TestMcpConfig:
    """Test that canonical MCP configuration enforces the secret-safety contract."""

    def test_loads_oauth_and_env_backed_servers(
        self, mcp_file_factory: Callable[[JsonObject], Path]
    ) -> None:
        """Test that OAuth and environment-backed servers load from the canonical file."""

        mcp_file_factory(
            {
                "version": 1,
                "servers": {
                    "gateway": {
                        "type": "http",
                        "url": "https://mcp.example.com/mcp",
                        "auth": {"type": "oauth"},
                    },
                    "private-api": {
                        "type": "http",
                        "url": "https://private.example.com/mcp",
                        "auth": {"type": "bearer-env", "env": "AGENT_MCP_GATEWAY_TOKEN"},
                        "envHeaders": {"X-Workspace": "MCP_WORKSPACE"},
                        "platforms": ["claude", "codex"],
                    },
                },
            }
        )

        config = load_mcp_config()

        assert config is not None
        assert set(config.servers) == {"gateway", "private-api"}

    @pytest.mark.parametrize(
        "server",
        [
            {
                "type": "http",
                "url": "https://user:password@example.com/mcp",
            },
            {
                "type": "http",
                "url": "https://example.com/mcp?token=literal",
            },
            {
                "type": "http",
                "url": "https://example.com/mcp",
                "auth": {"type": "bearer-env", "env": "TOKEN", "token": "literal"},
            },
            {
                "type": "stdio",
                "command": "server",
                "args": ["--api-key=literal"],
                "platforms": ["claude"],
            },
        ],
    )
    def test_rejects_literal_credentials(self, server: JsonObject) -> None:
        """Test that credential-like literal values are rejected."""

        with pytest.raises(ValidationError):
            McpConfig.model_validate({"version": 1, "servers": {"unsafe": server}})

    def test_rejects_unknown_fields_and_invalid_environment_names(self) -> None:
        """Test that unknown fields and non-portable environment names are rejected."""

        with pytest.raises(ValidationError):
            McpConfig.model_validate(
                {
                    "version": 1,
                    "servers": {
                        "unsafe": {
                            "type": "stdio",
                            "command": "server",
                            "env": ["lowercase-secret"],
                            "platforms": ["claude"],
                            "unknown": True,
                        }
                    },
                }
            )

    @pytest.mark.parametrize(
        "server",
        [
            {
                "type": "stdio",
                "command": "server",
                "env": ["SECRET"],
            },
            {
                "type": "http",
                "url": "https://example.com/mcp",
                "auth": {"type": "bearer-env", "env": "SECRET"},
            },
            {
                "type": "http",
                "url": "https://example.com/mcp",
                "envHeaders": {"X-API-Key": "SECRET"},
            },
        ],
    )
    def test_rejects_cursor_environment_references(self, server: JsonObject) -> None:
        """Test that env-backed secrets cannot target Cursor project configuration."""

        with pytest.raises(ValidationError, match="Cursor project MCP config"):
            McpConfig.model_validate({"version": 1, "servers": {"unsafe": server}})

    def test_loader_raises_for_invalid_json(
        self, mcp_file_factory: Callable[[JsonObject], Path]
    ) -> None:
        """Test that malformed canonical JSON fails loudly."""

        path = mcp_file_factory({"version": 1, "servers": {}})
        path.write_text("{invalid", encoding="utf-8")
        fs.TEXT_CACHE.clear()

        with pytest.raises(McpConfigError, match="Invalid JSON"):
            load_mcp_config()


class TestGenerateMcpOutputs:
    """Test that MCP configuration renders safely for all supported clients."""

    def test_generates_all_platform_formats_and_preserves_codex_settings(
        self, patch_sync_dirs: Path
    ) -> None:
        """Test that native formats are generated while unrelated Codex settings remain intact."""

        codex_path = patch_sync_dirs / ".codex" / "config.toml"
        codex_path.parent.mkdir(parents=True)
        existing = 'model = "gpt-5"\n\n[features]\nmulti_agent = true\n'
        codex_path.write_text(existing, encoding="utf-8")
        config = McpConfig.model_validate(
            {
                "version": 1,
                "servers": {
                    "gateway": {
                        "type": "http",
                        "url": "https://mcp.example.com/mcp",
                        "auth": {"type": "oauth"},
                    },
                    "local-tools": {
                        "type": "stdio",
                        "command": "npx",
                        "args": ["-y", "@example/mcp"],
                    },
                    "private-api": {
                        "type": "http",
                        "url": "https://private.example.com/mcp",
                        "auth": {"type": "bearer-env", "env": "AGENT_MCP_GATEWAY_TOKEN"},
                        "envHeaders": {"X-Workspace": "MCP_WORKSPACE"},
                        "platforms": ["claude", "codex"],
                    },
                },
            }
        )

        outputs = generate.generate_mcp_outputs(config)
        by_kind = {output.kind: output for output in outputs}
        claude = json.loads(by_kind[OutputKind.CLAUDE_MCP].content)
        cursor = json.loads(by_kind[OutputKind.CURSOR_MCP].content)
        codex = by_kind[OutputKind.CODEX_MCP].content

        assert claude["mcpServers"]["private-api"]["headers"] == {
            "Authorization": "Bearer ${AGENT_MCP_GATEWAY_TOKEN}",
            "X-Workspace": "${MCP_WORKSPACE}",
        }
        assert set(cursor["mcpServers"]) == {"gateway", "local-tools"}
        assert existing in codex
        assert '[mcp_servers."gateway"]' in codex
        assert "required = true" in codex
        assert 'bearer_token_env_var = "AGENT_MCP_GATEWAY_TOKEN"' in codex
        assert 'env_http_headers = { "X-Workspace" = "MCP_WORKSPACE" }' in codex

    def test_codex_replaces_only_managed_block(self) -> None:
        """Test that Codex generation replaces only the marked MCP block."""

        old = (
            'model = "gpt-5"\n\n'
            f"{CODEX_MCP_START_MARKER}\n"
            '[mcp_servers."old"]\n'
            'url = "https://old.example.com/mcp"\n'
            f"{CODEX_MCP_END_MARKER}\n\n"
            "[features]\nmulti_agent = true\n"
        )
        config = McpConfig.model_validate(
            {
                "version": 1,
                "servers": {
                    "new": {
                        "type": "http",
                        "url": "https://new.example.com/mcp",
                        "auth": {"type": "oauth"},
                    }
                },
            }
        )

        rendered = generate_codex_config(config, old)

        assert 'model = "gpt-5"\n\n' in rendered
        assert "\n\n[features]\nmulti_agent = true\n" in rendered
        assert '[mcp_servers."old"]' not in rendered
        assert '[mcp_servers."new"]' in rendered
        assert rendered.count(CODEX_MCP_START_MARKER) == 1

    @pytest.mark.parametrize(
        "existing",
        [
            f"{CODEX_MCP_START_MARKER}\n",
            f"{CODEX_MCP_END_MARKER}\n{CODEX_MCP_START_MARKER}\n",
            (
                f"{CODEX_MCP_START_MARKER}\n{CODEX_MCP_END_MARKER}\n"
                f"{CODEX_MCP_START_MARKER}\n{CODEX_MCP_END_MARKER}\n"
            ),
        ],
    )
    def test_rejects_malformed_codex_markers(self, existing: str) -> None:
        """Test that malformed or duplicate Codex markers fail safely."""

        config = McpConfig.model_validate({"version": 1, "servers": {}})

        with pytest.raises(McpGenerationError):
            generate_codex_config(config, existing)

    def test_empty_config_clears_generated_servers(self, patch_sync_dirs: Path) -> None:
        """Test that an empty canonical config clears previously generated servers."""

        config = McpConfig.model_validate({"version": 1, "servers": {}})
        codex_path = patch_sync_dirs / ".codex" / "config.toml"
        codex_path.parent.mkdir(parents=True)
        codex_path.write_text(
            f'model = "gpt-5"\n\n{CODEX_MCP_START_MARKER}\n'
            '[mcp_servers."stale"]\nrequired = true\n'
            f"{CODEX_MCP_END_MARKER}\n",
            encoding="utf-8",
        )

        outputs = generate.generate_mcp_outputs(config)
        by_kind = {output.kind: output for output in outputs}

        assert json.loads(by_kind[OutputKind.CLAUDE_MCP].content) == {"mcpServers": {}}
        assert json.loads(by_kind[OutputKind.CURSOR_MCP].content) == {"mcpServers": {}}
        assert CODEX_MCP_START_MARKER not in by_kind[OutputKind.CODEX_MCP].content
        assert 'model = "gpt-5"' in by_kind[OutputKind.CODEX_MCP].content

    def test_generation_is_deterministic(self) -> None:
        """Test that source server ordering cannot change generated output."""

        first = McpConfig.model_validate(
            {
                "version": 1,
                "servers": {
                    "z": {"type": "http", "url": "https://z.example.com/mcp"},
                    "a": {"type": "http", "url": "https://a.example.com/mcp"},
                },
            }
        )
        second = McpConfig.model_validate(
            {
                "version": 1,
                "servers": {
                    "a": {"type": "http", "url": "https://a.example.com/mcp"},
                    "z": {"type": "http", "url": "https://z.example.com/mcp"},
                },
            }
        )

        assert generate.generate_mcp_outputs(first)[0].content == generate.generate_mcp_outputs(
            second
        )[0].content


class TestMcpSync:
    """Test that MCP outputs participate safely in the complete sync lifecycle."""

    def test_sync_writes_all_outputs_and_is_idempotent(
        self,
        patch_sync_dirs: Path,
        mcp_file_factory: Callable[[JsonObject], Path],
    ) -> None:
        """Test that one canonical file writes all native formats exactly once."""

        mcp_file_factory(
            {
                "version": 1,
                "servers": {
                    "gateway": {
                        "type": "http",
                        "url": "https://mcp.example.com/mcp",
                        "auth": {"type": "oauth"},
                    }
                },
            }
        )

        assert run_sync(dry_run=False) == 0
        assert (patch_sync_dirs / ".mcp.json").is_file()
        assert (patch_sync_dirs / ".cursor" / "mcp.json").is_file()
        assert (patch_sync_dirs / ".codex" / "config.toml").is_file()
        assert run_sync(dry_run=True) == 0

    def test_missing_source_leaves_existing_mcp_files_untouched(
        self,
        patch_sync_dirs: Path,
    ) -> None:
        """Test that repositories without canonical MCP configuration remain unchanged."""

        agents_dir = patch_sync_dirs / ".agents"
        agents_dir.mkdir()
        claude_path = patch_sync_dirs / ".mcp.json"
        cursor_path = patch_sync_dirs / ".cursor" / "mcp.json"
        codex_path = patch_sync_dirs / ".codex" / "config.toml"
        claude_path.write_text('{"userManaged": true}\n', encoding="utf-8")
        cursor_path.parent.mkdir(parents=True)
        cursor_path.write_text('{"userManaged": true}\n', encoding="utf-8")
        codex_path.parent.mkdir(parents=True)
        codex_path.write_text('model = "gpt-5"\n', encoding="utf-8")

        assert run_sync(dry_run=False) == 0
        assert claude_path.read_text(encoding="utf-8") == '{"userManaged": true}\n'
        assert cursor_path.read_text(encoding="utf-8") == '{"userManaged": true}\n'
        assert codex_path.read_text(encoding="utf-8") == 'model = "gpt-5"\n'
