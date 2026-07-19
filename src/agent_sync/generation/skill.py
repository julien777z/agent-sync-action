from agent_sync.generation.context import GenerationContext
from agent_sync.models.output import ArtifactKind, GeneratedLink, GeneratedOutput
from agent_sync.models.provider import PROVIDER_LAYOUTS
from agent_sync.models.output import Provider


def generate_skills(context: GenerationContext, provider: Provider) -> list[GeneratedOutput]:
    """Generate one provider's skill links."""

    root = PROVIDER_LAYOUTS[provider].root(context.workspace.root)

    return [
        GeneratedLink(
            target_path=root / "skills" / source.slug,
            link_target=source.directory,
            artifact=ArtifactKind.SKILL,
            source_path=source.path,
            provider=provider,
        )
        for source in context.skills
    ]
