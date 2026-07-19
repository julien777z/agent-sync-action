import yaml
from pydantic import BaseModel, ValidationError

from agent_sync.errors import AgentSyncError


class FrontMatterDumper(yaml.SafeDumper):
    """Render multiline strings as YAML literal blocks."""


def represent_multiline_string(
    dumper: yaml.SafeDumper,
    value: str,
) -> yaml.ScalarNode:
    """Render a string with a suitable YAML scalar style."""

    style = "|" if "\n" in value else None

    # PyYAML's untyped value parameter makes this otherwise precise call partially unknown.
    return dumper.represent_scalar(  # pyright: ignore[reportUnknownMemberType]
        "tag:yaml.org,2002:str",
        value,
        style=style,
    )


FrontMatterDumper.add_representer(str, represent_multiline_string)


def ensure_trailing_newline(text: str) -> str:
    """Return text with a trailing newline."""

    return text if text.endswith("\n") else text + "\n"


def normalize_text(value: object) -> str:
    """Return normalized text or an empty string for another value type."""

    if not isinstance(value, str):
        return ""

    return value.strip()


def parse_markdown[T: BaseModel](content: str, model: type[T], source: str) -> tuple[T, str]:
    """Parse and validate a canonical Markdown document."""

    raw_front_matter: object = {}
    body = content
    lines = content.splitlines()
    if lines and lines[0] == "---":
        try:
            end_index = lines[1:].index("---") + 1
        except ValueError as exc:
            raise AgentSyncError(f"Unterminated front matter in {source}") from exc

        front_matter_content = "\n".join(lines[1:end_index]).strip()
        body = "\n".join(lines[end_index + 1 :])
        if front_matter_content:
            try:
                raw_front_matter = yaml.safe_load(front_matter_content) or {}
            except yaml.YAMLError as exc:
                raise AgentSyncError(f"Invalid YAML front matter in {source}: {exc}") from exc

    if not isinstance(raw_front_matter, dict):
        raise AgentSyncError(f"Front matter in {source} must be a mapping")

    try:
        front_matter = model.model_validate(raw_front_matter)
    except ValidationError as exc:
        raise AgentSyncError(f"Invalid front matter in {source}: {exc}") from exc

    return front_matter, normalize_text(body)


def render_front_matter(front_matter: BaseModel | dict[str, object], body: str) -> str:
    """Render validated YAML front matter followed by a Markdown body."""

    if isinstance(front_matter, BaseModel):
        values = front_matter.model_dump(
            by_alias=True,
            exclude_none=True,
            exclude={"variants"},
        )
    else:
        values = front_matter

    rendered = (
        yaml.dump(
            values,
            Dumper=FrontMatterDumper,
            sort_keys=False,
            default_flow_style=False,
            width=10_000,
            allow_unicode=True,
        ).strip()
        if values
        else ""
    )
    output = f"---\n{rendered}\n---\n"
    if body:
        output += f"\n{body}"

    return ensure_trailing_newline(output)


def normalize_rule(front_matter: BaseModel, body: str) -> str:
    """Render a rule with deterministic canonical front matter."""

    values = front_matter.model_dump(by_alias=True, exclude_none=True)
    known_keys = ("description", "globs", "alwaysApply", "starlark")
    normalized = {
        key: values[key] for key in known_keys if key in values and values[key] not in (None, "")
    }
    for key in sorted(set(values) - set(known_keys) - {"name"}):
        normalized[key] = values[key]

    return render_front_matter(normalized, body)
