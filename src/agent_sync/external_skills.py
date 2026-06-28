import io
import json
import shutil
import subprocess
import tarfile
import tempfile
import urllib.request
from pathlib import Path
from typing import Final

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from rich.panel import Panel
from rich.table import Table

from agent_sync.utils import fs
from agent_sync.utils.console import console, logger
from agent_sync.utils.slugs import SAFE_SLUG_PATTERN

SKILLS_CLI_VERSION: Final[str] = "1.5.13"
REGISTRY_FILENAME: Final[str] = "skills.json"
INSTALL_AGENT: Final[str] = "claude-code"
CODELOAD_URL: Final[str] = "https://codeload.github.com/{repo}/tar.gz/{ref}"
TARBALL_EXCLUDES: Final[frozenset[str]] = frozenset(
    {".git", ".github", ".gitignore", ".gitattributes", "node_modules", ".DS_Store"}
)


class ExternalSkill(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    name: str
    repo: str
    skill: str | None = None
    managed: bool = True

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        """Reject names that would not be a safe skill directory slug."""

        if not SAFE_SLUG_PATTERN.match(value):
            raise ValueError(f"Invalid skill name '{value}' (must match {SAFE_SLUG_PATTERN.pattern})")

        return value

    @property
    def upstream_skill(self) -> str:
        """Return the skill slug to request from the source repo (defaults to the local name)."""

        return self.skill or self.name


class SkillsRegistry(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    version: int = 1
    skills: list[ExternalSkill] = Field(default_factory=list)


def run_refresh(dry_run: bool) -> int:
    """Refresh registered external skills into the .agents/skills source directory."""

    registry_path = fs.agents_dir() / REGISTRY_FILENAME
    registry = load_registry(registry_path)
    if registry is None:
        console.print(f"[dim]No external-skill registry at {registry_path}; nothing to refresh.[/dim]")

        return 0

    managed = [skill for skill in registry.skills if skill.managed]
    if not managed:
        console.print("[dim]No managed external skills in registry; nothing to refresh.[/dim]")

        return 0

    skills_dir = fs.agents_dir() / "skills"
    results: list[tuple[ExternalSkill, bool]] = []
    for skill in managed:
        changed = vendor_skill(skill, skills_dir, dry_run=dry_run)
        results.append((skill, changed))

    report_results(results, dry_run=dry_run)

    changed_count = sum(1 for _, changed in results if changed)
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

    logger.info("Refreshing [bold]%s[/bold] from %s", skill.name, skill.repo)

    with tempfile.TemporaryDirectory(prefix="agent-sync-skill-") as tmp:
        tmp_path = Path(tmp)
        run_cli_install(skill, tmp_path)

        installed = locate_installed_skill(tmp_path, skill.name)
        skill_path = read_skill_path(tmp_path)
        if skill_path is not None and "/" not in skill_path:
            supplement_root_level_assets(skill, installed)

        dest = skills_dir / skill.name
        changed = trees_differ(installed, dest)
        if changed and not dry_run:
            fs.delete_path(dest)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(installed, dest)

    return changed


def run_cli_install(skill: ExternalSkill, cwd: Path) -> None:
    """Install a single skill into cwd/.claude/skills via the skills CLI, raising on failure."""

    command = [
        "npx",
        "--yes",
        f"skills@{SKILLS_CLI_VERSION}",
        "add",
        skill.repo,
        "--skill",
        skill.upstream_skill,
        "-a",
        INSTALL_AGENT,
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


def supplement_root_level_assets(skill: ExternalSkill, dest_dir: Path) -> None:
    """Copy sibling assets the CLI drops for a repo-root skill from the source tarball into dest_dir."""

    logger.info("  Supplementing root-level assets for %s from %s tarball", skill.name, skill.repo)

    with tempfile.TemporaryDirectory(prefix="agent-sync-tar-") as tmp:
        extract_root = download_and_extract_tarball(skill.repo, tmp)
        for entry in sorted(extract_root.iterdir()):
            if entry.name in TARBALL_EXCLUDES:
                continue
            target = dest_dir / entry.name
            if entry.is_dir():
                shutil.copytree(entry, target, dirs_exist_ok=True)
            else:
                shutil.copy2(entry, target)


def download_and_extract_tarball(repo: str, dest: str) -> Path:
    """Download a GitHub repo tarball via codeload and extract it, returning the single extracted root dir."""

    url = CODELOAD_URL.format(repo=repo, ref="HEAD")
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


def report_results(results: list[tuple[ExternalSkill, bool]], dry_run: bool) -> None:
    """Print a summary table of which external skills changed."""

    table = Table(show_header=True, header_style="bold")
    table.add_column("Skill")
    table.add_column("Source")
    table.add_column("Status")

    for skill, changed in results:
        if changed:
            status = "[yellow]would update[/yellow]" if dry_run else "[green]updated[/green]"
        else:
            status = "[dim]unchanged[/dim]"
        table.add_row(skill.name, skill.repo, status)

    console.print(table)

    changed_count = sum(1 for _, changed in results if changed)
    verb = "would change" if dry_run else "changed"
    console.print(Panel(f"{changed_count} of {len(results)} external skill(s) {verb}.", style="green"))
