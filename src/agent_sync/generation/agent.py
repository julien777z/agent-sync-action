from agent_sync.document import render_front_matter
from agent_sync.generation.context import GenerationContext
from agent_sync.models.output import ArtifactKind, GeneratedFile, GeneratedOutput, Provider
from agent_sync.models.provider import PROVIDER_LAYOUTS
from agent_sync.source import resolve_agent_model


def generate_agents(context: GenerationContext, provider: Provider) -> list[GeneratedOutput]:
    """Generate one provider's agent files with resolved models."""

    outputs: list[GeneratedOutput] = []
    root = PROVIDER_LAYOUTS[provider].root(context.workspace.root)

    for source in context.agents:
        front_matter = source.front_matter.model_copy(
            update={"model": resolve_agent_model(source.slug, provider, context.configuration)}
        )

        outputs.append(
            GeneratedFile(
                target_path=root / "agents" / f"{source.slug}.md",
                content=render_front_matter(front_matter, source.body),
                artifact=ArtifactKind.AGENT,
                source_path=source.path,
                provider=provider,
            )
        )

    return outputs
