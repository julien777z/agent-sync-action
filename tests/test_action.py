import os
from pathlib import Path
import subprocess
import sys
from types import ModuleType

import pytest
import yaml

from agent_sync.config import ActionConfig
from tests.conftest import RacingSyncCheckout


def mirror_nothing(agents_dir: str, output_dir: str) -> None:
    """Leave the harness mirrors as they are."""


def mirror_readme(agents_dir: str, output_dir: str) -> None:
    """Mirror the README into the generated output directory."""

    (Path(output_dir) / "mirror.md").write_text(Path("README.md").read_text())


def remote_log(racing_sync_checkout: RacingSyncCheckout, log_format: str) -> list[str]:
    """Return the remote branch's commits, newest first, in one log format."""

    return subprocess.run(
        ["git", "log", f"--format={log_format}", "main"],
        cwd=racing_sync_checkout.remote,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()


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
                    "Directory holding generated harness trees, relative to the repository "
                    "root; empty writes them at the root."
                ),
                "default": "",
            },
            "dry-run": {
                "description": (
                    "Report changes without writing; harness mirror drift fails while external updates "
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
            if "mirror-harnesses" in step.get("run", "")
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

    def test_overtaken_push_is_retried(
        self,
        persist_script: ModuleType,
        racing_sync_checkout: RacingSyncCheckout,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that a sync push overtaken by a new commit on the branch is retried on top of it."""

        monkeypatch.setattr(persist_script, "mirror_harnesses", mirror_nothing)

        racing_sync_checkout.races.write_text("1")

        persist_script.persist_changes(Path("."), ".agents", "generated", "commit", "main")

        assert remote_log(racing_sync_checkout, "%s")[:3] == [
            persist_script.SYNC_COMMIT_MESSAGE,
            "compete",
            "initial",
        ]

    def test_push_overtaken_every_attempt_fails(
        self,
        persist_script: ModuleType,
        racing_sync_checkout: RacingSyncCheckout,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that a sync push overtaken on every attempt fails after the last one."""

        monkeypatch.setattr(persist_script, "mirror_harnesses", mirror_nothing)

        racing_sync_checkout.races.write_text("99")

        with pytest.raises(RuntimeError, match="to main after 3 attempts"):
            persist_script.persist_changes(Path("."), ".agents", "generated", "commit", "main")

        assert racing_sync_checkout.races.read_text() == str(99 - persist_script.PUSH_ATTEMPTS)

    def test_dropped_sync_commit_is_recommitted(
        self,
        persist_script: ModuleType,
        racing_sync_checkout: RacingSyncCheckout,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that a sync commit the rebase drops is made again rather than amending the branch's tip."""

        monkeypatch.setattr(persist_script, "mirror_harnesses", mirror_readme)

        readme = (racing_sync_checkout.checkout / "README.md").read_text()
        racing_sync_checkout.prepare_race_commit(
            "generated/mirror.md", readme, persist_script.SYNC_COMMIT_MESSAGE
        )
        racing_sync_checkout.prepare_race_commit("README.md", "Changed\n", "source change")
        racing_sync_checkout.races.write_text("1")

        persist_script.persist_changes(Path("."), ".agents", "generated", "commit", "main")

        assert remote_log(racing_sync_checkout, "%s by %an")[:2] == [
            f"{persist_script.SYNC_COMMIT_MESSAGE} by {ActionConfig.COMMIT_AUTHOR_NAME}",
            "source change by Racer",
        ]

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

        assert "python -m agent_sync mirror-harnesses" in action_text
        assert "python -m agent_sync refresh-external-resources" in action_text
        assert "vendor-skills" not in action_text + persistence_text
        assert "external_skills.json" not in action_text + persistence_text
        assert "refresh-external-skills" not in action_text + persistence_text
        assert "AGENT_SYNC_SKILLS_CLI_VERSION: ${{ inputs.skills-cli-version }}" in action_text
        assert "PYTHONPATH=" not in action_text
        assert "requirements.txt" not in action_text

    def test_repository_validates_the_current_checkout_action(self) -> None:
        """Test that pull-request CI invokes the action from the current checkout."""

        workflow_text = Path(".github/workflows/test.yml").read_text(encoding="utf-8")

        assert "poetry run python -m agent_sync mirror-harnesses --root ." in workflow_text
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

        harness_file = tmp_path / output_dir / ".codex/config.toml"
        harness_file.parent.mkdir(parents=True)
        harness_file.write_text('model = "test"\n')
        marker = (
            "Generated by [Agent Sync Action](https://github.com/julien777z/agent-sync-action). "
            "Do not edit this file directly."
            if manages_instructions
            else "Authored instructions."
        )
        (tmp_path / "AGENTS.md").write_text(marker + "\n")
        (tmp_path / "CLAUDE.md").write_text("Authored Claude Code instructions.\n")
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
        expected = {str(harness_file.relative_to(tmp_path))}

        if manages_instructions:
            expected.add("AGENTS.md")

        assert set(staged) == expected

    def test_staging_relocated_outputs_ignores_root_harness_files(self, tmp_path: Path) -> None:
        """Test that staging a relocated output does not include root harness files."""

        subprocess.run(["git", "init", "--quiet", str(tmp_path)], check=True)

        generated_file = tmp_path / ".generated/.codex/config.toml"
        generated_file.parent.mkdir(parents=True)
        generated_file.write_text('model = "test"\n')
        abandoned_generated_file = tmp_path / ".codex/config.toml"
        abandoned_generated_file.parent.mkdir()
        abandoned_generated_file.write_text('model = "generated"\n')
        root_harness_file = tmp_path / ".codex/repository.toml"
        root_harness_file.write_text('model = "repository"\n')
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
                "test: add generated harness file",
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
