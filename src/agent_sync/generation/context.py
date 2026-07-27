import logging
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from agent_sync.config import SourceConfig
from agent_sync.document import parse_markdown
from agent_sync.models.document import (
    AgentFrontMatter,
    RuleFrontMatter,
)
from agent_sync.skill import SkillSource, load_skills
from agent_sync.utils import validate_slug
from agent_sync.workspace import Workspace

logger = logging.getLogger(__name__)


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
    source_config: SourceConfig
    skills: tuple[SkillSource, ...]
    agents: tuple[AgentSource, ...]
    rules: tuple[RuleSource, ...]
    hooks: tuple[HookSource, ...]
    instructions: str = ""


def load_generation_context(
    workspace: Workspace,
    source_config: SourceConfig,
) -> GenerationContext:
    """Read and validate every generation source once."""

    return GenerationContext(
        workspace=workspace,
        source_config=source_config,
        skills=tuple(load_skills(workspace)),
        agents=tuple(load_agents(workspace)),
        rules=tuple(load_rules(workspace)),
        hooks=tuple(load_hooks(workspace)),
    )


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
    """Load parsed rule documents."""

    return [
        RuleSource(slug=slug, path=path, front_matter=front_matter, body=body)
        for path, slug, front_matter, body in load_markdown_sources(
            workspace,
            "rules",
            RuleFrontMatter,
        )
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
