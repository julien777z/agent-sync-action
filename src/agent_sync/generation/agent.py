from agent_sync.document import parse_markdown, render_front_matter
from agent_sync.models.configuration import CanonicalConfiguration
from agent_sync.models.document import AgentFrontMatter
from agent_sync.models.output import ArtifactKind, GeneratedFile, GeneratedOutput, Provider
from agent_sync.models.provider import PROVIDER_LAYOUTS
from agent_sync.slug import validate_slug
from agent_sync.source import resolve_agent_model
from agent_sync.workspace import Workspace

AGENT_PROVIDERS = (Provider.CLAUDE, Provider.CURSOR)


def generate_agent_outputs(
    workspace: Workspace,
    configuration: CanonicalConfiguration,
) -> list[GeneratedOutput]:
    """Generate provider agent files with resolved model settings."""

    outputs: list[GeneratedOutput] = []
    agents_dir = workspace.agents_dir / "agents"
    if not agents_dir.exists():
        return outputs

    for path in sorted(agents_dir.glob("*.md")):
        slug = validate_slug(path.stem, path)
        content = workspace.read_text(path)
        if content is None:
            continue

        front_matter, body = parse_markdown(content, AgentFrontMatter, str(path))
        base_values = front_matter.model_dump(exclude={"model"}, exclude_none=True)
        for provider in AGENT_PROVIDERS:
            provider_values = dict(base_values)
            model = resolve_agent_model(slug, provider, configuration)
            if model:
                provider_values["model"] = model

            outputs.append(
                GeneratedFile(
                    target_path=(
                        PROVIDER_LAYOUTS[provider].root(workspace.root) / "agents" / f"{slug}.md"
                    ),
                    content=render_front_matter(provider_values, body),
                    artifact=ArtifactKind.AGENT,
                    source_path=path,
                    provider=provider,
                )
            )

    return outputs
