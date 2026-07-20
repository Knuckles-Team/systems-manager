# Deployment

`systems-manager` exposes a local stdio MCP server, an authenticated network MCP
server, and an optional agent server. Network transports fail closed unless their
authentication boundary is configured.

## Local stdio

Install the MCP extra and launch the entry point:

```bash
uvx --from "systems-manager[mcp]" systems-manager-mcp --transport stdio
```

A client configuration can use the repository's reference-only catalog. Keep runtime
values in AgentConfig rather than editing the catalog with deployment endpoints,
secrets, trust paths, or host identities.

## Network MCP

For `streamable-http` or `sse`, configure:

- an authentication provider through the current Agent Utilities MCP settings;
- direct TLS certificate/key settings, or a verified TLS-terminating proxy and
  trusted proxy CIDRs;
- an explicit host allowlist;
- a deliberate bind address.

The server refuses a network transport when authentication is absent. Use HTTPS for
every non-loopback client. A replaceable client entry is:

```json
{
  "mcpServers": {
    "systems-manager": {
      "url": "https://mcp.example.invalid/mcp"
    }
  }
}
```

Do not place credentials in the URL. Configure outbound OIDC or another supported
service identity through the client boundary.

## Containers

The repository ships two hardened Compose definitions:

- `docker/mcp.compose.yml` for the MCP server;
- `docker/agent.compose.yml` for an agent plus MCP sidecar.

Both require operator-selected image variables, bind published ports to loopback by
default, run as UID/GID 10001, drop all Linux capabilities, enable
`no-new-privileges`, use read-only filesystems, bound memory/CPU/PIDs, and use a
bounded `tmpfs`. Network authentication and TLS boundary inputs are required.

Build the two image targets with explicit registry tags:

```bash
docker build --target mcp -t "${SYSTEMS_MANAGER_MCP_IMAGE}" -f docker/Dockerfile .
docker build --target agent -t "${SYSTEMS_MANAGER_AGENT_IMAGE}" -f docker/Dockerfile .
```

The Dockerfile pins base and uv images by digest and installs into a multi-stage,
non-root runtime. Deployment pipelines should additionally sign the resulting image,
produce an SBOM/provenance attestation, scan it, and enforce the approved digest at
admission.

## Agent server

A non-loopback agent listener requires all of:

- `SYSTEMS_MANAGER_ALLOW_REMOTE_AGENT_SERVER=true`;
- direct TLS or an explicitly trusted TLS proxy boundary;
- JWT authentication through `AUTH_JWT_JWKS_URI`, `AUTH_JWT_ISSUER`, and
  `AUTH_JWT_AUDIENCE`;
- debug mode disabled.

Remote MCP children require an outbound service identity. Model, MCP, and OTLP
endpoints must be credential-free HTTPS or loopback HTTP. Certificate verification
is mandatory; private trust is selected from the AgentConfig TLS-profile catalog,
not a source-code switch.

## Host permissions

Run under a dedicated service identity. Configure
`SYSTEMS_MANAGER_FILESYSTEM_ROOT` to a non-volume, trusted-owner directory.
Privilege gates default to false. The optional elevation helper uses empty-by-default
deployment allowlists; see [Sudo security](sudo_security.md).

Containers operate on their container boundary unless a separately reviewed host
broker is provided. They do not implicitly manage the container host, Windows host,
or WSL host.

## Observability and privacy

OTLP/Langfuse settings are deployment inputs. Default to metadata-only telemetry.
Before enabling content capture, approve retention, access control, tenant isolation,
and redaction. Never store prompts, tool bodies/results, hostnames, usernames, local
paths, certificate paths, or credentials in traces.

## Release and readiness gates

1. Verify the package, image digest, SBOM, signature, and provenance. Generate a
   neutral dependency lock only after every declared release is available; reject
   editable local sources and stale locks.
2. Run the ecosystem doctor without printing values.
3. Validate the current ontology, source preset, mapping, MCP schemas, packaged skill,
   and signed offline source bundle. Generate external-live certification only in the
   authorized release environment; never infer it from offline evidence.
4. Prove unauthenticated network startup/calls fail.
5. Prove each privilege gate fails closed.
6. Exercise one approved typed operation and independent read-back.
7. Confirm sanitized traces arrive under opaque run and tenant identifiers.
8. Keep rollback artifacts and recovery ownership available before hot swapping.

See [Configuration](configuration.md) for the complete trust and privacy contract.
