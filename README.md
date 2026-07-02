# Systems Manager
## CLI or API | MCP | Agent

![PyPI - Version](https://img.shields.io/pypi/v/systems-manager)
![MCP Server](https://badge.mcpx.dev?type=server 'MCP Server')
![PyPI - Downloads](https://img.shields.io/pypi/dd/systems-manager)
![GitHub Repo stars](https://img.shields.io/github/stars/Knuckles-Team/systems-manager)
![GitHub forks](https://img.shields.io/github/forks/Knuckles-Team/systems-manager)
![GitHub contributors](https://img.shields.io/github/contributors/Knuckles-Team/systems-manager)
![PyPI - License](https://img.shields.io/pypi/l/systems-manager)
![GitHub](https://img.shields.io/github/license/Knuckles-Team/systems-manager)
![GitHub last commit (by committer)](https://img.shields.io/github/last-commit/Knuckles-Team/systems-manager)
![GitHub pull requests](https://img.shields.io/github/issues-pr/Knuckles-Team/systems-manager)
![GitHub closed pull requests](https://img.shields.io/github/issues-pr-closed/Knuckles-Team/systems-manager)
![GitHub issues](https://img.shields.io/github/issues/Knuckles-Team/systems-manager)
![GitHub top language](https://img.shields.io/github/languages/top/Knuckles-Team/systems-manager)
![GitHub language count](https://img.shields.io/github/languages/count/Knuckles-Team/systems-manager)
![GitHub repo size](https://img.shields.io/github/repo-size/Knuckles-Team/systems-manager)
![GitHub repo file count (file type)](https://img.shields.io/github/directory-file-count/Knuckles-Team/systems-manager)
![PyPI - Wheel](https://img.shields.io/pypi/wheel/systems-manager)
![PyPI - Implementation](https://img.shields.io/pypi/implementation/systems-manager)

*Version: 1.35.0*

> **Documentation** — Installation, deployment, and usage across the CLI, API, MCP,
> and agent interfaces are maintained in the
> [official documentation](https://knuckles-team.github.io/systems-manager/).

---

## Overview

**Systems Manager** is a production-grade Agent and Model Context Protocol (MCP) server designed to interface directly with Systems Manager will update your system and install/upgrade applications. Additionally, as allow AI to perform these activities as an MCP Server.

---

## Key Features

- **Consolidated Action-Routed MCP Tools:** Minimizes token overhead and eliminates tool bloat in LLM contexts by grouping methods into optimized, togglable tool modules.
- **Enterprise-Grade Security:** Comprehensive support for Eunomia policies, OIDC token delegation, and granular execution context tracking.
- **Integrated Graph Agent:** Built-in Pydantic AI agent supporting the Agent Control Protocol (ACP) and standard Web interfaces (AG-UI).
- **Native Telemetry & Tracing:** Out-of-the-box OpenTelemetry exports and native Langfuse tracing.

---

## Multi-Host & Zero-Script Remote Orchestration

`systems-manager` supports full zero-script remote server telemetry and control plane routing out of the box.

- **Unified Inventory**: Single source of truth inventory loaded dynamically from standard XDG paths (`~/.config/agent_utilities/inventory.yaml`).
- **Zero Remote Dependencies**: Remote targets require only standard SSH access and a standard Python interpreter—no remote daemons, systemd configurations, or software packages are deployed on the target hosts.
- **Dynamic Telemetry Serialization (`remote_eval`)**: Telemetries (such as `get_os_statistics()`, `get_hardware_statistics()`, and process monitoring) are automatically packed and evaluated dynamically over secure SSH tunnels.

To configure and utilize the multi-host remote routing, see the detailed [Multi-Host Architecture Guide](docs/multi_host.md).

---

## CLI or API

This agent wraps the Systems Manager will update your system and install/upgrade applications. Additionally, as allow AI to perform these activities as an MCP Server API. You can interact with it programmatically or via its integrated execution entrypoints.

Detailed instructions on how to use the underlying API wrappers, extended schema bindings, and developer SDK references are maintained in [docs/index.md](docs/index.md).

---

## MCP

This server utilizes dynamic Action-Routed tools to optimize token overhead and maximize IDE compatibility.

### Available MCP Tools

_Auto-generated from the live MCP server — do not edit by hand._

<!-- MCP-TOOLS-TABLE:START -->

#### Condensed action-routed tools (default — `MCP_TOOL_MODE=condensed`)

| MCP Tool | Toggle Env Var | Description |
|----------|----------------|-------------|
| `capture_system_snapshot` | `OS_PROVIDERTOOL` | Takes a point-in-time snapshot of the system state (CPU, RAM, Processes). |
| `get_network_connections` | `OS_PROVIDERTOOL` | Maps active TCP/UDP endpoints directly to owning processes. |
| `get_process_details` | `OS_PROVIDERTOOL` | Retrieves deep cross-platform process details (threads, modules, memory). |
| `health_check` | — |  |
| `list_kernel_modules` | `OS_PROVIDERTOOL` | List loaded drivers/modules (lsmod or driverquery). |
| `list_services` | `OS_PROVIDERTOOL` | Cross-platform service enumeration (systemctl or Get-Service). |
| `manage_service` | `OS_PROVIDERTOOL` | Start/Stop/Restart/Enable/Disable services cross-platform. |
| `query_system_logs` | `OS_PROVIDERTOOL` | Cross-platform log querying (journalctl or Get-WinEvent). |
| `sm_advanced_operations` | — | Operations for SSH and specialized managers |
| `sm_cron_operations` | — | Operations for cron jobs |
| `sm_disk_operations` | — | Operations for managing system disks |
| `sm_file_operations` | — | Operations for file and log management |
| `sm_firewall_operations` | — | Operations for firewall management |
| `sm_network_operations` | — | Operations for network analysis |
| `sm_process_operations` | — | Operations for managing system processes |
| `sm_service_operations` | — | Operations for managing system services |
| `sm_storage_health` | `STORAGE_HEALTHTOOL` | Physical disk + BMC drive-fault health: SMART (incl. RAID megaraid passthrough), BMC/IPMI drive-slot faults (OpenBao-credentialed OOB), RAID PD state — correlated. |
| `sm_system_operations` | — | System operations for managing packages, system health, and updates |
| `sm_user_operations` | — | Operations for user and group management |
| `start_system_trace` | `OS_PROVIDERTOOL` | Start a kernel-level event trace (ETW on Windows, or strace on Linux). |
| `stop_system_trace` | `OS_PROVIDERTOOL` | Stop a kernel-level event trace. |

_20 action-routed tool(s) (default) · 0 verbose 1:1 tool(s). Each is enabled unless its `<DOMAIN>TOOL` toggle is set false; `MCP_TOOL_MODE` selects the surface (`condensed` default · `verbose` 1:1 · `both`). Auto-generated — do not edit._
<!-- MCP-TOOLS-TABLE:END -->

Detailed tool schemas, parameter shapes, and validation constraints are preserved in [docs/mcp.md](docs/mcp.md).

### Dynamic Tool Selection & Visibility

This MCP server supports dynamic toolset selection and visibility filtering at runtime. This allows you to restrict the set of exposed tools in order to prevent blowing up the LLM's context window.

You can configure tool filtering via multiple input channels:

- **CLI Arguments:** Pass `--tools` or `--toolsets` (or their disabled counterparts `--disabled-tools` and `--disabled-toolsets`) during startup.
- **Environment Variables:** Define standard environment variables:
  - `MCP_ENABLED_TOOLS` / `MCP_DISABLED_TOOLS`
  - `MCP_ENABLED_TAGS` / `MCP_DISABLED_TAGS`
- **HTTP SSE Request Headers:** Pass custom headers during transport initialization:
  - `x-mcp-enabled-tools` / `x-mcp-disabled-tools`
  - `x-mcp-enabled-tags` / `x-mcp-disabled-tags`
- **HTTP SSE Request Query Parameters:** Append query parameters directly to your transport connection URL:
  - `?tools=tool1,tool2`
  - `?tags=tag1`

When query strings or parameters are supplied, an LLM-free **Knowledge Graph resolution layer** (using `DynamicToolOrchestrator`) matches query intents against known tool tags, names, or descriptions, with safe fallback and automated 24-hour background cache refreshing.

---

### MCP Configuration Examples

<!-- MCP-CONFIG-EXAMPLES:START -->

> **Install the slim `[mcp]` extra.** All examples install `systems-manager[mcp]` — the
> MCP-server extra that pulls only the FastMCP / FastAPI tooling (`agent-utilities[mcp]`).
> It deliberately **excludes** the heavy agent runtime (`pydantic-ai`, the epistemic-graph
> engine, `dspy`, `llama-index`), so `uvx` / container installs are far smaller. Use the
> full `[agent]` extra only when you need the integrated Pydantic AI agent.

#### stdio Transport (local IDEs — Cursor, Claude Desktop, VS Code)

```json
{
  "mcpServers": {
    "systems-manager-mcp": {
      "command": "uvx",
      "args": [
        "--from",
        "systems-manager[mcp]",
        "systems-manager-mcp"
      ],
      "env": {
        "MCP_TOOL_MODE": "condensed",
        "AGENT_HEALTHTOOL": "True",
        "AGENT_POLICIES_PATH": "",
        "IDENTITYTOOL": "True",
        "MAINTENANCETOOL": "True",
        "MAINTENANCE_PRIORITY": "",
        "MAINTENANCE_TOKEN_BUDGET": "",
        "MAX_CONCURRENT_AGENTS": "",
        "MCP_CONFIG_PATH": "",
        "MISCTOOL": "True",
        "OPENBAO_TOKEN": "",
        "OPENBAO_URL": "http://openbao.arpa",
        "OS_PROVIDERTOOL": "True",
        "PERMISSIONS_SIGNING_KEY": "",
        "POLICYTOOL": "True",
        "PROJECT_ROOT": "",
        "SPECIALIST_REGISTRYTOOL": "True",
        "SPECIALIST_REGISTRY_PATH": "",
        "STORAGE_HEALTHTOOL": "True",
        "SYSTEMS_MANAGER_HOST": "",
        "WATCHDOGTOOL": "True"
      }
    }
  }
}
```

#### Streamable-HTTP Transport (networked / production)

```json
{
  "mcpServers": {
    "systems-manager-mcp": {
      "command": "uvx",
      "args": [
        "--from",
        "systems-manager[mcp]",
        "systems-manager-mcp",
        "--transport",
        "streamable-http",
        "--port",
        "8000"
      ],
      "env": {
        "TRANSPORT": "streamable-http",
        "HOST": "0.0.0.0",
        "PORT": "8000",
        "MCP_TOOL_MODE": "condensed",
        "AGENT_HEALTHTOOL": "True",
        "AGENT_POLICIES_PATH": "",
        "IDENTITYTOOL": "True",
        "MAINTENANCETOOL": "True",
        "MAINTENANCE_PRIORITY": "",
        "MAINTENANCE_TOKEN_BUDGET": "",
        "MAX_CONCURRENT_AGENTS": "",
        "MCP_CONFIG_PATH": "",
        "MISCTOOL": "True",
        "OPENBAO_TOKEN": "",
        "OPENBAO_URL": "http://openbao.arpa",
        "OS_PROVIDERTOOL": "True",
        "PERMISSIONS_SIGNING_KEY": "",
        "POLICYTOOL": "True",
        "PROJECT_ROOT": "",
        "SPECIALIST_REGISTRYTOOL": "True",
        "SPECIALIST_REGISTRY_PATH": "",
        "STORAGE_HEALTHTOOL": "True",
        "SYSTEMS_MANAGER_HOST": "",
        "WATCHDOGTOOL": "True"
      }
    }
  }
}
```

Alternatively, connect to a pre-deployed Streamable-HTTP instance by `url`:

```json
{
  "mcpServers": {
    "systems-manager-mcp": {
      "url": "http://localhost:8000/systems-manager-mcp/mcp"
    }
  }
}
```

Deploying the Streamable-HTTP server via Docker:

```bash
docker run -d \
  --name systems-manager-mcp-mcp \
  -p 8000:8000 \
  -e TRANSPORT=streamable-http \
  -e HOST=0.0.0.0 \
  -e PORT=8000 \
  -e MCP_TOOL_MODE=condensed \
  -e AGENT_HEALTHTOOL=True \
  -e AGENT_POLICIES_PATH="" \
  -e IDENTITYTOOL=True \
  -e MAINTENANCETOOL=True \
  -e MAINTENANCE_PRIORITY="" \
  -e MAINTENANCE_TOKEN_BUDGET="" \
  -e MAX_CONCURRENT_AGENTS="" \
  -e MCP_CONFIG_PATH="" \
  -e MISCTOOL=True \
  -e OPENBAO_TOKEN="" \
  -e OPENBAO_URL=http://openbao.arpa \
  -e OS_PROVIDERTOOL=True \
  -e PERMISSIONS_SIGNING_KEY="" \
  -e POLICYTOOL=True \
  -e PROJECT_ROOT="" \
  -e SPECIALIST_REGISTRYTOOL=True \
  -e SPECIALIST_REGISTRY_PATH="" \
  -e STORAGE_HEALTHTOOL=True \
  -e SYSTEMS_MANAGER_HOST="" \
  -e WATCHDOGTOOL=True \
  knucklessg1/systems-manager:mcp
```

_Auto-generated from the code-read env surface (`MCP_TOOL_MODE` + package vars) — do not edit._
<!-- MCP-CONFIG-EXAMPLES:END -->

<!-- BEGIN GENERATED: additional-deployment-options -->
### Additional Deployment Options

`systems-manager` can also run as a **local container** (Docker / Podman / `uv`) or be
consumed from a **remote deployment**. The
[Deployment guide](https://knuckles-team.github.io/systems-manager/deployment/) has full, copy-paste
`mcp_config.json` for all four transports — **stdio**, **streamable-http**,
**local container / uv**, and **remote URL**:

- **Local container / uv** — launch the server from `mcp_config.json` via `uvx`,
  `docker run`, or `podman run`, or point at a local streamable-http container by `url`.
- **Remote URL** — connect to a server deployed behind Caddy at
  `http://systems-manager-mcp.arpa/mcp` using the `"url"` key.
<!-- END GENERATED: additional-deployment-options -->

---

## Environment Variables

<!-- ENV-VARS-TABLE:START -->

#### Package environment variables

| Variable | Example | Description |
|----------|---------|-------------|
| `HOST` | `0.0.0.0` |  |
| `PORT` | `8000` |  |
| `TRANSPORT` | `stdio` | options: stdio, streamable-http, sse |
| `ENABLE_OTEL` | `True` |  |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | `http://localhost:8080/api/public/otel` |  |
| `OTEL_EXPORTER_OTLP_PUBLIC_KEY` | `pk-...` |  |
| `OTEL_EXPORTER_OTLP_SECRET_KEY` | `sk-...` |  |
| `OTEL_EXPORTER_OTLP_PROTOCOL` | `http/protobuf` |  |
| `EUNOMIA_TYPE` | `none` | options: none, embedded, remote |
| `EUNOMIA_POLICY_FILE` | `mcp_policies.json` |  |
| `EUNOMIA_REMOTE_URL` | `http://eunomia-server:8000` |  |
| `SYSTEMS_MANAGER_HOST` | — | target host for remote telemetry/control (defaults to local) |
| `PROJECT_ROOT` | — | project root used to resolve config/inventory paths |
| `MCP_CONFIG_PATH` | — | path to the MCP config (mcp_config.json) |
| `MAX_CONCURRENT_AGENTS` | — | cap on concurrently dispatched sub-agents |
| `MAINTENANCE_PRIORITY` | — | maintenance-lane scheduling priority |
| `MAINTENANCE_TOKEN_BUDGET` | — | maintenance-lane token budget |
| `AGENT_POLICIES_PATH` | — | path to agent authorization policies |
| `PERMISSIONS_SIGNING_KEY` | — | signing key for elevated-permission tokens |
| `SPECIALIST_REGISTRY_PATH` | — | path to the specialist/domain registry |
| `OPENBAO_URL` | `http://openbao.arpa` | OpenBao address for out-of-band BMC creds (apps/idrac) |
| `OPENBAO_TOKEN` | — | OpenBao token with read on apps/data/idrac (agent-apps-rw) |
| `OS_PROVIDERTOOL` | `True` | MCP tools table (condensed action-routed surface). |
| `STORAGE_HEALTHTOOL` | `True` |  |
| `MISCTOOL` | `True` |  |
| `AGENT_HEALTHTOOL` | `True` |  |
| `IDENTITYTOOL` | `True` |  |
| `MAINTENANCETOOL` | `True` |  |
| `POLICYTOOL` | `True` |  |
| `SPECIALIST_REGISTRYTOOL` | `True` |  |
| `WATCHDOGTOOL` | `True` |  |

#### Inherited agent-utilities variables (apply to every connector)

| Variable | Example | Description |
|----------|---------|-------------|
| `MCP_TOOL_MODE` | `condensed` | Tool surface: `condensed` | `verbose` | `both` |
| `MCP_ENABLED_TOOLS` | — | Comma-separated tool allow-list |
| `MCP_DISABLED_TOOLS` | — | Comma-separated tool deny-list |
| `MCP_ENABLED_TAGS` | — | Comma-separated tag allow-list |
| `MCP_DISABLED_TAGS` | — | Comma-separated tag deny-list |
| `MCP_CLIENT_AUTH` | — | Outbound MCP auth (`oidc-client-credentials` for fleet calls) |
| `OIDC_CLIENT_ID` | — | OIDC client id (service-account auth) |
| `OIDC_CLIENT_SECRET` | — | OIDC client secret (service-account auth) |
| `DEBUG` | `False` | Verbose logging |
| `PYTHONUNBUFFERED` | `1` | Unbuffered stdout (recommended in containers) |
| `MCP_URL` | `http://localhost:8000/mcp` | URL of the MCP server the agent connects to |
| `PROVIDER` | `openai` | LLM provider for the agent |
| `MODEL_ID` | `gpt-4o` | Model id for the agent |
| `ENABLE_WEB_UI` | `True` | Serve the AG-UI web interface |

_28 package + 14 inherited variable(s). Auto-generated from `.env.example` + the shared agent-utilities set — do not edit._
<!-- ENV-VARS-TABLE:END -->


Every variable the server reads, grouped by purpose.

### MCP server / transport
| Variable | Description | Default |
|----------|-------------|---------|
| `TRANSPORT` | `stdio`, `streamable-http`, or `sse` | `stdio` |
| `HOST` | Bind host (HTTP transports) | `0.0.0.0` |
| `PORT` | Bind port (HTTP transports) | `8000` |
| `MCP_TOOL_MODE` | Tool surface: `condensed`, `verbose`, or `both` | `condensed` |
| `MCP_ENABLED_TOOLS` / `MCP_DISABLED_TOOLS` | Comma-separated tool allow/deny list | — |
| `MCP_ENABLED_TAGS` / `MCP_DISABLED_TAGS` | Comma-separated tag allow/deny list | — |
| `DEBUG` | Verbose logging | `False` |
| `PYTHONUNBUFFERED` | Unbuffered stdout (recommended in containers) | `1` |

### Connection & credentials
| Variable | Description | Default |
|----------|-------------|---------|
| `SYSTEMS_MANAGER_HOST` | Target host for remote telemetry/control (defaults to local) | — |

### Multi-host remote orchestration
| Variable | Description | Default |
|----------|-------------|---------|
| `PROJECT_ROOT` | Project root used to resolve config/inventory paths | — |
| `MCP_CONFIG_PATH` | Path to the MCP config (`mcp_config.json`) | — |

The remote inventory is loaded from `~/.config/agent_utilities/inventory.yaml` (XDG path);
see the [Multi-Host Architecture Guide](docs/multi_host.md).

### Tool toggles
Each action-routed tool can be disabled individually via its toggle env var (set to `false`).
The full list is in the [Available MCP Tools](#available-mcp-tools) table above
(e.g. `OS_PROVIDERTOOL`, `MISCTOOL`).

### Telemetry & governance
| Variable | Description | Default |
|----------|-------------|---------|
| `ENABLE_OTEL` | Enable OpenTelemetry export | `True` |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | OTLP collector endpoint | — |
| `OTEL_EXPORTER_OTLP_PUBLIC_KEY` / `OTEL_EXPORTER_OTLP_SECRET_KEY` | OTLP auth keys | — |
| `OTEL_EXPORTER_OTLP_PROTOCOL` | OTLP protocol (e.g. `http/protobuf`) | — |
| `EUNOMIA_TYPE` | Authorization mode: `none`, `embedded`, `remote` | `none` |
| `EUNOMIA_POLICY_FILE` | Embedded policy file | `mcp_policies.json` |
| `EUNOMIA_REMOTE_URL` | Remote Eunomia server URL | — |

### Agent runtime governance (full `[agent]` runtime only)
| Variable | Description | Default |
|----------|-------------|---------|
| `MCP_URL` | URL of the MCP server the agent connects to | `http://localhost:8000/mcp` |
| `PROVIDER` | LLM provider (e.g. `openai`) | `openai` |
| `MODEL_ID` | Model id (e.g. `gpt-4o`) | `gpt-4o` |
| `ENABLE_WEB_UI` | Serve the AG-UI web interface | `True` |
| `MAX_CONCURRENT_AGENTS` | Cap on concurrently dispatched sub-agents | — |
| `MAINTENANCE_PRIORITY` / `MAINTENANCE_TOKEN_BUDGET` | Maintenance-lane scheduling controls | — |
| `AGENT_POLICIES_PATH` | Path to agent authorization policies | — |
| `PERMISSIONS_SIGNING_KEY` | Signing key for elevated-permission tokens | — |
| `SPECIALIST_REGISTRY_PATH` | Path to the specialist/domain registry | — |

See [`.env.example`](.env.example) for a copy-paste starting point.

## Agent

This repository features a fully integrated Pydantic AI Graph Agent. It communicates over the **Agent Control Protocol (ACP)** and interacts seamlessly with the **Agent Web UI (AG-UI)** and Terminal interface.

### Running the Agent CLI
To start the interactive command-line agent:

```bash
# Optional: target a remote host for telemetry/control
export SYSTEMS_MANAGER_HOST="remote-host.local"

# Run the agent server
systems-manager-agent --provider openai --model-id gpt-4o
```

### Docker Compose Orchestration
The following `docker/agent.compose.yml` configures the Agent, Web UI, and Terminal Interface together:

```yaml
version: '3.8'

services:
  systems-manager-mcp:
    image: knucklessg1/systems-manager:mcp
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
      start_period: 10s
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "3"

  systems-manager-agent:
    image: knucklessg1/systems-manager:latest
    container_name: systems-manager-agent
    hostname: systems-manager-agent
    restart: always
    depends_on:
      - systems-manager-mcp
    env_file:
      - ../.env
    command: [ "systems-manager-agent" ]
    environment:
      - PYTHONUNBUFFERED=1
      - HOST=0.0.0.0
      - PORT=9009
      - MCP_URL=http://systems-manager-mcp:8000/mcp
      - PROVIDER=${PROVIDER:-openai}
      - MODEL_ID=${MODEL_ID:-gpt-4o}
      - ENABLE_WEB_UI=True
      - ENABLE_OTEL=True
    ports:
      - "9009:9009"
    healthcheck:
      test: ["CMD", "python3", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:9009/health')"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 10s
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "3"

```

Detailed graph node architecture explanations, custom skill configurations, and agentic trace guides are available in [docs/agent.md](docs/agent.md).

---

## Security & Governance

Built directly upon the enterprise-ready [`agent-utilities`](https://github.com/Knuckles-Team/agent-utilities) core, standard security parameters are fully supported:

### Access Control & Policy Enforcement
- **Eunomia Policies:** Fine-grained, policy-driven tool authorization. Supports `none`, local `embedded` (`mcp_policies.json`), or centralized `remote` modes.
- **OIDC Token Delegation:** Compliant with RFC 8693 token exchange for flowing authenticating user credentials from Web UI / ACP → Agent → MCP.
- **Scoped Credentials:** Execution context runs restricted to the specific caller identity.

### Runtime Security Grid
| Feature | Functionality | Enablement |
|---------|---------------|------------|
| **Tool Guard** | Sensitivity inspection with human-in-the-loop validation | Enabled by default |
| **Prompt Injection Defense** | Input scanning, repetition monitoring, and recursive loop blocks | Enabled by default |
| **Context Safety Guard** | Stuck-loop detectors and contextual overflow preemptive alerts | Enabled by default |

---

## Installation

Pick the extra that matches what you want to run:

| Extra | Installs | Use when |
|-------|----------|----------|
| `systems-manager[mcp]` | Slim MCP server only (`agent-utilities[mcp]` — FastMCP/FastAPI) | You only run the **MCP server** (smallest install / image) |
| `systems-manager[agent]` | Full agent runtime (`agent-utilities[agent,logfire]` — Pydantic AI + the epistemic-graph engine) | You run the **integrated agent** |
| `systems-manager[all]` | Everything (`mcp` + `agent` + `logfire`) | Development / both surfaces |

```bash
# MCP server only (recommended for tool hosting — slim deps)
uv pip install "systems-manager[mcp]"

# Full agent runtime (Pydantic AI + epistemic-graph engine)
uv pip install "systems-manager[agent]"

# Everything (development)
uv pip install "systems-manager[all]"      # or: python -m pip install "systems-manager[all]"
```

### Container images (`:mcp` vs `:agent`)

One multi-stage `docker/Dockerfile` builds two right-sized images, selected by `--target`:

| Image tag | Build target | Contents | Entrypoint |
|-----------|--------------|----------|------------|
| `knucklessg1/systems-manager:mcp` | `--target mcp` | `systems-manager[mcp]` — **slim**, no engine/`pydantic-ai`/`dspy`/`llama-index`/`tree-sitter` | `systems-manager-mcp` |
| `knucklessg1/systems-manager:latest` | `--target agent` (default) | `systems-manager[agent]` — **full** agent runtime + epistemic-graph engine | `systems-manager-agent` |

```bash
docker build --target mcp   -t knucklessg1/systems-manager:mcp    docker/   # slim MCP server
docker build --target agent -t knucklessg1/systems-manager:latest docker/   # full agent
```

`docker/mcp.compose.yml` runs the slim `:mcp` server; `docker/agent.compose.yml` runs the
agent (`:latest`) with a co-located `:mcp` sidecar.

### Knowledge-graph database (`epistemic-graph`)

The **full agent** (`[agent]` / `:latest`) embeds the **epistemic-graph** engine (pulled in
transitively via `agent-utilities[agent]`). For production — or to share one knowledge graph
across multiple agents — run **epistemic-graph as its own database container** and point the
agent at it instead of embedding it. Deployment recipes (single-node + Raft HA), connection
config, and the full database architecture (with diagrams) are documented in the
[epistemic-graph deployment guide](https://knuckles-team.github.io/epistemic-graph/deployment/).
The slim `[mcp]` server does **not** require the database.

---

## Documentation

The complete documentation is published as the
[official documentation site](https://knuckles-team.github.io/systems-manager/) and is
the recommended reference for installation, deployment, and day-to-day operation.

| Page | Contents |
|---|---|
| [Installation](https://knuckles-team.github.io/systems-manager/installation/) | pip, source, extras, prebuilt Docker image |
| [Deployment](https://knuckles-team.github.io/systems-manager/deployment/) | run the MCP and agent servers, Compose, Caddy + Technitium, env config |
| [Usage](https://knuckles-team.github.io/systems-manager/usage/) | the MCP tools, the `SystemsManager` API, the CLI |
| [Overview](https://knuckles-team.github.io/systems-manager/overview/) | ecosystem role and concept map |
| [Sudo Security](https://knuckles-team.github.io/systems-manager/sudo_security/) | least-privilege elevated-execution model |
| [Multi-Host](https://knuckles-team.github.io/systems-manager/multi_host/) | zero-script remote telemetry and control plane |
| [Day 0 Installation](https://knuckles-team.github.io/systems-manager/day_0_provisioning/) | bare-metal to managed cluster node |

`AGENTS.md` is the canonical contributor/agent guidance.

---

## Repository Owners

<img width="100%" height="180em" src="https://github-readme-stats.vercel.app/api?username=Knucklessg1&show_icons=true&hide_border=true&&count_private=true&include_all_commits=true" />

![GitHub followers](https://img.shields.io/github/followers/Knucklessg1)
![GitHub User's stars](https://img.shields.io/github/stars/Knucklessg1)

---

## Contribute

Contributions are welcome! Please ensure code quality by executing local checks before submitting pull requests:
- Format code using `ruff format .`
- Lint code using `ruff check .`
- Validate type-safety with `mypy .`
- Execute test suites using `pytest`


<!-- BEGIN agent-os-genesis-deploy (generated; do not edit between markers) -->

## Deploy with `agent-os-genesis`

This package can be provisioned for you — skill-guided — by the **`agent-os-genesis`**
universal skill (its *single-package deploy mode*): it picks your install method, seeds
secrets to OpenBao/Vault (or `.env`), trusts your enterprise CA, registers the MCP
server, and verifies it — the same machinery that stands up the whole Agent OS, narrowed
to just this package. Ask your agent to **"deploy `systems-manager` with agent-os-genesis"**.

| Install mode | Command |
|------|---------|
| Bare-metal, prod (PyPI) | `uvx systems-manager-mcp` · or `uv tool install systems-manager` |
| Bare-metal, dev (editable) | `uv pip install -e ".[all]"` · or `pip install -e ".[all]"` |
| Container, prod | deploy `knucklessg1/systems-manager:latest` via docker-compose / swarm / podman / podman-compose / kubernetes |
| Container, dev (editable) | deploy `docker/compose.dev.yml` (source-mounted at `/src`; edits live on restart) |

Secrets are read-existing + seeded via `vault_sync` — you are only prompted for what's missing.

<!-- END agent-os-genesis-deploy -->
