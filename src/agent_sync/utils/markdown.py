import yaml


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


def render_front_matter(front_matter: dict, body: str) -> str:
    """Serialize a dict as YAML front matter wrapped in --- delimiters above the body."""

    if front_matter:
        front = yaml.safe_dump(
            front_matter,
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


def assemble_cursor_rule(body: str, always_apply: bool) -> str:
    """Build a Cursor .mdc file with alwaysApply front matter."""

    front_matter = "---\n" + f"alwaysApply: {str(always_apply).lower()}" + "\n---\n\n"

    return front_matter + ensure_trailing_newline(body)


def assemble_codex_skill(body: str, name: str, description: str) -> str:
    """Build a Codex SKILL.md file with name/description front matter."""

    front_matter = "---\n" f"name: {yaml_quote(name)}\n" f"description: {yaml_quote(description)}\n" "---\n\n"

    return front_matter + ensure_trailing_newline(body)
