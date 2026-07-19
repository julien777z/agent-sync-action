import logging
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from agent_sync.configuration import CanonicalConfiguration
from agent_sync.document import parse_markdown
from agent_sync.errors import AgentSyncError
from agent_sync.models.document import (
    AgentFrontMatter,
    RuleFrontMatter,
    SkillFrontMatter,
)
from agent_sync.utils import validate_slug
from agent_sync.workspace import Workspace

logger = logging.getLogger(__name__)


class SkillSource(BaseModel):
    """Hold one validated skill source."""

    model_config = ConfigDict(frozen=True)

    slug: str
    path: Path
    directory: Path


class AgentSource(BaseModel):
    """Hold one parsed agent source."""

    model_config = ConfigDict(frozen=True)

    slug: str
    path: Path
    front_matter: AgentFrontMatter
    body: str


class RuleSource(BaseModel):
    """Hold one parsed rule source."""

    model_config = ConfigDict(frozen=True)

    slug: str
    path: Path
    front_matter: RuleFrontMatter
    body: str


class HookSource(BaseModel):
    """Hold one hook source and its executable intent."""

    model_config = ConfigDict(frozen=True)

    path: Path
    content: str
    executable: bool


class GenerationContext(BaseModel):
    """Hold all immutable inputs for one generation run."""

    model_config = ConfigDict(frozen=True)

    workspace: Workspace
    configuration: CanonicalConfiguration
    skills: tuple[SkillSource, ...]
    agents: tuple[AgentSource, ...]
    rules: tuple[RuleSource, ...]
    hooks: tuple[HookSource, ...]
    instructions: str = ""


def load_generation_context(
    workspace: Workspace,
    configuration: CanonicalConfiguration,
) -> GenerationContext:
    """Read and validate every generation source once."""

    return GenerationContext(
        workspace=workspace,
        configuration=configuration,
        skills=tuple(load_skills(workspace)),
        agents=tuple(load_agents(workspace)),
        rules=tuple(load_rules(workspace)),
        hooks=tuple(load_hooks(workspace)),
    )


def load_skills(workspace: Workspace) -> list[SkillSource]:
    """Load validated skill directories."""

    skills_dir = workspace.agents_dir / "skills"
    if not skills_dir.exists():
        return []

    sources: list[SkillSource] = []
    for directory in sorted(path for path in skills_dir.iterdir() if path.is_dir()):
        slug = validate_slug(directory.name, directory)
        path = directory / "SKILL.md"
        content = workspace.read_text(path)
        if content is None:
            logger.warning("Missing SKILL.md in %s.", directory)
            continue

        front_matter, _ = parse_markdown(content, SkillFrontMatter, str(path))
        if front_matter.name != slug:
            raise AgentSyncError(
                f"Skill {path} must use directory name {slug!r} "
                f"as its front matter name, not {front_matter.name!r}"
            )
        sources.append(SkillSource(slug=slug, path=path, directory=directory))

    return sources


def load_agents(workspace: Workspace) -> list[AgentSource]:
    """Load parsed agent documents."""

    return [
        AgentSource(slug=slug, path=path, front_matter=front_matter, body=body)
        for path, slug, front_matter, body in load_markdown_sources(
            workspace,
            "agents",
            AgentFrontMatter,
        )
    ]


def load_rules(workspace: Workspace) -> list[RuleSource]:
    """Load parsed non-empty rule documents."""

    return [
        RuleSource(slug=slug, path=path, front_matter=front_matter, body=body)
        for path, slug, front_matter, body in load_markdown_sources(
            workspace,
            "rules",
            RuleFrontMatter,
        )
        if body
    ]


def load_hooks(workspace: Workspace) -> list[HookSource]:
    """Load hook files and executable intent."""

    hooks_dir = workspace.agents_dir / "hooks"
    if not hooks_dir.exists():
        return []

    sources: list[HookSource] = []
    for path in sorted(path for path in hooks_dir.iterdir() if path.is_file()):
        content = workspace.read_text(path)
        if content is not None:
            sources.append(
                HookSource(
                    path=path,
                    content=content,
                    executable=path.suffix == ".sh" or content.startswith("#!"),
                )
            )

    return sources


def load_markdown_sources[T: BaseModel](
    workspace: Workspace,
    directory_name: str,
    model: type[T],
) -> list[tuple[Path, str, T, str]]:
    """Load typed Markdown documents from one source directory."""

    directory = workspace.agents_dir / directory_name
    if not directory.exists():
        return []

    sources: list[tuple[Path, str, T, str]] = []
    for path in sorted(directory.glob("*.md")):
        slug = validate_slug(path.stem, path)
        content = workspace.read_text(path)
        if content is not None:
            front_matter, body = parse_markdown(content, model, str(path))
            sources.append((path, slug, front_matter, body))

    return sources
