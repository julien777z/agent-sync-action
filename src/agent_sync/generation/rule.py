import logging
from pathlib import Path
from typing import Final

from agent_sync.document import FrontMatterValues, render_front_matter
from agent_sync.generation.artifact import GENERATED_FILE_NOTICE
from agent_sync.generation.context import GenerationContext
from agent_sync.models.document import RuleFrontMatter
from agent_sync.models.output import (
    ArtifactKind,
    GeneratedFile,
    GeneratedLink,
    GeneratedOutput,
    Provider,
)
from agent_sync.providers import PROVIDER_LAYOUTS
from agent_sync.utils import ensure_trailing_newline, serialized_field_names

logger = logging.getLogger(__name__)

# A rule is identified by its filename slug, so an authored name never persists.
DISCARDED_RULE_KEYS: Final[frozenset[str]] = frozenset({"name"})


def normalize_rule(front_matter: RuleFrontMatter, body: str) -> str:
    """Render a rule with deterministic source front matter."""

    values = FrontMatterValues.model_validate(
        front_matter.model_dump(by_alias=True, exclude_none=True)
    ).root

    declared_keys = serialized_field_names(RuleFrontMatter)
    normalized = {
        key: values[key] for key in declared_keys if key in values and values[key] not in (None, "")
    }

    for key in sorted(set(values) - set(declared_keys) - DISCARDED_RULE_KEYS):
        normalized[key] = values[key]

    return render_front_matter(normalized, body)


def generate_shared_rule_outputs(context: GenerationContext) -> list[GeneratedOutput]:
    """Generate normalized rule sources and root instructions."""

    outputs: list[GeneratedOutput] = [
        GeneratedFile(
            target_path=source.path,
            content=normalize_rule(source.front_matter, source.body),
            artifact=ArtifactKind.RULE,
            source_path=source.path,
        )
        for source in context.rules
        if source.body
    ]

    outputs.append(
        GeneratedFile(
            target_path=context.workspace.root / "AGENTS.md",
            content=render_instructions(
                [
                    render_instruction_section(
                        source.path,
                        source.front_matter,
                        source.body,
                    )
                    for source in context.rules
                    if source.body
                ]
            ),
            artifact=ArtifactKind.INSTRUCTIONS,
            source_path=context.workspace.agents_dir / "rules",
        )
    )

    return outputs


def generate_rule_links(
    context: GenerationContext,
    provider: Provider,
) -> list[GeneratedOutput]:
    """Generate one provider's rule links."""

    return [
        GeneratedLink(
            target_path=(
                PROVIDER_LAYOUTS[provider].root(context.workspace.root)
                / "rules"
                / f"{source.slug}{PROVIDER_LAYOUTS[provider].rule_extension}"
            ),
            link_target=source.path,
            artifact=ArtifactKind.RULE,
            source_path=source.path,
            provider=provider,
        )
        for source in context.rules
        if source.body
    ]


def generate_codex_rules(
    context: GenerationContext,
    provider: Provider,
) -> list[GeneratedOutput]:
    """Generate Codex Starlark rule files."""

    root = PROVIDER_LAYOUTS[provider].root(context.workspace.root)

    return [
        GeneratedFile(
            target_path=root / "rules" / f"{source.slug}.rules",
            content=ensure_trailing_newline(
                f"# {GENERATED_FILE_NOTICE}\n"
                f"# Source: .agents/rules/{source.path.name}\n"
                f"{source.front_matter.starlark.strip()}"
            ),
            artifact=ArtifactKind.RULE,
            source_path=source.path,
            provider=provider,
        )
        for source in context.rules
        if source.front_matter.starlark and source.front_matter.starlark.strip()
    ]


def render_instruction_section(
    path: Path,
    front_matter: RuleFrontMatter,
    body: str,
) -> str:
    """Render one canonical rule inside the generated root instructions."""

    scope = ""
    patterns = front_matter.scope_patterns

    if patterns:
        scope = "> Applies only to files matching: " + ", ".join(
            f"`{pattern}`" for pattern in patterns
        )
    elif not front_matter.always_apply:
        scope = "> Apply this rule only when it is explicitly relevant to the current task."

    return "\n\n".join(
        part for part in (f"<!-- Source: .agents/rules/{path.name} -->", scope, body) if part
    )


def render_instructions(sections: list[str]) -> str:
    """Render the root instruction document from canonical rule sections."""

    header = (
        "# AGENTS.md\n\n"
        f"{GENERATED_FILE_NOTICE}\n\n"
        "The canonical project rules live in `.agents/rules/`.\n"
    )

    content = header if not sections else header + "\n" + "\n\n".join(sections)

    return ensure_trailing_newline(content)
