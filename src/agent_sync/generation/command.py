from agent_sync.document import (
    ensure_trailing_newline,
    render_front_matter,
)
from agent_sync.generation.context import CommandSource, GenerationContext
from agent_sync.models.output import ArtifactKind, GeneratedFile, GeneratedOutput, Provider
from agent_sync.models.provider import PROVIDER_LAYOUTS


def generate_claude_commands(
    context: GenerationContext,
    provider: Provider,
) -> list[GeneratedOutput]:
    """Generate Claude commands with supported front matter."""

    return [generate_claude_command(context, provider, source) for source in context.commands]


def generate_claude_command(
    context: GenerationContext,
    provider: Provider,
    source: CommandSource,
) -> GeneratedFile:
    """Generate one Claude command."""

    front_matter = source.front_matter.model_dump(
        by_alias=True,
        exclude_none=True,
        exclude={"variants"},
    )
    body = command_body(source, provider)

    return GeneratedFile(
        target_path=(
            PROVIDER_LAYOUTS[provider].root(context.workspace.root)
            / "commands"
            / f"{source.slug}.md"
        ),
        content=(
            render_front_matter(front_matter, body)
            if front_matter
            else ensure_trailing_newline(body)
        ),
        artifact=ArtifactKind.COMMAND,
        source_path=source.path,
        provider=provider,
    )


def generate_cursor_commands(
    context: GenerationContext,
    provider: Provider,
) -> list[GeneratedOutput]:
    """Generate plain Cursor command files."""

    root = PROVIDER_LAYOUTS[provider].root(context.workspace.root)
    return [
        GeneratedFile(
            target_path=root / "commands" / f"{source.slug}.md",
            content=ensure_trailing_newline(command_body(source, provider)),
            artifact=ArtifactKind.COMMAND,
            source_path=source.path,
            provider=provider,
        )
        for source in context.commands
    ]


def command_body(source: CommandSource, provider: Provider) -> str:
    """Resolve one provider's command body."""

    variants = source.front_matter.variants or {}

    return (variants.get(provider.value) or source.body).strip()
