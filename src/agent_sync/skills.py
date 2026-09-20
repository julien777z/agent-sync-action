from pathlib import Path

from agent_sync.errors import AgentSyncError


def grouping_folders(root: Path) -> list[Path]:
    """Return the directories under a root that may hold skills, in a stable order."""

    return sorted(entry for entry in root.iterdir() if entry.is_dir())


def discover_skill_directories(root: Path) -> list[Path]:
    """Return every skill directory under a root, descending through grouping folders."""

    directories: list[Path] = []

    for path in grouping_folders(root):
        if (path / "SKILL.md").exists():
            directories.append(path)

            continue

        # Following a linked directory lets a cycle recurse without end.
        nested = [] if path.is_symlink() else discover_skill_directories(path)

        if not nested:
            raise AgentSyncError(f"Missing SKILL.md in {path}")

        directories.extend(nested)

    return directories


def locate_skill_by_name(skills_dir: Path, name: str) -> Path | None:
    """Return where a skill already lives under a skills directory, at any depth."""

    if not skills_dir.is_dir():
        return None

    for path in grouping_folders(skills_dir):
        if (path / "SKILL.md").exists():
            if path.name == name:
                return path

            continue

        if path.is_symlink():
            continue

        located = locate_skill_by_name(path, name)

        if located is not None:
            return located

    return None
