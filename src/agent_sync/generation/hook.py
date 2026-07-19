from agent_sync.generation.context import GenerationContext
from agent_sync.models.output import ArtifactKind, GeneratedFile, GeneratedOutput, Provider
from agent_sync.models.provider import PROVIDER_LAYOUTS
from agent_sync.utils import ensure_trailing_newline


def generate_hooks(context: GenerationContext, provider: Provider) -> list[GeneratedOutput]:
    """Generate one provider's hook files."""

    root = PROVIDER_LAYOUTS[provider].root(context.workspace.root)

    return [
        GeneratedFile(
            target_path=root / "hooks" / source.path.name,
            content=ensure_trailing_newline(source.content),
            artifact=ArtifactKind.HOOK,
            source_path=source.path,
            provider=provider,
            executable=source.executable,
        )
        for source in context.hooks
    ]
