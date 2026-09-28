from collections.abc import Callable
from pathlib import Path
from typing import TypedDict

from pydantic import BaseModel, ConfigDict

from agent_sync.models.document import AgentFrontMatter, RuleFrontMatter, SkillFrontMatter
from agent_sync.models.output import GeneratedOutput, Provider
from agent_sync.models.settings import SourceConfig, Workspace


class SkillSource(BaseModel):
    """Hold one validated skill source."""

    model_config = ConfigDict(frozen=True)

    slug: str
    path: Path
    directory: Path
    front_matter: SkillFrontMatter


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
    global_instructions: str = ""
    project_instructions: str = ""
    hooks: tuple[HookSource, ...]
    instructions: str = ""


type GenerationHandler = Callable[[GenerationContext, Provider], list[GeneratedOutput]]


class ArtifactRegistration(TypedDict):
    """Describe generation and ownership for one artifact kind."""

    owned_directory: str | None
    owned_files: dict[Provider, tuple[str, ...]]
    handlers: dict[Provider, GenerationHandler]
