import json
import logging

from agent_sync.constants import CODEX_RULE_MARKER
from agent_sync.loaders import parse_markdown_file, resolve_agent_model, settings_dir
from agent_sync.models.front_matter import (
    AgentFrontMatter,
    CommandFrontMatter,
    RuleFrontMatter,
    SkillFrontMatter,
)
from agent_sync.models.outputs import OutputFile
from agent_sync.utils import fs
from agent_sync.utils.markdown import (
    assemble_codex_skill,
    assemble_cursor_rule,
    derive_description,
    ensure_trailing_newline,
    nonempty_str,
    normalize_text,
    render_front_matter,
)
from agent_sync.utils.slugs import SAFE_SLUG_PATTERN, slug_to_codex_name, validate_slug

logger = logging.getLogger(__name__)


def generate_outputs(
    platform_settings: dict[str, dict],
    agent_model_overrides: dict[str, dict[str, str]],
) -> list[OutputFile]:
    """Generate all output files from .agents sources."""

    outputs: list[OutputFile] = []
    outputs.extend(generate_skill_outputs())
    outputs.extend(generate_command_outputs())
    outputs.extend(generate_agent_outputs(platform_settings, agent_model_overrides))
    outputs.extend(generate_rule_outputs())
    outputs.extend(generate_hook_outputs())
    outputs.extend(generate_settings_outputs(platform_settings))

    return outputs


def generate_skill_outputs() -> list[OutputFile]:
    """Sync .agents/skills/<slug>/SKILL.md to .claude/skills/, .cursor/skills/, and .codex/skills/."""

    outputs: list[OutputFile] = []
    skills_dir = fs.agents_dir() / "skills"
    if not skills_dir.exists():
        return outputs

    for skill_dir in sorted(skills_dir.iterdir()):
        if not skill_dir.is_dir():
            continue

        slug = validate_slug(skill_dir.name, skill_dir)
        source_path = skill_dir / "SKILL.md"
        if not source_path.exists():
            logger.warning("Missing SKILL.md in %s.", skill_dir)
            continue

        front_matter, content = parse_markdown_file(source_path, SkillFrontMatter)
        source_content = fs.read_text(source_path) or ""

        codex_name = nonempty_str(front_matter.get("name")) or slug_to_codex_name(slug)
        if not SAFE_SLUG_PATTERN.match(codex_name):
            logger.warning(
                "Invalid codex skill name '%s' in %s; using '%s'.",
                codex_name,
                source_path,
                slug_to_codex_name(slug),
            )
            codex_name = slug_to_codex_name(slug)

        codex_description = nonempty_str(front_matter.get("description")) or derive_description(content)

        skill_dirs = (("cursor", slug), ("claude", slug), ("codex", codex_name))

        skill_md_content = {
            "cursor": ensure_trailing_newline(source_content),
            "claude": ensure_trailing_newline(source_content),
            "codex": assemble_codex_skill(content, codex_name, codex_description),
        }
        for platform, dir_name in skill_dirs:
            outputs.append(
                OutputFile(
                    target_path=fs.root() / f".{platform}" / "skills" / dir_name / "SKILL.md",
                    content=skill_md_content[platform],
                    kind=f"{platform}_skill",
                    slug=slug,
                    source_path=source_path,
                )
            )

        for asset_path in sorted(skill_dir.rglob("*")):
            if not asset_path.is_file() or asset_path.name == "SKILL.md":
                continue
            asset_content = fs.read_text(asset_path)
            if asset_content is None:
                continue
            relative = asset_path.relative_to(skill_dir)
            for platform, dir_name in skill_dirs:
                outputs.append(
                    OutputFile(
                        target_path=fs.root() / f".{platform}" / "skills" / dir_name / relative,
                        content=ensure_trailing_newline(asset_content),
                        kind=f"{platform}_skill_asset",
                        slug=slug,
                        source_path=asset_path,
                    )
                )

    return outputs


def generate_command_outputs() -> list[OutputFile]:
    """Generate Claude and Cursor command files for each command markdown file."""

    outputs: list[OutputFile] = []
    commands_dir = fs.agents_dir() / "commands"
    if not commands_dir.exists():
        return outputs

    for path in sorted(commands_dir.glob("*.md")):
        slug = validate_slug(path.stem, path)
        front_matter, content = parse_markdown_file(path, CommandFrontMatter)
        raw_variants = front_matter.get("variants")
        variants = raw_variants if isinstance(raw_variants, dict) else {}

        claude_body = normalize_text(variants.get("claude", content) or content)
        cursor_body = normalize_text(variants.get("cursor", content) or content)
        claude_front_matter = dict(front_matter)
        claude_front_matter.pop("variants", None)

        if claude_front_matter:
            claude_output = render_front_matter(claude_front_matter, claude_body)
        else:
            claude_output = ensure_trailing_newline(claude_body)

        outputs.append(
            OutputFile(
                target_path=fs.root() / ".claude" / "commands" / f"{slug}.md",
                content=claude_output,
                kind="claude_command",
                slug=slug,
                source_path=path,
            )
        )
        outputs.append(
            OutputFile(
                target_path=fs.root() / ".cursor" / "commands" / f"{slug}.md",
                content=ensure_trailing_newline(cursor_body),
                kind="cursor_command",
                slug=slug,
                source_path=path,
            )
        )

    return outputs


def generate_agent_outputs(
    platform_settings: dict[str, dict],
    agent_model_overrides: dict[str, dict[str, str]],
) -> list[OutputFile]:
    """Generate Claude and Cursor agent files with per-platform model resolution."""

    outputs: list[OutputFile] = []
    agents_subdir = fs.agents_dir() / "agents"
    if not agents_subdir.exists():
        return outputs

    for path in sorted(agents_subdir.glob("*.md")):
        slug = validate_slug(path.stem, path)
        front_matter, content = parse_markdown_file(path, AgentFrontMatter)
        source_front_matter = dict(front_matter)
        source_front_matter.pop("model", None)

        for platform in ("claude", "cursor"):
            platform_front_matter = dict(source_front_matter)
            model = resolve_agent_model(slug, platform, platform_settings, agent_model_overrides)
            if model:
                platform_front_matter["model"] = model

            agent_content = render_front_matter(platform_front_matter, content)
            outputs.append(
                OutputFile(
                    target_path=fs.root() / f".{platform}" / "agents" / f"{slug}.md",
                    content=agent_content,
                    kind=f"{platform}_agent",
                    slug=slug,
                    source_path=path,
                )
            )

    return outputs


def generate_rule_outputs() -> list[OutputFile]:
    """Sync .agents/rules/<name>.md to .claude/rules/*.md, .cursor/rules/*.mdc, and Starlark .codex/rules/*.rules."""

    outputs: list[OutputFile] = []
    rules_dir = fs.agents_dir() / "rules"
    if not rules_dir.exists():
        return outputs

    for path in sorted(rules_dir.glob("*.md")):
        slug = validate_slug(path.stem, path)
        front_matter, body = parse_markdown_file(path, RuleFrontMatter)
        if body.strip():
            outputs.append(
                OutputFile(
                    target_path=fs.root() / ".claude" / "rules" / f"{slug}.md",
                    content=ensure_trailing_newline(body),
                    kind="claude_rule",
                    slug=slug,
                    source_path=path,
                )
            )
            outputs.append(
                OutputFile(
                    target_path=fs.root() / ".cursor" / "rules" / f"{slug}.mdc",
                    content=assemble_cursor_rule(body, always_apply=True),
                    kind="cursor_rule",
                    slug=slug,
                    source_path=path,
                )
            )

        starlark = front_matter.get("starlark")
        if isinstance(starlark, str) and starlark.strip():
            content = f"{CODEX_RULE_MARKER}{path.name}\n{starlark.strip()}"
            outputs.append(
                OutputFile(
                    target_path=fs.root() / ".codex" / "rules" / f"{slug}.rules",
                    content=ensure_trailing_newline(content),
                    kind="codex_rule",
                    slug=slug,
                    source_path=path,
                )
            )

    return outputs


def generate_hook_outputs() -> list[OutputFile]:
    """Sync .agents/hooks/* scripts to .claude/hooks/ and .cursor/hooks/."""

    outputs: list[OutputFile] = []
    hooks_dir = fs.agents_dir() / "hooks"
    if not hooks_dir.exists():
        return outputs

    for path in sorted(hooks_dir.iterdir()):
        if not path.is_file():
            continue
        content = fs.read_text(path)
        if content is None:
            continue
        for platform in ("claude", "cursor"):
            outputs.append(
                OutputFile(
                    target_path=fs.root() / f".{platform}" / "hooks" / path.name,
                    content=ensure_trailing_newline(content),
                    kind=f"{platform}_hook",
                    slug=path.stem,
                    source_path=path,
                )
            )

    return outputs


def generate_settings_outputs(platform_settings: dict[str, dict]) -> list[OutputFile]:
    """Sync .agents/settings/claude.json verbatim to .claude/settings.json."""

    outputs: list[OutputFile] = []
    claude_settings = platform_settings.get("claude")
    if claude_settings is None:
        return outputs

    outputs.append(
        OutputFile(
            target_path=fs.root() / ".claude" / "settings.json",
            content=ensure_trailing_newline(json.dumps(claude_settings, indent=2)),
            kind="claude_settings",
            slug="claude",
            source_path=settings_dir() / "claude.json",
        )
    )

    return outputs
