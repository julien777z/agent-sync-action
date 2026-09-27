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
from agent_sync.utils import ensure_trailing_newline, serialized_field_names

logger = logging.getLogger(__name__)

DISCARDED_RULE_KEYS: Final[frozenset[str]] = frozenset({"name"})


def normalize_rule(front_matter: RuleFrontMatter, body: str) -> str:
    """Render a rule with deterministic source front matter."""

    values = FrontMatterValues.model_validate(front_matter.model_dump(by_alias=True, exclude_none=True)).root

    declared_keys = serialized_field_names(RuleFrontMatter)
    normalized = {
        key: values[key] for key in declared_keys if key in values and values[key] not in (None, "")
    }

    for key in sorted(set(values) - set(declared_keys) - DISCARDED_RULE_KEYS):
        normalized[key] = values[key]

    return render_front_matter(normalized, body)


def generate_shared_rule_outputs(context: GenerationContext) -> list[GeneratedOutput]:
    """Generate root instructions without changing canonical rules."""

    sections = [
        render_instruction_section(source.path.relative_to(context.workspace.root), source.body)
        for source in context.rules
        if source.body and source.front_matter.always_apply
    ]
    pointers = [
        render_rule_pointer(source.path.relative_to(context.workspace.root), source.front_matter)
        for source in context.rules
        if source.body and not source.front_matter.always_apply
    ]
    scoped_rules = "## Scoped rules\n\n" + "\n".join(pointers) if pointers else ""
    content = render_instructions(
        [
            part
            for part in (context.global_instructions, *sections, context.project_instructions, scoped_rules)
            if part
        ],
        context.workspace.agents_dir.relative_to(context.workspace.root).as_posix(),
    )
    if not content:
        return []

    return [
        GeneratedFile(
            target_path=context.workspace.root / "AGENTS.md",
            content=content,
            artifact=ArtifactKind.INSTRUCTIONS,
            source_path=context.workspace.agents_dir / "rules",
        )
    ]


def generate_rule_mirrors(
    context: GenerationContext,
    provider: Provider,
) -> list[GeneratedOutput]:
    """Link scoped rules when their provider metadata is already canonical."""

    scope_key = "paths" if provider is Provider.CLAUDE else "globs"
    outputs: list[GeneratedOutput] = []
    for source in context.rules:
        if not source.body or source.front_matter.always_apply:
            continue

        target = (
            provider.root(context.workspace.output_root) / "rules" / f"{source.slug}{provider.rule_extension}"
        )
        scope = getattr(source.front_matter, scope_key)
        if scope is not None or (source.front_matter.globs is None and source.front_matter.paths is None):
            outputs.append(
                GeneratedLink(
                    target_path=target,
                    link_target=source.path,
                    artifact=ArtifactKind.RULE,
                    source_path=source.path,
                    provider=provider,
                )
            )
            continue

        outputs.append(
            GeneratedFile(
                target_path=target,
                content=normalize_rule(
                    source.front_matter.model_copy(update={scope_key: source.front_matter.scope_patterns}),
                    f"<!-- {GENERATED_FILE_NOTICE} -->\n\n{source.body}",
                ),
                artifact=ArtifactKind.RULE,
                source_path=source.path,
                provider=provider,
            )
        )

    return outputs


def generate_codex_rules(
    context: GenerationContext,
    provider: Provider,
) -> list[GeneratedOutput]:
    """Generate Codex Starlark rule files."""

    root = provider.root(context.workspace.output_root)

    return [
        GeneratedFile(
            target_path=root / "rules" / f"{source.slug}.rules",
            content=ensure_trailing_newline(
                f"# {GENERATED_FILE_NOTICE}\n"
                f"# Source: {source.path.relative_to(context.workspace.root).as_posix()}\n"
                f"{source.front_matter.starlark.strip()}"
            ),
            artifact=ArtifactKind.RULE,
            source_path=source.path,
            provider=provider,
        )
        for source in context.rules
        if source.front_matter.starlark and source.front_matter.starlark.strip()
    ]


def render_instruction_section(path: Path, body: str) -> str:
    """Render one canonical rule inside the generated root instructions."""

    return f"<!-- Source: {path.as_posix()} -->\n\n{body}"


def render_rule_pointer(path: Path, front_matter: RuleFrontMatter) -> str:
    """Tell Codex when to read one scoped canonical rule."""

    source = f"`{path.as_posix()}`"
    description = front_matter.description or path.stem.replace("-", " ")
    patterns = front_matter.scope_patterns
    if patterns:
        scope = ", ".join(f"`{pattern}`" for pattern in patterns)
        return f"- Read {source} for files matching {scope}: {description}"
    return f"- Read {source} when its topic is relevant: {description}"


def render_instructions(sections: list[str], agents_dirname: str) -> str:
    """Render the root instruction document from canonical rule sections."""

    if not sections:
        return ""

    header = f"# AGENTS.md\n\n{GENERATED_FILE_NOTICE}\n\nCanonical guidance lives in `{agents_dirname}/`.\n"

    content = header + "\n" + "\n\n".join(sections)

    return ensure_trailing_newline(content)
