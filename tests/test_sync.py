from pathlib import Path

from agent_sync import sync


def write_skill(root: Path, slug: str, body: str = "Body text.") -> Path:
    """Create a minimal .agents/skills/<slug>/SKILL.md under root and return its path."""

    skill_dir = root / ".agents" / "skills" / slug
    skill_dir.mkdir(parents=True)
    source = skill_dir / "SKILL.md"
    source.write_text(
        f"---\nname: {slug}\ndescription: Does a thing.\n---\n\n# {slug}\n\n{body}\n",
        encoding="utf-8",
    )

    return source


class TestGenerateHookOutputs:
    """Test hook sync output and stale-path detection."""

    def test_stale_cursor_hook_when_source_removed(self, patch_sync_dirs: Path) -> None:
        """Test that a generated .cursor/hooks file is stale when no .agents/hooks source maps to it."""

        cursor_hooks_dir = patch_sync_dirs / ".cursor" / "hooks"
        cursor_hooks_dir.mkdir(parents=True)
        stale_file = cursor_hooks_dir / "orphan.sh"
        stale_file.write_text("#!/usr/bin/env bash\necho stale\n", encoding="utf-8")

        outputs = sync.generate_hook_outputs()
        stale_paths = sync.compute_stale_paths(outputs, {})

        assert stale_file in stale_paths


class TestGenerateSkillOutputs:
    """Test that skill sources disperse into the expected Claude/Cursor/Codex files."""

    def test_generate_skill_outputs_targets_codex_skill_md(self, patch_sync_dirs: Path) -> None:
        """Test that a skill source is written to .codex/skills/<name>/SKILL.md with name/description front matter."""

        write_skill(patch_sync_dirs, "my-skill")

        outputs = sync.generate_skill_outputs()
        codex_output = next(output for output in outputs if output.kind == "codex_skill")

        assert codex_output.target_path == patch_sync_dirs / ".codex" / "skills" / "my-skill" / "SKILL.md"
        assert 'name: "my-skill"' in codex_output.content
        assert 'description: "Does a thing."' in codex_output.content
        assert "# my-skill" in codex_output.content

    def test_generate_skill_outputs_copies_nested_assets(self, patch_sync_dirs: Path) -> None:
        """Test that nested skill assets (a references/ file) disperse to every platform skill dir."""

        write_skill(patch_sync_dirs, "vendored")
        references = patch_sync_dirs / ".agents" / "skills" / "vendored" / "references"
        references.mkdir()
        (references / "details.md").write_text("Detail content.\n", encoding="utf-8")

        outputs = sync.generate_skill_outputs()
        asset_targets = {
            output.target_path for output in outputs if output.kind.endswith("_skill_asset")
        }

        for platform in ("claude", "cursor", "codex"):
            base = patch_sync_dirs / f".{platform}" / "skills" / "vendored"
            assert base / "references" / "details.md" in asset_targets


class TestComputeStalePaths:
    """Test that stale generated files are detected correctly against current sources."""

    def test_marks_orphan_rule_as_stale_and_keeps_managed(self, patch_sync_dirs: Path) -> None:
        """Test that a generated rule with no .agents source is stale while an expected rule is kept."""

        claude_rules_dir = patch_sync_dirs / ".claude" / "rules"
        claude_rules_dir.mkdir(parents=True)
        orphan_rule = claude_rules_dir / "orphan.md"
        orphan_rule.write_text("legacy\n", encoding="utf-8")
        managed_rule = claude_rules_dir / "managed.md"
        managed_rule.write_text("managed\n", encoding="utf-8")

        expected_output = sync.OutputFile(
            target_path=managed_rule,
            content="managed\n",
            kind="claude_rule",
            slug="managed",
            source_path=None,
        )
        stale_paths = sync.compute_stale_paths([expected_output], {})

        assert orphan_rule in stale_paths
        assert managed_rule not in stale_paths

    def test_vendored_skill_dir_is_not_stale(self, patch_sync_dirs: Path) -> None:
        """Test that a mirror skill dir backed by a .agents/skills source is kept while an orphan dir is stale."""

        write_skill(patch_sync_dirs, "security-audit")
        outputs = sync.generate_skill_outputs()

        for output in outputs:
            sync.fs.write_text(output.target_path, output.content)

        orphan_dir = patch_sync_dirs / ".claude" / "skills" / "left-over"
        orphan_dir.mkdir(parents=True)
        (orphan_dir / "SKILL.md").write_text("stale\n", encoding="utf-8")

        stale_paths = sync.compute_stale_paths(outputs, {})

        assert orphan_dir in stale_paths
        assert patch_sync_dirs / ".claude" / "skills" / "security-audit" not in stale_paths

    def test_orphan_settings_removed_only_when_source_absent(self, patch_sync_dirs: Path) -> None:
        """Test that .claude/settings.json is stale when its source is gone but kept when the source still exists."""

        settings_path = patch_sync_dirs / ".claude" / "settings.json"
        settings_path.parent.mkdir(parents=True)
        settings_path.write_text("{}\n", encoding="utf-8")

        stale_without_source = sync.compute_stale_paths([], {})

        assert settings_path in stale_without_source

        source = patch_sync_dirs / ".agents" / "settings" / "claude.json"
        source.parent.mkdir(parents=True)
        source.write_text("{ invalid", encoding="utf-8")

        stale_with_unparsed_source = sync.compute_stale_paths([], {})

        assert settings_path not in stale_with_unparsed_source
