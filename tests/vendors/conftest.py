from collections.abc import Callable
from pathlib import Path

import pytest

from agent_sync.config import ACTION_CONFIG
from agent_sync.models.vendors import ecc as ecc_models
from agent_sync.models.vendors import skills_cli as skills_cli_models
from agent_sync.models.vendors.skills_cli import SkillsCliVendor, VendoredSkill
from agent_sync.vendors.skills_cli import discovery, github, installer
from tests.factories import materialize_tree


@pytest.fixture
def snapshot(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Serve one synthetic repository snapshot to the skills.sh vendoring path."""

    source_root = tmp_path / "snapshot"
    source_root.mkdir()

    def fake_resolve(repository: str) -> str:
        """Return a stable synthetic revision."""

        return "a" * 40

    def fake_download(repository: str, revision: str, destination: Path) -> Path:
        """Return the prepared synthetic snapshot."""

        return source_root

    def fake_install(
        vendor: SkillsCliVendor,
        skill: VendoredSkill,
        install_directory: Path,
        search_root: Path,
    ) -> None:
        """Copy the resolved upstream skill the way the installer would."""

        located = discovery.locate_skill_directory(search_root, skill.upstream_skill)
        materialize_tree(
            install_directory / ".staging/skills" / skill.name,
            {"SKILL.md": (located / "SKILL.md").read_text(encoding="utf-8")},
        )

    monkeypatch.setattr(github, "resolve_revision", fake_resolve)
    monkeypatch.setattr(github, "download_snapshot", fake_download)
    monkeypatch.setattr(installer, "install_skill", fake_install)

    return source_root


@pytest.fixture
def configure_action(monkeypatch: pytest.MonkeyPatch) -> Callable[..., None]:
    """Install action settings carrying the given overrides for every vendor model."""

    def _configure(**overrides: str) -> None:
        """Replace the settings object each vendor model reads its defaults from."""

        settings = ACTION_CONFIG.model_copy(update=overrides)

        for module in (skills_cli_models, ecc_models):
            monkeypatch.setattr(module, "ACTION_CONFIG", settings)

    return _configure
