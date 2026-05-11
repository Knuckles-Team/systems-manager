# systems-manager — Concept Overview

> **Category**: Infrastructure | **Ecosystem Role**: MCP Server + A2A Agent
> Built on [`agent-utilities`](https://github.com/Knuckles-Team/agent-utilities) — the unified AGI Harness.

## Description

Systems Manager will update your system and install/upgrade applications. Additionally, as allow AI to perform these activities as an MCP Server

## Enterprise Readiness

All agents in the ecosystem inherit enterprise-grade infrastructure from `agent-utilities`:

| Feature | Status | Source |
|:--------|:-------|:-------|
| **JWT/OIDC Authentication** | ✅ Built-in | `agent-utilities[auth]` — Authlib JWKS + API key middleware |
| **OpenTelemetry Instrumentation** | ✅ Built-in | `agent-utilities[logfire]` — OTLP export, FastAPI auto-instrumentation |
| **HashiCorp Vault Integration** | ✅ Built-in | `agent-utilities[vault]` — `secret://`, `env://`, `vault://` URI schemes |
| **Audit Logging** | ✅ Built-in | Append-only compliance trail with 30+ action types (CONCEPT:OS-5.4) |
| **Token Usage Analytics** | ✅ Built-in | 4-bucket tracking with budget alerting (CONCEPT:OS-5.4) |
| **Prompt Injection Defense** | ✅ Built-in | 25+ pattern scanner + jailbreak taxonomy (CONCEPT:OS-5.1) |
| **Guardrail Engine** | ✅ Built-in | Input/output interception with block/redact/warn (CONCEPT:OS-5.3) |
| **Action Execution Pipeline** | ✅ Built-in | Token, cost, duration, and node transition limits Dry-run / commit / rollback phases (CONCEPT:ORCH-1.4) |
| **Resource Scheduling** | ✅ Built-in | Priority queuing + preemption limits (CONCEPT:OS-5.2) |
| **Session Concurrency** | ✅ Built-in | Enqueue/reject/interrupt/rollback (CONCEPT:OS-5.3) |

## Concept Registry

This project implements or inherits the following ecosystem concepts:

| Concept ID | Description | Source |
|:-----------|:------------|:-------|
| SYS-1.0 | Abstracted OS Provider | `systems-manager` |
| SYS-1.1 | Distributed Fleet Control Plane | `systems-manager` |
| SYS-1.2 | Deep Introspection Telemetry | `systems-manager` |
| SYS-1.3 | Package & Service Mutation | `systems-manager` |
| ECO-4.1 | MCP & Universal Skills | `agent-utilities` (inherited) |
| OS-5.0 | Agent OS Kernel | `agent-utilities` (inherited) |
| OS-5.2 | Resource Scheduling | `agent-utilities` (inherited) |

> 📖 **Full Breakdown**: See [Pillar 1: Agent OS Layer](pillars/1_agent_os_layer.md) for deep dives into `SYS-1.X`.

> 📖 **Full Registry**: See [`agent-utilities/docs/overview.md`](https://github.com/Knuckles-Team/agent-utilities/blob/main/docs/overview.md) for the complete 5-Pillar concept index.

## Architecture

The `systems-manager` acts as the physical execution layer (Agent OS Layer) driven by the core `agent-utilities` kernel.

```mermaid
flowchart TD
    subgraph Agent OS Kernel (agent-utilities)
        Orchestrator[Graph Orchestrator]
        Auth[Permissions Kernel]
    end

    subgraph Agent OS Layer (systems-manager)
        MCP[MCP Server]
        OSProvider[Abstracted OS Provider]
        Linux[Linux Backend]
        Windows[Windows Backend]
    end

    Orchestrator -->|Tool Calls| MCP
    Auth -->|Token Validation| MCP
    MCP --> OSProvider
    OSProvider --> Linux
    OSProvider --> Windows
```

This project follows the standardized agent-package pattern:

```text
systems-manager/
├── systems_manager/        # Source code
│   ├── __init__.py
│   ├── agent_server.py      # Entry point (create_graph_agent_server)
│   ├── api_client.py        # REST/GraphQL API wrapper
│   └── mcp_server.py        # FastMCP tool definitions
├── tests/                   # Test suite
├── docs/                    # Documentation
├── pyproject.toml           # Package metadata
├── mcp_config.json          # MCP server configuration
├── main_agent.json          # Agent identity & system prompt
└── Dockerfile               # Container deployment
```

## MCP Configuration

### stdio Mode
```json
{
  "mcpServers": {
    "systems-manager": {
      "command": "uv",
      "args": ["run", "--with", "systems-manager", "systems-mcp"],
      "env": {}
    }
  }
}
```

### Streamable HTTP Mode
```bash
systems-mcp --transport streamable-http --port 8001
```
