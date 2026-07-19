import logging

import yaml
from pydantic import BaseModel, JsonValue, RootModel, ValidationError

from agent_sync.errors import AgentSyncError
from agent_sync.utils import ensure_trailing_newline

logger = logging.getLogger(__name__)


class FrontMatterValues(RootModel[dict[str, JsonValue]]):
    """Validate recursive YAML values supported by front matter."""


type YamlMapping = dict[str, JsonValue]


def parse_markdown[T: BaseModel](content: str, model: type[T], source: str) -> tuple[T, str]:
    """Parse and validate a canonical Markdown document."""

    raw_front_matter: YamlMapping = {}
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
                raw_front_matter = FrontMatterValues.model_validate(
                    yaml.safe_load(front_matter_content) or {}
                ).root
            except (yaml.YAMLError, ValidationError) as exc:
                raise AgentSyncError(f"Invalid YAML front matter in {source}: {exc}") from exc

    try:
        front_matter = model.model_validate(raw_front_matter)
    except ValidationError as exc:
        raise AgentSyncError(f"Invalid front matter in {source}: {exc}") from exc

    return front_matter, body.strip()


def render_front_matter(front_matter: BaseModel | YamlMapping, body: str) -> str:
    """Render validated YAML front matter followed by a Markdown body."""

    if isinstance(front_matter, BaseModel):
        values = FrontMatterValues.model_validate(
            front_matter.model_dump(
                by_alias=True,
                exclude_none=True,
            )
        ).root
    else:
        values = front_matter

    rendered = (
        yaml.safe_dump(
            values,
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
