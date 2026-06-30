# Shared ContextForge MCP gateway

This directory is an optional, vendor-neutral reference deployment for
[IBM ContextForge](https://github.com/IBM/mcp-context-forge). ContextForge is
the one MCP endpoint used by Claude, Cursor, and Codex. Upstream MCP
credentials stay in the gateway and are encrypted in PostgreSQL instead of
being copied into agent repositories or agent runtimes.

This is a reference architecture, not a production security guarantee. Review
ContextForge releases and security guidance before deploying it.

## Local evaluation

Provide a reachable PostgreSQL database, then build and run the same image used
by an OCI-compatible host. The example environment intentionally uses
`ENVIRONMENT=development` and `SECURE_COOKIES=false` because it serves plain
HTTP on localhost:

```bash
cp .env.example .env
# Replace every placeholder in .env. Use a different generated value for each secret.
docker build --tag agent-sync-contextforge .
docker run --rm --env-file .env --publish 4444:4444 agent-sync-contextforge
curl --fail http://localhost:4444/health
```

Open `http://localhost:4444/admin`, sign in with the bootstrap administrator,
register upstream MCP gateways, and compose them into a virtual server. Copy
the virtual server's streamable HTTP URL into `.agents/mcp.json`.

Do not reuse `JWT_SECRET_KEY`, `AUTH_ENCRYPTION_SECRET`, the database password,
the bootstrap administrator password, or `BASIC_AUTH_PASSWORD`. Rotate the
bootstrap administrator password after first sign-in. Hex output from
`openssl rand -hex 32` is appropriate for the two keys; passwords should use
independent values containing at least uppercase letters, lowercase letters,
and digits.

## Hosting requirements

The Dockerfile follows ContextForge's current `latest` OCI image and can be
deployed by any container host. A hosted deployment must provide:

- An external, backed-up PostgreSQL database. SQLite is evaluation-only.
- HTTPS termination with HTTP redirected or disabled.
- `ENVIRONMENT=production`, the public HTTPS `APP_DOMAIN`, and
  `SECURE_COOKIES=true`.
- Secret environment variables for `DATABASE_URL`, `JWT_SECRET_KEY`,
  `AUTH_ENCRYPTION_SECRET`, `BASIC_AUTH_PASSWORD`, and the bootstrap
  administrator credentials.
- A health probe against `/health`.
- Restricted administrator access and outbound network policy appropriate for
  the registered upstream servers.
- Edge-enforced host allowlisting, trusted-proxy boundaries, request-size
  limits, and rate limits.

Keep ContextForge's strict SSRF defaults. If an upstream server is on a private
network, allow only its specific CIDR through `SSRF_ALLOWED_NETWORKS`; do not
enable all private-network destinations. Keep query-string authentication and
API basic authentication disabled. Keep CORS disabled unless a browser client
requires it; if enabled, allowlist only the public application origin.
Authorization headers must not be written to application or reverse-proxy
logs.

Inject the complete provider-issued `DATABASE_URL` through the hosting
platform's secret manager.

ContextForge encrypts stored upstream authorization headers and OAuth tokens
using `AUTH_ENCRYPTION_SECRET`. Losing that value makes encrypted credentials
unrecoverable; leaking it together with a database backup exposes them. Back
up and rotate it as a deployment master key.

## Agent authentication

OAuth/OIDC is the preferred flow for persistent clients:

```json
{
  "version": 1,
  "servers": {
    "agent-tools": {
      "type": "http",
      "url": "https://mcp.example.com/agent-tools/mcp",
      "auth": { "type": "oauth" },
      "platforms": ["claude", "cursor", "codex"]
    }
  }
}
```

ContextForge's upstream OAuth support is separate from MCP client OAuth.
Standard MCP OAuth discovery and dynamic client registration can be placed in
front of ContextForge using its documented
[HyprMCP integration](https://ibm.github.io/mcp-context-forge/tutorials/dcr-hyprmcp/).
Treat that tutorial as an architecture guide: retain issuer and audience
verification, trust proxy-auth headers only from the authenticated proxy, and
use a maintained external identity provider. This reference does not bundle an
identity provider or HyprMCP.

For unattended runs, issue a short-lived ContextForge JWT and inject it into
the agent runtime:

```json
{
  "version": 1,
  "servers": {
    "agent-tools": {
      "type": "http",
      "url": "https://mcp.example.com/agent-tools/mcp",
      "auth": {
        "type": "bearer-env",
        "env": "AGENT_MCP_GATEWAY_TOKEN"
      },
      "platforms": ["claude", "codex"]
    }
  }
}
```

Claude and Codex read only the environment-variable reference. Repository-level
Cursor configuration does not have a documented, portable secret-reference
syntax, so configure the same gateway and token in Cursor's hosted secret or
MCP dashboard instead of committing it.

Deployment-level secrets may later be supplied by OpenBao or another external
vault. OpenBao is intentionally not bundled with this reference.
