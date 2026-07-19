from agent_sync.document import (
    ensure_trailing_newline,
    normalize_text,
    parse_markdown,
    render_front_matter,
)
from agent_sync.models.document import CommandFrontMatter
from agent_sync.models.output import ArtifactKind, GeneratedFile, GeneratedOutput, Provider
from agent_sync.models.provider import PROVIDER_LAYOUTS
from agent_sync.slug import validate_slug
from agent_sync.workspace import Workspace

COMMAND_PROVIDERS = (Provider.CLAUDE, Provider.CURSOR)


def generate_command_outputs(workspace: Workspace) -> list[GeneratedOutput]:
    """Generate provider command files from canonical command documents."""

    outputs: list[GeneratedOutput] = []
    commands_dir = workspace.agents_dir / "commands"
    if not commands_dir.exists():
        return outputs

    for path in sorted(commands_dir.glob("*.md")):
        slug = validate_slug(path.stem, path)
        content = workspace.read_text(path)
        if content is None:
            continue

        front_matter, body = parse_markdown(content, CommandFrontMatter, str(path))
        variants = front_matter.variants or {}
        claude_front_matter = front_matter.model_dump(
            by_alias=True,
            exclude_none=True,
            exclude={"variants"},
        )
        for provider in COMMAND_PROVIDERS:
            provider_body = normalize_text(variants.get(provider.value, body) or body)
            rendered = (
                render_front_matter(claude_front_matter, provider_body)
                if provider is Provider.CLAUDE and claude_front_matter
                else ensure_trailing_newline(provider_body)
            )
            outputs.append(
                GeneratedFile(
                    target_path=(
                        PROVIDER_LAYOUTS[provider].root(workspace.root) / "commands" / f"{slug}.md"
                    ),
                    content=rendered,
                    artifact=ArtifactKind.COMMAND,
                    source_path=path,
                    provider=provider,
                )
            )

    return outputs
