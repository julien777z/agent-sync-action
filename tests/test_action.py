import os
from pathlib import Path
import subprocess
import sys

import pytest
import yaml


class TestAction:
    """Test that the reusable action and repository workflow keep their contract."""

    def test_uses_unique_marketplace_name(self) -> None:
        """Test that the action publishes under its complete product name."""

        action = yaml.safe_load(Path("action.yml").read_text(encoding="utf-8"))

        assert action["name"] == "Agent Sync Action"

    def test_keeps_the_public_input_contract(self) -> None:
        """Test that action inputs and defaults remain stable through the refactor."""

        action = yaml.safe_load(Path("action.yml").read_text(encoding="utf-8"))

        assert action["inputs"] == {
            "github-token": {
                "description": "Token used to commit and push changes (or open a pull request).",
                "default": "${{ github.token }}",
            },
            "refresh-external-resources": {
                "description": "Force vendoring external skills and resources from the registry before mirroring.",
                "default": "false",
            },
            "skills-cli-version": {
                "description": "Version of the skills CLI used to update external skills.",
                "default": "1.5.13",
            },
            "mode": {
                "description": "How to persist changes — commit (push to the branch) or pull-request.",
                "default": "commit",
            },
            "agents-dir": {
                "description": (
                    "Source-of-truth directory name; the external registry is read from this directory."
                ),
                "default": ".agents",
            },
            "output-dir": {
                "description": (
                    "Directory holding generated provider trees, relative to the repository "
                    "root; empty writes them at the root."
                ),
                "default": "",
            },
            "dry-run": {
                "description": (
                    "Report changes without writing; provider mirror drift fails while external updates "
                    "remain informational."
                ),
                "default": "false",
            },
        }

    def test_threads_the_output_directory_through_mirroring_and_staging(self) -> None:
        """Test that a configured output directory reaches every mirror run and both commits."""

        action_text = Path("action.yml").read_text(encoding="utf-8")

        mirror_steps = [
            step
            for step in yaml.safe_load(action_text)["runs"]["steps"]
            if "mirror-providers" in step.get("run", "")
        ]

        assert mirror_steps
        assert all('--output-dir "$OUTPUT_DIR"' in step["run"] for step in mirror_steps)
        assert all(step.get("env", {}).get("OUTPUT_DIR") for step in mirror_steps)
        assert "AGENT_SYNC_GENERATE_AGENTS_MD" not in action_text
        assert '--output-dir "$OUTPUT_DIR"' in action_text

    def test_keeps_configurable_values_out_of_the_scripts(self) -> None:
        """Test that a consumer's value reaches bash as data rather than as script text."""

        steps = yaml.safe_load(Path("action.yml").read_text(encoding="utf-8"))["runs"]["steps"]
        interpolations = [
            line
            for step in steps
            for line in step.get("run", "").splitlines()
            if "${{" in line and "--dry-run" not in line
        ]

        assert not interpolations

    def test_persistence_uses_the_checked_in_script(self) -> None:
        """Test that the action delegates persistence to its checked-in script."""

        action_text = Path("action.yml").read_text(encoding="utf-8")

        assert 'python "$GITHUB_ACTION_PATH/.github/scripts/persist_changes.py"' in action_text

    @pytest.mark.parametrize("first_push", [False, True], ids=["existing-branch", "new-branch"])
    def test_refresh_detects_registry_changes_with_a_dot_prefixed_agents_dir(
        self, tmp_path: Path, first_push: bool
    ) -> None:
        """Detect registry changes on existing and new branches with an equivalent agents path."""

        subprocess.run(["git", "init", "--quiet", str(tmp_path)], check=True)

        registry = tmp_path / ".agents/external_resources.json"
        registry.parent.mkdir()
        registry.write_text('{"resources":[]}\n')

        subprocess.run(["git", "add", ".agents/external_resources.json"], cwd=tmp_path, check=True)
        commit = ["git", "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "--quiet"]

        subprocess.run([*commit, "-m", "initial"], cwd=tmp_path, check=True)

        before = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=tmp_path, text=True).strip()

        registry.write_text('{"resources":[{"kind":"directory"}]}\n')

        subprocess.run(["git", "add", ".agents/external_resources.json"], cwd=tmp_path, check=True)
        subprocess.run([*commit, "-m", "update"], cwd=tmp_path, check=True)

        current = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=tmp_path, text=True).strip()

        output = tmp_path / "action-output"
        env = {
            **os.environ,
            "GITHUB_OUTPUT": str(output),
        }

        subprocess.run(
            [
                sys.executable,
                str(Path(".github/scripts/refresh_external_resources.py").resolve()),
                "--force",
                "false",
                "--event",
                "push",
                "--before",
                "0" * 40 if first_push else before,
                "--current",
                current,
                "--agents-dir",
                "./.agents",
            ],
            cwd=tmp_path,
            env=env,
            check=True,
        )

        assert output.read_text() == "enabled=true\n"

    def test_both_persist_modes_call_the_staging_script(self) -> None:
        """Test that both commit paths use the same staging script."""

        calls = [
            line
            for line in Path(".github/scripts/persist_changes.py").read_text(encoding="utf-8").splitlines()
            if line.strip().startswith("stage_generated_paths(action_path,")
        ]
        assert len(calls) == 2

    def test_uses_the_installed_unified_cli(self) -> None:
        """Test that every action operation uses the canonical package entrypoint."""

        action_text = Path("action.yml").read_text(encoding="utf-8")
        persistence_text = Path(".github/scripts/persist_changes.py").read_text(encoding="utf-8")

        assert "python -m agent_sync mirror-providers" in action_text
        assert "python -m agent_sync vendor-resources" in action_text
        assert "vendor-skills" not in action_text + persistence_text
        assert "external_skills.json" not in action_text + persistence_text
        assert "refresh-external-skills" not in action_text + persistence_text
        assert "AGENT_SYNC_SKILLS_CLI_VERSION: ${{ inputs.skills-cli-version }}" in action_text
        assert "PYTHONPATH=" not in action_text
        assert "requirements.txt" not in action_text

    def test_repository_validates_the_current_checkout_action(self) -> None:
        """Test that pull-request CI invokes the action from the current checkout."""

        workflow_text = Path(".github/workflows/test.yml").read_text(encoding="utf-8")

        assert "poetry run python -m agent_sync mirror-providers --root ." in workflow_text
        assert "uses: ./" in workflow_text
        assert 'refresh-external-resources: "true"' in workflow_text

    def test_sets_up_node_when_vendoring_may_run(self) -> None:
        """Test that Node setup covers initial and post-rebase vendoring."""

        action_text = Path("action.yml").read_text(encoding="utf-8")

        assert "node_version=\"$(tr -d '[:space:]'" in action_text
        assert "node-version: ${{ steps.node.outputs.version }}" in action_text
        assert "node-version-file: ${{ github.action_path }}/.nvmrc" not in action_text
        assert "steps.refresh.outputs.enabled == 'true' || inputs.mode == 'commit'" in action_text

    def test_agent_sync_workflow_runs_on_feature_branches(self) -> None:
        """Test that repository mirroring is not restricted to the default branch."""

        workflow_text = Path(".github/workflows/agent-sync.yml").read_text(encoding="utf-8")

        assert "branches: [main]" not in workflow_text
        assert "uses: ./" in workflow_text

    @pytest.mark.parametrize("output_dir", ["", ".", ".generated"], ids=["root", "dot", "nested"])
    @pytest.mark.parametrize("manages_instructions", [True, False], ids=["generated", "authored"])
    def test_staging_respects_instruction_ownership(
        self,
        tmp_path: Path,
        output_dir: str,
        manages_instructions: bool,
    ) -> None:
        """Test that staging includes only owned paths and the selected root instructions."""

        subprocess.run(["git", "init", "--quiet", str(tmp_path)], check=True)

        provider_file = tmp_path / output_dir / ".codex/config.toml"
        provider_file.parent.mkdir(parents=True)
        provider_file.write_text('model = "test"\n')
        marker = (
            "Generated by [Agent Sync Action](https://github.com/julien777z/agent-sync-action). "
            "Do not edit this file directly."
            if manages_instructions
            else "Authored instructions."
        )
        (tmp_path / "AGENTS.md").write_text(marker + "\n")
        (tmp_path / "CLAUDE.md").write_text("Authored Claude instructions.\n")
        (tmp_path / "unrelated.txt").write_text("User work.\n")

        subprocess.run(
            [
                sys.executable,
                str(Path(".github/scripts/stage_generated_paths.py").resolve()),
                "--agents-dir",
                ".agents",
                "--output-dir",
                output_dir,
            ],
            cwd=tmp_path,
            check=True,
        )

        staged = subprocess.check_output(
            ["git", "diff", "--cached", "--name-only"], cwd=tmp_path, text=True
        ).splitlines()
        expected = {str(provider_file.relative_to(tmp_path))}

        if manages_instructions:
            expected.add("AGENTS.md")

        assert set(staged) == expected

    def test_staging_relocated_outputs_ignores_root_provider_files(self, tmp_path: Path) -> None:
        """Test that staging a relocated output does not include root provider files."""

        subprocess.run(["git", "init", "--quiet", str(tmp_path)], check=True)

        generated_file = tmp_path / ".generated/.codex/config.toml"
        generated_file.parent.mkdir(parents=True)
        generated_file.write_text('model = "test"\n')
        abandoned_generated_file = tmp_path / ".codex/config.toml"
        abandoned_generated_file.parent.mkdir()
        abandoned_generated_file.write_text('model = "generated"\n')
        root_provider_file = tmp_path / ".codex/repository.toml"
        root_provider_file.write_text('model = "repository"\n')
        subprocess.run(["git", "add", ".codex/config.toml"], cwd=tmp_path, check=True)
        subprocess.run(
            [
                "git",
                "-c",
                "user.name=Test",
                "-c",
                "user.email=test@example.com",
                "commit",
                "--quiet",
                "-m",
                "test: add generated provider file",
            ],
            cwd=tmp_path,
            check=True,
        )
        abandoned_generated_file.unlink()

        subprocess.run(
            [
                sys.executable,
                str(Path(".github/scripts/stage_generated_paths.py").resolve()),
                "--agents-dir",
                ".agents",
                "--output-dir",
                ".generated",
            ],
            cwd=tmp_path,
            check=True,
        )

        staged = subprocess.check_output(
            ["git", "diff", "--cached", "--name-only"], cwd=tmp_path, text=True
        ).splitlines()

        assert set(staged) == {
            str(generated_file.relative_to(tmp_path)),
            str(abandoned_generated_file.relative_to(tmp_path)),
        }

    def test_stages_large_generated_instruction_deletion(self, tmp_path: Path) -> None:
        """Stage owned deletion even when its tracked document is large."""

        subprocess.run(["git", "init", "--quiet", str(tmp_path)], check=True)
        notice = (
            "Generated by [Agent Sync Action](https://github.com/julien777z/agent-sync-action). "
            "Do not edit this file directly."
        )
        instructions = tmp_path / "AGENTS.md"
        instructions.write_text(f"# AGENTS.md\n\n{notice}\n\n" + "long text\n" * 200_000)
        subprocess.run(["git", "add", "AGENTS.md"], cwd=tmp_path, check=True)
        subprocess.run(
            [
                "git",
                "-c",
                "user.name=Test",
                "-c",
                "user.email=test@example.com",
                "commit",
                "--quiet",
                "-m",
                "test",
            ],
            cwd=tmp_path,
            check=True,
        )
        instructions.unlink()
        script = Path(".github/scripts/stage_generated_paths.py").resolve()
        subprocess.run(
            ["bash", "-euo", "pipefail", "-c", f'python "{script}" --agents-dir .agents --output-dir ""'],
            cwd=tmp_path,
            check=True,
        )
        staged = subprocess.check_output(
            ["git", "diff", "--cached", "--name-only"], cwd=tmp_path, text=True
        ).splitlines()
        assert staged == ["AGENTS.md"]
