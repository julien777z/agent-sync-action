import yaml

from agent_sync.models.json_types import JsonObject, JsonValue


class FrontMatterDumper(yaml.SafeDumper):
    """SafeDumper variant that renders multiline strings as literal blocks."""


def represent_multiline_str(dumper: yaml.SafeDumper, value: str) -> yaml.ScalarNode:
    """Render strings containing newlines with literal block style."""

    style = "|" if "\n" in value else None

    return dumper.represent_scalar("tag:yaml.org,2002:str", value, style=style)


FrontMatterDumper.add_representer(str, represent_multiline_str)


def ensure_trailing_newline(text: str) -> str:
    """Return text with a guaranteed single trailing newline."""

    return text if text.endswith("\n") else text + "\n"


def normalize_text(value: object) -> str:
    """Return a stripped string, or empty string for non-string input."""

    if not isinstance(value, str):
        return ""

    return value.strip()


def nonempty_str(value: object) -> str | None:
    """Return value when it is a non-empty string, else None."""

    return value if isinstance(value, str) and value else None


def derive_description(content: str) -> str:
    """Extract a description, preferring the first non-header line then the first header."""

    first_header: str | None = None
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("#"):
            if first_header is None:
                first_header = " ".join(line.lstrip("#").strip().split())
            continue

        return " ".join(line.split())

    return first_header if first_header is not None else "Project conventions."


def yaml_quote(value: str) -> str:
    """Return a double-quoted YAML scalar with backslashes and quotes escaped."""

    escaped = value.replace("\\", "\\\\").replace('"', '\\"')

    return f'"{escaped}"'


def render_front_matter(front_matter: JsonObject, body: str) -> str:
    """Serialize a dict as YAML front matter wrapped in --- delimiters above the body."""

    if front_matter:
        front = yaml.dump(
            front_matter,
            Dumper=FrontMatterDumper,
            sort_keys=False,
            default_flow_style=False,
            width=10_000,
            allow_unicode=True,
        ).strip()
    else:
        front = ""

    output = f"---\n{front}\n---\n"
    if body:
        output += "\n" + body

    return ensure_trailing_newline(output)


def normalize_rule_source(front_matter: JsonObject, body: str) -> str:
    """Rebuild a rule source file with unified, deterministically ordered front matter."""

    normalized: JsonObject = {}
    for key in ("description", "globs"):
        value: JsonValue = front_matter.get(key)
        if value:
            normalized[key] = value

    always_apply = front_matter.get("alwaysApply")
    normalized["alwaysApply"] = always_apply if isinstance(always_apply, bool) else True

    starlark = front_matter.get("starlark")
    if isinstance(starlark, str) and starlark.strip():
        normalized["starlark"] = starlark

    known_keys = {"name", "description", "globs", "alwaysApply", "starlark"}
    for key in sorted(set(front_matter) - known_keys):
        normalized[key] = front_matter[key]

    return render_front_matter(normalized, body)


def assemble_codex_skill(body: str, name: str, description: str) -> str:
    """Build a Codex SKILL.md file with name/description front matter."""

    front_matter = (
        "---\n"
        f"name: {yaml_quote(name)}\n"
        f"description: {yaml_quote(description)}\n"
        "---\n\n"
    )

    return front_matter + ensure_trailing_newline(body)
