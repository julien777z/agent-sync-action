import argparse
import io
import json
import logging
import re
import shutil
import subprocess
import tarfile
import tempfile
import urllib.request
from pathlib import Path
from typing import Final

from pydantic import ValidationError

from agent_sync.models.registry import ExternalSkill, SkillsRegistry, VendorResult
from agent_sync.utils import fs

logger = logging.getLogger(__name__)

SKILLS_CLI_VERSION: Final[str] = "1.5.13"
REGISTRY_FILENAME: Final[str] = "skills.json"
TARBALL_EXCLUDES: Final[frozenset[str]] = frozenset(
    {
        "node_modules",
        "dist",
        "build",
        "__pycache__",
        "package.json",
        "package-lock.json",
        "pnpm-lock.yaml",
        "yarn.lock",
        "tsconfig.json",
        "Makefile",
    }
)


def run_refresh(dry_run: bool) -> int:
    """Refresh registered external skills into the .agents/skills source directory."""

    registry_path = fs.agents_dir() / REGISTRY_FILENAME
    registry = load_registry(registry_path)
    if registry is None:
        logger.info("No external-skill registry at %s; nothing to refresh.", registry_path)

        return 0

    managed = [skill for skill in registry.skills if skill.managed]
    if not managed:
        logger.info("No managed external skills in registry; nothing to refresh.")

        return 0

    skills_dir = fs.agents_dir() / "skills"
    results: list[VendorResult] = []
    for skill in managed:
        changed = vendor_skill(skill, skills_dir, dry_run=dry_run)
        results.append(VendorResult(skill=skill, changed=changed))

    report_results(results, dry_run=dry_run)

    changed_count = sum(1 for result in results if result.changed)
    if dry_run and changed_count:
        return 1

    return 0


def load_registry(path: Path) -> SkillsRegistry | None:
    """Load and validate the external-skill registry, returning None when it is absent."""

    raw = fs.read_text(path)
    if raw is None:
        return None

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {path}: {exc}") from exc

    try:
        return SkillsRegistry.model_validate(data)
    except ValidationError as exc:
        raise ValueError(f"Invalid external-skill registry at {path}: {exc}") from exc


def vendor_skill(skill: ExternalSkill, skills_dir: Path, dry_run: bool) -> bool:
    """Install one external skill into a temp dir and vendor it into .agents/skills/<name>, returning whether it changed."""

    logger.info("Refreshing %s from %s", skill.name, skill.repo)

    with tempfile.TemporaryDirectory(prefix="agent-sync-skill-") as tmp:
        tmp_path = Path(tmp)
        revision = resolve_repo_revision(skill.repo)
        source_root = download_and_extract_tarball(
            skill.repo,
            revision,
            str(tmp_path / "source"),
        )
        run_cli_install(skill, tmp_path, source_root)

        installed = locate_installed_skill(tmp_path, skill.name)
        skill_path = read_skill_path(tmp_path)
        if skill_path is not None and "/" not in skill_path:
            supplement_root_level_assets(skill, installed, source_root)

        dest = skills_dir / skill.name
        changed = trees_differ(installed, dest)
        if changed and not dry_run:
            fs.delete_path(dest)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(installed, dest)

    return changed


def resolve_repo_revision(repo: str) -> str:
    """Resolve the repository's current HEAD so every source read uses one revision."""

    command = ["git", "ls-remote", f"https://github.com/{repo}.git", "HEAD"]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    revision = result.stdout.split(maxsplit=1)[0] if result.stdout.strip() else ""
    if result.returncode != 0 or re.fullmatch(r"[0-9a-fA-F]{40}", revision) is None:
        raise RuntimeError(
            f"`git ls-remote {repo} HEAD` failed (exit {result.returncode}):\n"
            f"{result.stdout}\n{result.stderr}"
        )

    return revision


def run_cli_install(skill: ExternalSkill, cwd: Path, source_root: Path) -> None:
    """Install a single skill into cwd/.claude/skills via the skills CLI, raising on failure."""

    command = [
        "npx",
        "--yes",
        f"skills@{SKILLS_CLI_VERSION}",
        "add",
        str(source_root),
        "--skill",
        skill.upstream_skill,
        "-a",
        "claude-code",
        "-y",
        "--copy",
    ]
    result = subprocess.run(command, cwd=cwd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(
            f"`skills add {skill.repo} --skill {skill.upstream_skill}` failed "
            f"(exit {result.returncode}):\n{result.stdout}\n{result.stderr}"
        )


def locate_installed_skill(cwd: Path, name: str) -> Path:
    """Return the installed skill directory, raising loudly when the CLI produced nothing usable."""

    expected = cwd / ".claude" / "skills" / name
    if expected.is_dir():
        return expected

    installed_root = cwd / ".claude" / "skills"
    candidates = [path for path in installed_root.glob("*") if path.is_dir()] if installed_root.exists() else []
    if len(candidates) == 1:
        return candidates[0]

    raise RuntimeError(
        f"Could not locate installed skill '{name}' under {installed_root} "
        f"(found: {[path.name for path in candidates]})"
    )


def read_skill_path(cwd: Path) -> str | None:
    """Return the skillPath of the single skill recorded in skills-lock.json, if present."""

    raw = fs.read_text(cwd / "skills-lock.json")
    if raw is None:
        return None

    entries = json.loads(raw).get("skills", {})
    if len(entries) != 1:
        return None

    entry = next(iter(entries.values()))
    skill_path = entry.get("skillPath") if isinstance(entry, dict) else None

    return skill_path if isinstance(skill_path, str) else None


def supplement_root_level_assets(
    skill: ExternalSkill,
    dest_dir: Path,
    source_root: Path,
) -> None:
    """Copy sibling assets the CLI drops for a repo-root skill from the source tarball into dest_dir."""

    logger.info("  Supplementing root-level assets for %s from %s tarball", skill.name, skill.repo)

    for entry in sorted(source_root.iterdir()):
        if entry.name.startswith(".") or entry.name in TARBALL_EXCLUDES:
            continue
        target = dest_dir / entry.name
        if entry.is_dir():
            shutil.copytree(entry, target, dirs_exist_ok=True)
        else:
            shutil.copy2(entry, target)


def download_and_extract_tarball(repo: str, revision: str, dest: str) -> Path:
    """Download a GitHub repo tarball via codeload and extract it, returning the single extracted root dir."""

    url = f"https://codeload.github.com/{repo}/tar.gz/{revision}"
    request = urllib.request.Request(url, headers={"User-Agent": "agent-sync"})
    with urllib.request.urlopen(request, timeout=60) as response:
        payload = response.read()

    with tarfile.open(fileobj=io.BytesIO(payload), mode="r:gz") as archive:
        archive.extractall(dest, filter="data")

    roots = [path for path in Path(dest).iterdir() if path.is_dir()]
    if len(roots) != 1:
        raise RuntimeError(f"Unexpected tarball layout for {repo}: {[path.name for path in roots]}")

    return roots[0]


def snapshot_tree(directory: Path) -> dict[str, bytes]:
    """Return a mapping of relative path to file bytes for every file under directory."""

    if not directory.is_dir():
        return {}

    snapshot: dict[str, bytes] = {}
    for path in sorted(directory.rglob("*")):
        if path.is_file():
            snapshot[str(path.relative_to(directory))] = path.read_bytes()

    return snapshot


def trees_differ(source: Path, dest: Path) -> bool:
    """Report whether two skill directories differ in file set or content."""

    return snapshot_tree(source) != snapshot_tree(dest)


def report_results(results: list[VendorResult], dry_run: bool) -> None:
    """Log a summary of which external skills changed."""

    for result in results:
        if result.changed:
            status = "would update" if dry_run else "updated"
        else:
            status = "unchanged"
        logger.info("  %s (%s): %s", result.skill.name, result.skill.repo, status)

    changed_count = sum(1 for result in results if result.changed)
    verb = "would change" if dry_run else "changed"
    logger.info("%d of %d external skill(s) %s.", changed_count, len(results), verb)


def main() -> int:
    """Refresh registered external skills into the .agents/skills source directory."""

    parser = argparse.ArgumentParser(
        prog="agent_sync.external_skills",
        description="Install/update external skills from the registry.",
    )
    fs.add_root_arguments(parser)
    parser.add_argument("--dry-run", action="store_true", help="Report changes without writing.")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    fs.set_root_from_args(args)

    return run_refresh(dry_run=args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
