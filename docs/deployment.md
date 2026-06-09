# Deployment

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
