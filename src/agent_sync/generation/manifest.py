from agent_sync.configuration import CanonicalConfiguration
from agent_sync.generation.context import load_generation_context
from agent_sync.generation.registry import ARTIFACT_REGISTRY
from agent_sync.generation.rule import generate_shared_rule_outputs
from agent_sync.models.output import ArtifactKind, GeneratedFile, Manifest
from agent_sync.workspace import Workspace


def generate_manifest(
    workspace: Workspace,
    configuration: CanonicalConfiguration,
) -> Manifest:
    """Generate the complete desired provider-output manifest."""

    context = load_generation_context(workspace, configuration)
    shared_outputs = generate_shared_rule_outputs(context)
    instructions = next(
        output
        for output in shared_outputs
        if isinstance(output, GeneratedFile) and output.artifact is ArtifactKind.INSTRUCTIONS
    )

    context = context.model_copy(update={"instructions": instructions.content})

    provider_outputs = [
        output
        for registration in ARTIFACT_REGISTRY.values()
        for provider, handler in registration["handlers"].items()
        for output in handler(context, provider)
    ]

    return Manifest(outputs=[*shared_outputs, *provider_outputs])
