import json
import tomllib
from typing import Literal, NotRequired, TypedDict

from agent_sync.constants import CODEX_MCP_END_MARKER, CODEX_MCP_START_MARKER
from agent_sync.models.mcp import BearerEnvAuth, McpConfig, StdioMcpServer
from agent_sync.utils.markdown import ensure_trailing_newline


class McpGenerationError(ValueError):
    """Raised when existing generated MCP state cannot be updated safely."""


class StdioMcpJson(TypedDict):
    """Native JSON shape shared by Claude and Cursor stdio servers."""

    type: Literal["stdio"]
    command: str
    args: list[str]
    env: NotRequired[dict[str, str]]


class HttpMcpJson(TypedDict):
    """Native JSON shape shared by Claude and Cursor HTTP servers."""

    type: Literal["http"]
    url: str
    headers: NotRequired[dict[str, str]]


type NativeMcpServer = StdioMcpJson | HttpMcpJson


def generate_claude_mcp(config: McpConfig) -> str:
    """Render Claude Code's project-scoped .mcp.json."""

    servers: dict[str, NativeMcpServer] = {}
    for name, server in sorted(config.servers.items()):
        if "claude" not in server.platforms:
            continue

        if isinstance(server, StdioMcpServer):
            rendered_stdio = StdioMcpJson(
                type="stdio",
                command=server.command,
                args=server.args,
            )
            if server.env:
                rendered_stdio["env"] = {
                    env_name: f"${{{env_name}}}" for env_name in sorted(server.env)
                }
            rendered: NativeMcpServer = rendered_stdio
        else:
            rendered_http = HttpMcpJson(type="http", url=server.url)
            headers = {
                header: f"${{{env_name}}}"
                for header, env_name in sorted(server.env_headers.items())
            }
            if isinstance(server.auth, BearerEnvAuth):
                headers["Authorization"] = f"Bearer ${{{server.auth.env}}}"
            if headers:
                rendered_http["headers"] = headers
            rendered = rendered_http

        servers[name] = rendered

    return json_document(servers)


def generate_cursor_mcp(config: McpConfig) -> str:
    """Render Cursor's project-scoped .cursor/mcp.json."""

    servers: dict[str, NativeMcpServer] = {}
    for name, server in sorted(config.servers.items()):
        if "cursor" not in server.platforms:
            continue

        if isinstance(server, StdioMcpServer):
            rendered = StdioMcpJson(
                type="stdio",
                command=server.command,
                args=server.args,
            )
        else:
            rendered = HttpMcpJson(type="http", url=server.url)

        servers[name] = rendered

    return json_document(servers)


def generate_codex_config(config: McpConfig, existing: str | None) -> str:
    """Replace only agent-sync's marked MCP block in .codex/config.toml."""

    current = existing or ""
    block = generate_codex_block(config)
    start_count = current.count(CODEX_MCP_START_MARKER)
    end_count = current.count(CODEX_MCP_END_MARKER)

    if start_count != end_count or start_count > 1:
        raise McpGenerationError(
            ".codex/config.toml has malformed or duplicate agent-sync MCP markers"
        )

    if start_count == 1:
        start = current.index(CODEX_MCP_START_MARKER)
        end_start = current.index(CODEX_MCP_END_MARKER)
        if end_start < start:
            raise McpGenerationError(".codex/config.toml has MCP markers in the wrong order")
        end = end_start + len(CODEX_MCP_END_MARKER)
        rendered = current[:start] + block + current[end:]
    elif block:
        if not current or current.endswith("\n\n"):
            separator = ""
        elif current.endswith("\n"):
            separator = "\n"
        else:
            separator = "\n\n"
        rendered = current + separator + block
    else:
        rendered = current

    rendered = ensure_trailing_newline(rendered) if rendered else ""
    try:
        tomllib.loads(rendered)
    except tomllib.TOMLDecodeError as exc:
        raise McpGenerationError(f"generated .codex/config.toml is invalid TOML: {exc}") from exc

    return rendered


def json_document(servers: dict[str, NativeMcpServer]) -> str:
    """Serialize native MCP server mappings deterministically."""

    return ensure_trailing_newline(
        json.dumps({"mcpServers": servers}, indent=2, sort_keys=True, ensure_ascii=False)
    )


def generate_codex_block(config: McpConfig) -> str:
    """Render the complete marked Codex MCP block."""

    sections: list[str] = []
    for name, server in sorted(config.servers.items()):
        if "codex" not in server.platforms:
            continue

        lines = [
            f'[mcp_servers.{toml_string(name)}]',
            "enabled = true",
            "required = true",
        ]
        if isinstance(server, StdioMcpServer):
            lines.append(f"command = {toml_string(server.command)}")
            lines.append(f"args = {toml_array(server.args)}")
            if server.env:
                lines.append(f"env_vars = {toml_array(sorted(server.env))}")
        else:
            lines.append(f"url = {toml_string(server.url)}")
            if isinstance(server.auth, BearerEnvAuth):
                lines.append(f"bearer_token_env_var = {toml_string(server.auth.env)}")
            if server.env_headers:
                header_pairs = ", ".join(
                    f"{toml_string(header)} = {toml_string(env_name)}"
                    for header, env_name in sorted(server.env_headers.items())
                )
                lines.append(f"env_http_headers = {{ {header_pairs} }}")

        sections.append("\n".join(lines))

    if not sections:
        return ""

    return (
        CODEX_MCP_START_MARKER
        + "\n"
        + "\n\n".join(sections)
        + "\n"
        + CODEX_MCP_END_MARKER
    )


def toml_string(value: str) -> str:
    """JSON strings are valid TOML basic strings for the values accepted by our schema."""

    return json.dumps(value, ensure_ascii=False)


def toml_array(values: list[str]) -> str:
    """Serialize a list of strings as a TOML array."""

    return "[" + ", ".join(toml_string(value) for value in values) + "]"
