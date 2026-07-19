from agent_sync.generation.agent import generate_agent_outputs
from agent_sync.generation.command import generate_command_outputs
from agent_sync.generation.hook import generate_hook_outputs
from agent_sync.generation.rule import generate_rule_outputs
from agent_sync.generation.setting import generate_setting_outputs
from agent_sync.generation.skill import generate_skill_outputs
from agent_sync.models.configuration import CanonicalConfiguration
from agent_sync.models.output import ArtifactKind, GeneratedFile, Manifest
from agent_sync.workspace import Workspace


def generate_manifest(
    workspace: Workspace,
    configuration: CanonicalConfiguration,
) -> Manifest:
    """Generate the complete desired provider-output manifest."""

    outputs = [
        *generate_skill_outputs(workspace),
        *generate_command_outputs(workspace),
        *generate_agent_outputs(workspace, configuration),
        *generate_rule_outputs(workspace),
        *generate_hook_outputs(workspace),
    ]
    instructions = next(
        output
        for output in outputs
        if isinstance(output, GeneratedFile) and output.artifact is ArtifactKind.INSTRUCTIONS
    )
    outputs.extend(generate_setting_outputs(workspace, configuration, instructions))

    return Manifest(outputs=outputs)
