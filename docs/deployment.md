# Deployment

<!-- BEGIN GENERATED: deployment-options -->
## Deployment Options

`systems-manager` exposes its MCP server (console script `systems-manager-mcp`) four ways. Pick the row that
matches where the server runs relative to your MCP client, then copy the matching
`mcp_config.json` below. Replace the `<your-…>` placeholders with the values from the **Configuration / Environment Variables** section.

| # | Option | Transport | Where it runs | `mcp_config.json` key |
|---|--------|-----------|---------------|------------------------|
| 1 | stdio | `stdio` | client launches a subprocess | `command` |
| 2 | Streamable-HTTP (local) | `streamable-http` | a local network port | `command` or `url` |
| 3 | Local container / uv | `stdio` or `streamable-http` | Docker / Podman / uv on this host | `command` or `url` |
| 4 | Remote URL | `streamable-http` | a remote host behind Caddy | `url` |

### 1. stdio (local subprocess)

The client launches the server over stdio via `uvx` — best for local IDEs
(Cursor, Claude Desktop, VS Code):

```json
{
  "mcpServers": {
    "systems-manager-mcp": {
      "command": "uvx",
      "args": ["--from", "systems-manager", "systems-manager-mcp"],
      "env": {
        "SYSTEMS_API_KEY": "<your-systems_api_key>"
      }
    }
  }
}
```

### 2. Streamable-HTTP (local process)

Run the server as a long-lived HTTP process:

```bash
uvx --from systems-manager systems-manager-mcp --transport streamable-http --host 0.0.0.0 --port 8000
curl -s http://localhost:8000/health        # {"status":"OK"}
```

Then either let the client launch it:

```json
{
  "mcpServers": {
    "systems-manager-mcp": {
      "command": "uvx",
      "args": ["--from", "systems-manager", "systems-manager-mcp", "--transport", "streamable-http", "--port", "8000"],
      "env": {
        "TRANSPORT": "streamable-http",
        "HOST": "0.0.0.0",
        "PORT": "8000",
        "SYSTEMS_API_KEY": "<your-systems_api_key>"
      }
    }
  }
}
```

…or connect to the already-running process by URL:

```json
{
  "mcpServers": {
    "systems-manager-mcp": { "url": "http://localhost:8000/mcp" }
  }
}
```

### 3. Local container / uv

**(a) Launch a container directly from `mcp_config.json`** (stdio over the container —
no ports to manage). Swap `docker` for `podman` for a daemonless runtime:

```json
{
  "mcpServers": {
    "systems-manager-mcp": {
      "command": "docker",
      "args": [
        "run", "-i", "--rm",
        "-e", "TRANSPORT=stdio",
        "-e", "SYSTEMS_API_KEY=<your-systems_api_key>",
        "knucklessg1/systems-manager:latest"
      ]
    }
  }
}
```

**(b) Run a local streamable-http container, then connect by URL:**

```bash
docker run -d --name systems-manager-mcp -p 8000:8000 \
  -e TRANSPORT=streamable-http \
  -e PORT=8000 \
  -e SYSTEMS_API_KEY="<your-systems_api_key>" \
  knucklessg1/systems-manager:latest
# or, from a clone of this repo:
docker compose -f docker/mcp.compose.yml up -d
```

```json
{
  "mcpServers": {
    "systems-manager-mcp": { "url": "http://localhost:8000/mcp" }
  }
}
```

**(c) From a local checkout with `uv`:**

```bash
uv run systems-manager-mcp --transport streamable-http --port 8000
```

### 4. Remote URL (deployed behind Caddy)

When the server is deployed remotely (e.g. as a Docker service) and published through
Caddy on the internal `*.arpa` zone, connect with the `"url"` key — no local process or
image required:

```json
{
  "mcpServers": {
    "systems-manager-mcp": { "url": "http://systems-manager-mcp.arpa/mcp" }
  }
}
```

Caddy reverse-proxies `http://systems-manager-mcp.arpa` to the container's `:8000`
streamable-http listener; `http://systems-manager-mcp.arpa/health` returns
`{"status":"OK"}` when the service is live.
<!-- END GENERATED: deployment-options -->

This page covers running `systems-manager` as a long-lived server: the transports, a
Docker Compose stack, putting it behind a Caddy reverse proxy, giving it a DNS name
with Technitium, and running the integrated agent server.

> `systems-manager` ships both an **MCP server** (console script `systems-manager-mcp`)
> and an **A2A agent server** (console script `systems-manager-agent`). The MCP server
> is a typed, deterministic tool surface a policy router / agent calls; the agent
> server wraps it in a Pydantic AI graph reachable over ACP and the Agent Web UI.

## Run the MCP server

The transport is selected with `--transport` (or the `TRANSPORT` env var):

=== "stdio (default)"

    ```bash
    systems-manager-mcp
    ```
    For IDE / desktop MCP clients that launch the server as a subprocess.

=== "streamable-http"

    ```bash
    systems-manager-mcp --transport streamable-http --host 0.0.0.0 --port 8000
    ```
    A network server with a `/health` endpoint and `/mcp` route.

=== "sse"

    ```bash
    systems-manager-mcp --transport sse --host 0.0.0.0 --port 8000
    ```

Health check (HTTP transports):

```bash
curl -s http://localhost:8000/health        # {"status":"OK"}
```

## Configuration (environment)

`systems-manager` is configured entirely from the environment. The **required** set:

| Var | Default | Meaning |
|---|---|---|
| `HOST` | `0.0.0.0` | Bind address for HTTP transports |
| `PORT` | `8000` | Bind port for HTTP transports |
| `TRANSPORT` | `stdio` | Transport: `stdio`, `streamable-http`, or `sse` |
| `MISCTOOL` | `True` | Register the miscellaneous tool module |
| `ENABLE_OTEL` | `True` | Export OpenTelemetry traces |
| `EUNOMIA_TYPE` | `none` | Authorization mode: `none`, `embedded`, or `remote` |
| `EUNOMIA_POLICY_FILE` | `mcp_policies.json` | Embedded policy file path |

Optional observability and authorization settings (`OTEL_EXPORTER_OTLP_ENDPOINT`,
`EUNOMIA_REMOTE_URL`, and connector credentials) are documented in
[`.env.example`](https://github.com/Knuckles-Team/systems-manager/blob/main/.env.example).
Copy it to `.env` and fill in only what you use.

## Docker Compose

The repo ships [`docker/mcp.compose.yml`](https://github.com/Knuckles-Team/systems-manager/blob/main/docker/mcp.compose.yml).
It reads a sibling `.env` and publishes the HTTP server on `:8000`:

```yaml
services:
  systems-manager-mcp:
    image: knucklessg1/systems-manager:latest
    container_name: systems-manager-mcp
    hostname: systems-manager-mcp
    restart: always
    env_file:
      - ../.env
    environment:
      - PYTHONUNBUFFERED=1
      - HOST=0.0.0.0
      - PORT=8000
      - TRANSPORT=streamable-http
    ports:
      - "8000:8000"
    healthcheck:
      test: ["CMD", "python3", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"]
      interval: 30s
      timeout: 10s
      retries: 3
```

```bash
cp .env.example .env          # then edit values
docker compose -f docker/mcp.compose.yml up -d
docker compose -f docker/mcp.compose.yml logs -f
```

## Agent server

`systems-manager` includes an integrated Pydantic AI graph agent (console script
`systems-manager-agent`). It connects to the MCP server over `MCP_URL`, communicates
over the Agent Control Protocol (ACP), and serves the Agent Web UI (AG-UI) on its own
port (default `9009`).

```bash
export MCP_URL=http://localhost:8000/mcp
systems-manager-agent --provider openai --model-id gpt-4o
```

The repo ships [`docker/agent.compose.yml`](https://github.com/Knuckles-Team/systems-manager/blob/main/docker/agent.compose.yml),
which runs the MCP server and the agent together; the agent reaches the MCP server by
container name:

```yaml
services:
  systems-manager-mcp:
    image: knucklessg1/systems-manager:latest
    container_name: systems-manager-mcp
    hostname: systems-manager-mcp
    restart: always
    env_file:
      - ../.env
    environment:
      - PYTHONUNBUFFERED=1
      - HOST=0.0.0.0
      - PORT=8000
      - TRANSPORT=streamable-http
    ports:
      - "8000:8000"

  systems-manager-agent:
    image: knucklessg1/systems-manager:latest
    container_name: systems-manager-agent
    hostname: systems-manager-agent
    restart: always
    depends_on:
      - systems-manager-mcp
    env_file:
      - ../.env
    command: ["systems-manager-agent"]
    environment:
      - PYTHONUNBUFFERED=1
      - HOST=0.0.0.0
      - PORT=9009
      - MCP_URL=http://systems-manager-mcp:8000/mcp
      - PROVIDER=${PROVIDER:-openai}
      - MODEL_ID=${MODEL_ID:-gpt-4o}
      - ENABLE_WEB_UI=True
    ports:
      - "9009:9009"
```

```bash
docker compose -f docker/agent.compose.yml up -d
```

## Behind a Caddy reverse proxy

Expose the HTTP server on a hostname with automatic TLS. Add to your `Caddyfile`:

```caddy
# Internal (self-signed) — homelab .arpa zone
systems-manager.arpa {
    tls internal
    reverse_proxy systems-manager-mcp:8000
}
```

```caddy
# Public — automatic Let's Encrypt
systems-manager.example.com {
    reverse_proxy systems-manager-mcp:8000
}
```

Reload Caddy:

```bash
docker compose -f services/caddy/compose.yml exec caddy caddy reload --config /etc/caddy/Caddyfile
```

## DNS with Technitium

Point the hostname at the host running Caddy. Via the Technitium API:

```bash
curl -s "http://technitium.arpa:5380/api/zones/records/add" \
  --data-urlencode "token=$TECHNITIUM_DNS_TOKEN" \
  --data-urlencode "domain=systems-manager.arpa" \
  --data-urlencode "zone=arpa" \
  --data-urlencode "type=A" \
  --data-urlencode "ipAddress=10.0.0.10" \
  --data-urlencode "ttl=3600"
```

…or add an **A record** `systems-manager.arpa → <caddy-host-ip>` in the Technitium web
console (`http://technitium.arpa:5380`). The ecosystem
[`technitium-dns-mcp`](https://knuckles-team.github.io/technitium-dns-mcp/) automates
this as a tool.

## Register with an MCP client

Add to your client's `mcp_config.json`:

```json
{
  "mcpServers": {
    "systems-manager": {
      "command": "uvx",
      "args": ["--from", "systems-manager", "systems-manager-mcp"],
      "env": {
        "MISCTOOL": "True"
      }
    }
  }
}
```

For a remote HTTP server, point the client at `http://systems-manager.arpa/mcp`
instead.
