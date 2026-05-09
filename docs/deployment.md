# Systems-Manager Deployment Architecture

The `systems-manager` is designed to be highly scalable. It can be run locally on a single machine or deployed as a decentralized fleet orchestrator for 10,000+ nodes.

## Mode A: Single-Node Deployment (Standard)

The standard mode runs `systems-manager` as an MCP Server directly on the host that the Agent is interacting with.

**Use Case:** Local troubleshooting, dedicated CI/CD runner management, or simple homelab environments.

### stdio Mode
The Agent process spawns the MCP Server as a subprocess and communicates via standard input/output.
```json
{
  "mcpServers": {
    "systems-manager": {
      "command": "uv",
      "args": ["run", "--with", "systems-manager", "systems-mcp"],
      "env": {
        "REQUIRE_ADMIN": "true"
      }
    }
  }
}
```

### Streamable HTTP Mode (SSE)
Alternatively, you can run the server in HTTP mode. This allows the Agent to exist on a separate container while still communicating 1:1 with the host.
```bash
# Start the HTTP Server on the target host
sudo uv run systems-mcp --transport streamable-http --port 8001
```

---

## Mode B: Distributed Fleet Deployment (Enterprise)

To manage 10,000+ hosts, creating 10,000 `mcpServers` entries is impossible. Instead, `systems-manager` uses a **Message Broker (Control Plane)** architecture.

### Architectural Diagram

```mermaid
flowchart TD
    Agent[Agent Utilities OS Kernel]

    subgraph Control Plane
        MCP[Central MCP Server]
        NATS[(NATS / RabbitMQ Broker)]
    end

    subgraph Fleet Nodes
        Node1[Host 1: systems-mcp --daemon]
        Node2[Host 2: systems-mcp --daemon]
        Node3[Host N: systems-mcp --daemon]
    end

    Agent -->|1 Tool Call: list_services()| MCP
    MCP -->|Publish Event| NATS
    NATS -.->|Fan-out| Node1
    NATS -.->|Fan-out| Node2
    NATS -.->|Fan-out| Node3
    Node1 -.->|JSON Result| NATS
    Node2 -.->|JSON Result| NATS
    Node3 -.->|JSON Result| NATS
    NATS -->|Aggregate 10k JSONs| MCP
    MCP -->|1 Summary Payload| Agent
```

### How it Works

1. **The Daemon**: On every host (Linux or Windows), `systems-manager` is installed as a background service using the `--daemon` flag. Instead of exposing an HTTP port, it securely connects to your Message Broker.
2. **The Aggregator**: The Central MCP Server exposes the exact same tools (e.g., `get_network_connections(pid=None)`). However, when the Agent calls the tool, the MCP Server broadcasts the request to the fleet.
3. **Payload Compression**: 10,000 hosts returning process trees would overwhelm the LLM's context window. The Central MCP Server uses MapReduce logic to aggregate the responses:
   - *Example Output*: "9,998 hosts are running nginx v1.18. 2 hosts are offline."

### Example Configuration

**1. Daemon (On Host):**
```bash
# Connects to the Control Plane
sudo systems-mcp --daemon --broker tls://nats.internal:4222
```

**2. Control Plane (For the Agent):**
```json
{
  "mcpServers": {
    "systems-fleet-manager": {
      "command": "systems-mcp",
      "args": ["--control-plane", "--broker", "tls://nats.internal:4222"]
    }
  }
}
```
