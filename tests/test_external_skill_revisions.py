import subprocess
from pathlib import Path

import pytest

from agent_sync import external_skills
from agent_sync.models.registry import ExternalSkill


def test_resolve_repo_revision_returns_head_sha(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that repository HEAD resolution returns the exact commit SHA."""

    revision = "a" * 40

    def fake_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args=[], returncode=0, stdout=f"{revision}\tHEAD\n")

    monkeypatch.setattr(external_skills.subprocess, "run", fake_run)

    assert external_skills.resolve_repo_revision("owner/repo") == revision


def test_resolve_repo_revision_rejects_invalid_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that an unusable remote HEAD fails before sources can be mixed."""

    def fake_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args=[], returncode=0, stdout="not-a-sha\tHEAD\n")

    monkeypatch.setattr(external_skills.subprocess, "run", fake_run)

    with pytest.raises(RuntimeError, match="git ls-remote"):
        external_skills.resolve_repo_revision("owner/repo")


def test_cli_install_uses_local_source_snapshot(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Test that the skills CLI installs from the downloaded source snapshot."""

    source_root = tmp_path / "source"
    captured: list[str] = []

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        captured.extend(command)
        return subprocess.CompletedProcess(args=command, returncode=0, stdout="")

    monkeypatch.setattr(external_skills.subprocess, "run", fake_run)
    skill = ExternalSkill(name="example", repo="owner/repo")

    external_skills.run_cli_install(skill, tmp_path, source_root)

    assert str(source_root) in captured


def test_vendor_uses_one_snapshot_for_cli_and_root_assets(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Test that root-level assets and installed content share one commit."""

    revision = "c" * 40
    observed: list[tuple[str, str]] = []
    skill = ExternalSkill(name="example", repo="owner/repo")

    monkeypatch.setattr(
        external_skills,
        "resolve_repo_revision",
        lambda repo: revision,
    )

    def fake_download(repo: str, downloaded_revision: str, dest: str) -> Path:
        observed.append(("tarball", downloaded_revision))
        source_root = Path(dest) / "owner-repo"
        source_root.mkdir(parents=True)
        (source_root / "SKILL.md").write_text("content\n", encoding="utf-8")

        return source_root

    monkeypatch.setattr(
        external_skills,
        "download_and_extract_tarball",
        fake_download,
    )

    def fake_install(
        installed_skill: ExternalSkill,
        cwd: Path,
        source_root: Path,
    ) -> None:
        observed.append(("cli", str(source_root)))
        installed = cwd / ".claude" / "skills" / installed_skill.name
        installed.mkdir(parents=True)
        (installed / "SKILL.md").write_text("content\n", encoding="utf-8")

    monkeypatch.setattr(external_skills, "run_cli_install", fake_install)
    monkeypatch.setattr(external_skills, "read_skill_path", lambda cwd: "SKILL.md")
    monkeypatch.setattr(
        external_skills,
        "supplement_root_level_assets",
        lambda installed_skill, dest, source_root: observed.append(
            ("assets", str(source_root))
        ),
    )

    external_skills.vendor_skill(skill, tmp_path / "skills", dry_run=True)

    assert observed[0] == ("tarball", revision)
    assert observed[1][0] == "cli"
    assert observed[2] == ("assets", observed[1][1])
