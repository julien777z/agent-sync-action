from agent_sync.document import ensure_trailing_newline
from agent_sync.models.output import ArtifactKind, GeneratedFile, GeneratedOutput, Provider
from agent_sync.models.provider import PROVIDER_LAYOUTS
from agent_sync.workspace import Workspace

HOOK_PROVIDERS = (Provider.CLAUDE, Provider.CURSOR)


def generate_hook_outputs(workspace: Workspace) -> list[GeneratedOutput]:
    """Generate provider hook files from canonical scripts."""

    outputs: list[GeneratedOutput] = []
    hooks_dir = workspace.agents_dir / "hooks"
    if not hooks_dir.exists():
        return outputs

    for path in sorted(hooks_dir.iterdir()):
        if not path.is_file():
            continue

        content = workspace.read_text(path)
        if content is None:
            continue

        executable = path.suffix == ".sh" or content.startswith("#!")
        for provider in HOOK_PROVIDERS:
            outputs.append(
                GeneratedFile(
                    target_path=(
                        PROVIDER_LAYOUTS[provider].root(workspace.root) / "hooks" / path.name
                    ),
                    content=ensure_trailing_newline(content),
                    artifact=ArtifactKind.HOOK,
                    source_path=path,
                    provider=provider,
                    executable=executable,
                )
            )

    return outputs
