import re
from typing import Annotated, Final, Literal, Self
from urllib.parse import parse_qsl, urlsplit

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

Platform = Literal["claude", "cursor", "codex"]

ENV_NAME_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[A-Z_][A-Z0-9_]*$")
HEADER_NAME_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"^[!#$%&'*+\-.^_`|~0-9A-Za-z]+$"
)
SERVER_NAME_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9_-]*$"
)
SECRET_ARGUMENT_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"^--?(?:api[-_]?key|auth(?:orization)?|bearer|password|secret|token)(?:=|$)",
    re.IGNORECASE,
)
SECRET_QUERY_NAMES: Final[frozenset[str]] = frozenset(
    {
        "access_token",
        "api_key",
        "apikey",
        "auth",
        "authorization",
        "client_secret",
        "credential",
        "jwt",
        "key",
        "password",
        "secret",
        "sig",
        "signature",
        "token",
    }
)


def validate_env_name(value: str) -> str:
    """Require portable, explicit environment-variable names."""

    if not ENV_NAME_PATTERN.fullmatch(value):
        raise ValueError("must match ^[A-Z_][A-Z0-9_]*$")

    return value


class OAuthAuth(BaseModel):
    """Use the MCP client's OAuth discovery and login flow."""

    model_config = ConfigDict(extra="forbid", strict=True)

    type: Literal["oauth"]


class BearerEnvAuth(BaseModel):
    """Read an HTTP bearer token from the agent's runtime environment."""

    model_config = ConfigDict(extra="forbid", strict=True)

    type: Literal["bearer-env"]
    env: str

    validate_env_variable = field_validator("env")(validate_env_name)


McpAuth = Annotated[OAuthAuth | BearerEnvAuth, Field(discriminator="type")]


class McpServerBase(BaseModel):
    """Fields shared by every canonical MCP server definition."""

    model_config = ConfigDict(extra="forbid", strict=True)

    platforms: list[Platform] = Field(default_factory=lambda: ["claude", "cursor", "codex"])

    @field_validator("platforms")
    @classmethod
    def validate_platforms(cls, value: list[Platform]) -> list[Platform]:
        """Require a non-empty platform list without duplicates."""

        if not value:
            raise ValueError("must contain at least one platform")
        if len(value) != len(set(value)):
            raise ValueError("must not contain duplicate platforms")

        return value


class StdioMcpServer(McpServerBase):
    """A local MCP server launched as a child process."""

    type: Literal["stdio"]
    command: str = Field(min_length=1)
    args: list[str] = Field(default_factory=list)
    env: list[str] = Field(default_factory=list)

    @field_validator("command")
    @classmethod
    def validate_command(cls, value: str) -> str:
        """Reject blank or environment-expanded executable names."""

        if not value.strip():
            raise ValueError("must not be blank")
        if "${" in value:
            raise ValueError(
                "must be literal; environment interpolation is only allowed through env"
            )

        return value

    @field_validator("args")
    @classmethod
    def validate_args(cls, value: list[str]) -> list[str]:
        """Reject argument interpolation and credential-bearing flags."""

        for argument in value:
            if "${" in argument:
                raise ValueError(
                    "arguments must be literal; pass secrets through a named environment variable"
                )
            if SECRET_ARGUMENT_PATTERN.match(argument):
                raise ValueError(
                    f"argument {argument!r} looks credential-bearing; pass it through env instead"
                )

        return value

    @field_validator("env")
    @classmethod
    def validate_env(cls, value: list[str]) -> list[str]:
        """Require unique, portable environment-variable names."""

        if len(value) != len(set(value)):
            raise ValueError("must not contain duplicate environment-variable names")

        return [validate_env_name(name) for name in value]

    @model_validator(mode="after")
    def validate_cursor_secrets(self) -> Self:
        """Prevent undocumented Cursor environment interpolation."""

        if self.env and "cursor" in self.platforms:
            raise ValueError(
                "Cursor project MCP config has no documented safe environment-reference syntax; "
                "exclude cursor or remove env"
            )

        return self


class HttpMcpServer(McpServerBase):
    """A remote streamable-HTTP MCP server."""

    type: Literal["http"]
    url: str = Field(min_length=1)
    auth: McpAuth | None = None
    env_headers: dict[str, str] = Field(default_factory=dict, alias="envHeaders")

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        """Require credential-free HTTPS URLs, except for loopback development."""

        if "${" in value:
            raise ValueError("must be literal; environment interpolation is not allowed in URLs")

        parsed = urlsplit(value)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("must be an absolute http:// or https:// URL")
        if parsed.username is not None or parsed.password is not None:
            raise ValueError("must not contain embedded credentials")
        if parsed.fragment:
            raise ValueError("must not contain a URL fragment")
        if parsed.scheme == "http" and parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
            raise ValueError("remote MCP URLs must use HTTPS")

        query_names = {name.lower() for name, _ in parse_qsl(parsed.query, keep_blank_values=True)}
        secret_names = sorted(query_names & SECRET_QUERY_NAMES)
        if secret_names:
            raise ValueError(
                "must not contain credential-like query parameters: " + ", ".join(secret_names)
            )

        return value

    @field_validator("env_headers")
    @classmethod
    def validate_env_headers(cls, value: dict[str, str]) -> dict[str, str]:
        """Validate header names and environment references."""

        for header, env_name in value.items():
            if not HEADER_NAME_PATTERN.fullmatch(header):
                raise ValueError(f"invalid HTTP header name: {header!r}")
            if header.lower() == "authorization":
                raise ValueError("use auth.type=bearer-env for the Authorization header")
            validate_env_name(env_name)

        return value

    @model_validator(mode="after")
    def validate_cursor_secrets(self) -> Self:
        """Prevent repository-expanded HTTP secrets from targeting Cursor."""

        uses_env_secrets = isinstance(self.auth, BearerEnvAuth) or bool(self.env_headers)
        if uses_env_secrets and "cursor" in self.platforms:
            raise ValueError(
                "Cursor project MCP config has no documented safe environment-reference syntax; "
                "exclude cursor and configure hosted Cursor secrets separately"
            )

        return self


McpServer = Annotated[StdioMcpServer | HttpMcpServer, Field(discriminator="type")]


class McpConfig(BaseModel):
    """Canonical .agents/mcp.json configuration."""

    model_config = ConfigDict(extra="forbid", strict=True)

    version: Literal[1]
    servers: dict[str, McpServer]

    @field_validator("servers")
    @classmethod
    def validate_server_names(cls, value: dict[str, McpServer]) -> dict[str, McpServer]:
        """Require portable server names and reject Claude's reserved name."""

        for name, server in value.items():
            if not SERVER_NAME_PATTERN.fullmatch(name):
                raise ValueError(
                    f"server name {name!r} must match ^[A-Za-z0-9][A-Za-z0-9_-]*$"
                )
            if name == "workspace" and "claude" in server.platforms:
                raise ValueError("server name 'workspace' is reserved by Claude Code")

        return value
