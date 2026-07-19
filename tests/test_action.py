from pathlib import Path

import yaml


class TestAction:
    """Test that the reusable action and repository workflow keep their contract."""

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
                    "<agents-dir>/skills.json."
                ),
                "default": ".agents",
            },
            "dry-run": {
                "description": (
                    "Report changes without writing or committing; fails if anything is out of sync."
                ),
                "default": "false",
            },
        }

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
