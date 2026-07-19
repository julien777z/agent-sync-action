import logging

from agent_sync.document import parse_markdown
from agent_sync.errors import AgentSyncError
from agent_sync.models.document import SkillFrontMatter
from agent_sync.models.output import ArtifactKind, GeneratedLink, GeneratedOutput
from agent_sync.models.provider import PROVIDER_LAYOUTS
from agent_sync.slug import validate_slug
from agent_sync.workspace import Workspace

logger = logging.getLogger(__name__)


def generate_skill_outputs(workspace: Workspace) -> list[GeneratedOutput]:
    """Generate provider links for every canonical skill directory."""

    outputs: list[GeneratedOutput] = []
    skills_dir = workspace.agents_dir / "skills"
    if not skills_dir.exists():
        return outputs

    for skill_dir in sorted(skills_dir.iterdir()):
        if not skill_dir.is_dir():
            continue

        slug = validate_slug(skill_dir.name, skill_dir)
        source_path = skill_dir / "SKILL.md"
        content = workspace.read_text(source_path)
        if content is None:
            logger.warning("Missing SKILL.md in %s.", skill_dir)
            continue

        front_matter, _ = parse_markdown(content, SkillFrontMatter, str(source_path))
        if front_matter.name != slug:
            raise AgentSyncError(
                f"Skill {source_path} must use directory name {slug!r} "
                f"as its front matter name, not {front_matter.name!r}"
            )

        for provider, layout in PROVIDER_LAYOUTS.items():
            outputs.append(
                GeneratedLink(
                    target_path=layout.root(workspace.root) / "skills" / slug,
                    link_target=skill_dir,
                    artifact=ArtifactKind.SKILL,
                    source_path=source_path,
                    provider=provider,
                )
            )

    return outputs
