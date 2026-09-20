from pathlib import Path

import yaml


def selects_a_fixed_flag(line: str) -> bool:
    """Report whether a line's expression can only ever expand to a fixed flag."""

    return "--dry-run" in line


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
            "refresh-external-skills": {
                "description": "Force vendoring external skills from the registry before mirroring.",
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
                    "Source-of-truth directory name; the registry is read from "
                    "<agents-dir>/external_skills.json."
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
        assert '"$OUTPUT_DIR" AGENTS.md' in action_text

    def test_keeps_configurable_values_out_of_the_scripts(self) -> None:
        """Test that a consumer's value reaches bash as data rather than as script text."""

        steps = yaml.safe_load(Path("action.yml").read_text(encoding="utf-8"))["runs"]["steps"]
        interpolations = [
            line
            for step in steps
            for line in step.get("run", "").splitlines()
            if "${{" in line and not selects_a_fixed_flag(line)
        ]

        assert not interpolations

    def test_stages_a_tracked_path_a_run_deleted(self) -> None:
        """Test that staging reaches a tracked path no longer on disk, and skips an empty one."""

        action_text = Path("action.yml").read_text(encoding="utf-8")

        assert '[ -e "$path" ] || [ -n "$(git ls-files -- "$path")" ]' in action_text
        assert 'if [ -z "$path" ]; then continue; fi' in action_text

    def test_both_persist_modes_stage_through_one_definition(self) -> None:
        """Test that each mode reaches staging through the single shared definition."""

        action_text = Path("action.yml").read_text(encoding="utf-8")

        calls = [line for line in action_text.splitlines() if line.strip() == "stage_generated_paths"]

        assert action_text.count("stage_generated_paths() {") == 1
        assert len(calls) == 2

    def test_uses_the_installed_unified_cli(self) -> None:
        """Test that every action operation uses the canonical package entrypoint."""

        action_text = Path("action.yml").read_text(encoding="utf-8")

        assert "python -m agent_sync mirror-providers" in action_text
        assert "python -m agent_sync vendor-skills" in action_text
        assert "AGENT_SYNC_SKILLS_CLI_VERSION: ${{ inputs.skills-cli-version }}" in action_text
        assert "PYTHONPATH=" not in action_text
        assert "requirements.txt" not in action_text

    def test_repository_validates_the_current_checkout_action(self) -> None:
        """Test that pull-request CI invokes the action from the current checkout."""

        workflow_text = Path(".github/workflows/test.yml").read_text(encoding="utf-8")

        assert "poetry run python -m agent_sync mirror-providers --root ." in workflow_text
        assert "uses: ./" in workflow_text
        assert 'refresh-external-skills: "true"' in workflow_text

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
