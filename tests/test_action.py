from pathlib import Path

import yaml


def test_action_keeps_the_public_input_contract() -> None:
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


def test_action_uses_the_installed_unified_cli() -> None:
    """Test that every action operation uses the canonical package entrypoint."""

    action_text = Path("action.yml").read_text(encoding="utf-8")

    assert "python -m agent_sync mirror-providers" in action_text
    assert "python -m agent_sync vendor-skills" in action_text
    assert "PYTHONPATH=" not in action_text
    assert "requirements.txt" not in action_text


def test_repository_validates_the_current_checkout_action() -> None:
    """Test that pull-request CI invokes the action from the current checkout."""

    workflow_text = Path(".github/workflows/test.yml").read_text(encoding="utf-8")

    assert "poetry run python -m agent_sync mirror-providers --root ." in workflow_text
    assert "uses: ./" in workflow_text
