import logging
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from agent_sync.document import parse_markdown
from agent_sync.errors import AgentSyncError
from agent_sync.models.document import SkillFrontMatter
from agent_sync.utils import validate_slug
from agent_sync.workspace import Workspace

logger = logging.getLogger(__name__)


class SkillSource(BaseModel):
    """Hold one validated canonical skill source."""

    model_config = ConfigDict(frozen=True)

    slug: str
    path: Path
    directory: Path


def load_skills(workspace: Workspace) -> list[SkillSource]:
    """Load validated canonical skill directories."""

    skills_dir = workspace.agents_dir / "skills"

    if not skills_dir.exists():
        return []

    sources: list[SkillSource] = []

    for directory in sorted(path for path in skills_dir.iterdir() if path.is_dir()):
        slug = validate_slug(directory.name, directory)
        path = directory / "SKILL.md"
        content = workspace.read_text(path)

        if content is None:
            raise AgentSyncError(f"Missing SKILL.md in {directory}")

        front_matter, _ = parse_markdown(content, SkillFrontMatter, str(path))

        if front_matter.name != slug:
            raise AgentSyncError(
                f"Skill {path} must use directory name {slug!r} "
                f"as its front matter name, not {front_matter.name!r}"
            )

        sources.append(SkillSource(slug=slug, path=path, directory=directory))

    return sources
