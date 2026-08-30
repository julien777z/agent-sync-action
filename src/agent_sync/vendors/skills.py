from pathlib import Path

from agent_sync.document import parse_markdown, render_front_matter
from agent_sync.models.document import SkillFrontMatter


def normalize_installed_skill(directory: Path, name: str, source_url: str | None = None) -> None:
    """Rewrite an installed skill's front matter for its local canonical directory."""

    document = directory / "SKILL.md"
    content = document.read_text(encoding="utf-8")
    front_matter, body = parse_markdown(content, SkillFrontMatter, str(document))
    metadata = dict(front_matter.metadata or {})

    if source_url is not None:
        metadata["source"] = source_url

    normalized = front_matter.model_copy(update={"name": name, "metadata": metadata or None})

    if normalized == front_matter:
        return

    document.write_text(render_front_matter(normalized, body), encoding="utf-8")


def normalize_installed_skills(skills_dir: Path, installed: list[str]) -> None:
    """Align every installed skill's front matter name with its directory name."""

    directories = {
        skills_dir / Path(path).relative_to(skills_dir).parts[0]
        for path in (Path(entry).resolve() for entry in installed)
        if path.is_relative_to(skills_dir)
    }

    for directory in sorted(directories):
        if (directory / "SKILL.md").is_file():
            normalize_installed_skill(directory, directory.name)
