# Concept Registry — systems-manager

> **Prefix**: `CONCEPT:SYS-*`
> **Version**: 1.15.0
> **Bridge**: [`CONCEPT:AU-ECO.messaging.native-backend-abstraction`](https://knuckles-team.github.io/agent-connector-sdk/concepts/) (Unified Toolkit Ingestion)

---

## Project-Specific Concepts

| Concept ID | Name | Description |
|------------|------|-------------|
| `CONCEPT:SM-OS.governance.sys` | Agent Health Operations | MCP tool domain `agent_health` — Action-routed dynamic tool registration |
| `CONCEPT:SM-OS.governance.sys-2` | Identity Operations | MCP tool domain `identity` — Action-routed dynamic tool registration |
| `CONCEPT:SM-OS.governance.sys-4` | Os Provider Operations | MCP tool domain `os_provider` — Action-routed dynamic tool registration |
| `CONCEPT:SM-OS.governance.sys-6` | Specialist Registry Operations | MCP tool domain `specialist_registry` — Action-routed dynamic tool registration |
| `CONCEPT:SM-OS.governance.sys-7` | Watchdog Operations | MCP tool domain `watchdog` — Action-routed dynamic tool registration |
| `CONCEPT:SM-OS.governance.sys-8` | Physical Storage Health | MCP tool domain `storage_health` — SMART (including RAID passthrough), RAID physical-disk state, and a combined local-host report correlating media health with controller state. |
| `CONCEPT:SM-OS.governance.bay-bmc-flags-as` | BMC Drive-Fault Correlation | BMC/IPMI drive-slot fault detection, in-band or through an exact AgentConfig-projected out-of-band credential, wired into `system_health_check`; a BMC-flagged disk with clean SMART media is classified as a link/aging fault, not media wear. |

## Cross-Project References (from scion-sdk)

| Concept ID | Name | Origin |
|------------|------|--------|
| `CONCEPT:AU-ECO.messaging.native-backend-abstraction` | Unified Toolkit Ingestion | scion-sdk |
| `CONCEPT:AU-ORCH.adapter.hot-cache-invalidation` | Confidence-Gated Router | scion-sdk |
| `CONCEPT:AU-OS.config.secrets-authentication` | Prompt Injection Defense | scion-sdk |
| `CONCEPT:AU-OS.state.cognitive-scheduler-preemption` | Cognitive Scheduler | scion-sdk |
| `CONCEPT:AU-OS.governance.reactive-multi-axis-budget` | Guardrail Engine | scion-sdk |
| `CONCEPT:AU-OS.governance.wasm-micro-agent-sandbox` | Audit Logging | scion-sdk |
| `CONCEPT:AU-KG.query.object-graph-mapper` | Knowledge Graph Core | scion-sdk |

## Synergy with scion-sdk

This project integrates with `scion-sdk` via `CONCEPT:AU-ECO.messaging.native-backend-abstraction` (Unified Toolkit Ingestion). The `systems_manager` MCP server registers its tools with the scion-sdk FastMCP middleware, enabling automatic discovery, telemetry, and Knowledge Graph ingestion of all SYS-* concepts.
