from pathlib import Path
from shlex import shlex

from pydantic import BaseModel

from agent_sync.document import parse_markdown
from agent_sync.models.document import (
    AgentFrontMatter,
    RuleFrontMatter,
    SkillFrontMatter,
)
from agent_sync.models.generation import (
    AgentSource,
    GenerationContext,
    HookSource,
    RuleSource,
    SkillSource,
)
from agent_sync.models.settings import SourceConfig, Workspace
from agent_sync.models.hooks import HooksConfig
from agent_sync.skills import discover_skill_directories
from agent_sync.utils import AgentSyncError, load_json_model, validate_slug
from agent_sync.workspace import agents_dir, read_optional_text


def load_generation_context(
    workspace: Workspace,
    source_config: SourceConfig,
) -> GenerationContext:
    """Read and validate every generation source once."""

    hooks, hook_config = load_hooks(workspace)

    return GenerationContext(
        workspace=workspace,
        source_config=source_config,
        skills=tuple(load_skills(workspace)),
        agents=tuple(load_agents(workspace)),
        rules=tuple(load_rules(workspace)),
        global_instructions=load_root_instructions(workspace, "global.md"),
        project_instructions=load_root_instructions(workspace, "project.md"),
        hooks=tuple(hooks),
        hook_config=hook_config,
    )


def load_root_instructions(workspace: Workspace, filename: str) -> str:
    """Read optional root guidance without its front matter."""

    path = agents_dir(workspace) / filename
    content = read_optional_text(path)

    if content is None:
        return ""

    _, body = parse_markdown(content, AgentFrontMatter, str(path))

    return body


def load_skills(workspace: Workspace) -> list[SkillSource]:
    """Load validated skill directories, which may be grouped in folders."""

    skills_dir = agents_dir(workspace) / "skills"

    if not skills_dir.exists():
        return []

    sources: list[SkillSource] = []
    slugs: dict[str, Path] = {}

    for directory in discover_skill_directories(skills_dir):
        forbidden_metadata = directory / "agents/openai.yaml"

        if forbidden_metadata.exists() or forbidden_metadata.is_symlink():
            raise AgentSyncError(f"Repository skills cannot contain {forbidden_metadata}")

        slug = validate_slug(directory.name, directory)

        if slug in slugs:
            raise AgentSyncError(
                f"Skill {slug!r} is defined twice, in {slugs[slug]} and {directory}; "
                "a grouping folder does not namespace a skill"
            )

        slugs[slug] = directory
        path = directory / "SKILL.md"
        content = path.read_text(encoding="utf-8")
        front_matter, _ = parse_markdown(content, SkillFrontMatter, str(path))

        if front_matter.name != slug:
            raise AgentSyncError(
                f"Skill {path} must use directory name {slug!r} "
                f"as its front matter name, not {front_matter.name!r}"
            )

        sources.append(
            SkillSource(
                slug=slug,
                path=path,
                directory=directory,
                front_matter=front_matter,
            )
        )

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
    """Load parsed rule documents."""

    return [
        RuleSource(slug=slug, path=path, front_matter=front_matter, body=body)
        for path, slug, front_matter, body in load_markdown_sources(
            workspace,
            "rules",
            RuleFrontMatter,
        )
    ]


def load_hooks(workspace: Workspace) -> tuple[list[HookSource], HooksConfig | None]:
    """Load hook files and require canonical registration for every hook."""

    hooks_dir = agents_dir(workspace) / "hooks"

    if hooks_dir.is_symlink():
        raise AgentSyncError(f"Hook sources must be regular files or directories, not symlinks: {hooks_dir}")

    if not hooks_dir.exists():
        return [], None

    sources: list[HookSource] = []

    for path in sorted(hooks_dir.rglob("*")):
        if path.is_symlink():
            raise AgentSyncError(f"Hook sources must be regular files or directories, not symlinks: {path}")

        if path == hooks_dir / "hooks.json":
            continue

        relative_path = path.relative_to(hooks_dir)

        if "__pycache__" in relative_path.parts or path.suffix in {".pyc", ".pyo"}:
            continue

        if not path.is_file():
            continue

        content = read_optional_text(path)

        if content is not None:
            sources.append(
                HookSource(
                    path=path,
                    relative_path=relative_path,
                    content=content,
                    executable=bool(path.stat().st_mode & 0o111)
                    or path.suffix == ".sh"
                    or content.startswith("#!"),
                )
            )

    registration = hooks_dir / "hooks.json"
    config = load_json_model(registration, HooksConfig)

    if sources and config is None:
        raise AgentSyncError(f"Hook sources require canonical event registration in {registration}")

    if config is not None and sources:
        tokens: set[str] = set()

        for groups in config.hooks.values():
            for group in groups:
                for handler in group.hooks:
                    lexer = shlex(handler.command, posix=True, punctuation_chars=True)
                    lexer.whitespace_split = True

                    try:
                        tokens.update(lexer)
                    except ValueError as exc:
                        raise AgentSyncError(f"Invalid hook command in {registration}: {exc}") from exc

        registered: set[str] = set()

        for source in sources:
            canonical_path = source.path.relative_to(workspace.root).as_posix()

            references = {
                canonical_path,
                f"./{canonical_path}",
                str(source.path),
                f"$(git rev-parse --show-toplevel)/{canonical_path}",
            }

            if tokens & references:
                registered.add(source.relative_path.parts[0])

        missing = sorted({source.relative_path.parts[0] for source in sources} - registered)

        if missing:
            raise AgentSyncError(
                f"Unregistered hooks in {registration}: {', '.join(missing)}. "
                "Register a command referencing an entrypoint in each canonical hook file or folder."
            )

    return sources, config


def load_markdown_sources[T: BaseModel](
    workspace: Workspace,
    directory_name: str,
    model: type[T],
) -> list[tuple[Path, str, T, str]]:
    """Load typed Markdown documents from one source directory."""

    directory = agents_dir(workspace) / directory_name

    if not directory.exists():
        return []

    sources: list[tuple[Path, str, T, str]] = []

    for path in sorted(directory.glob("*.md")):
        slug = validate_slug(path.stem, path)
        content = read_optional_text(path)

        if content is not None:
            front_matter, body = parse_markdown(content, model, str(path))
            sources.append((path, slug, front_matter, body))

    return sources
