# Concept Registry — systems-manager

> **Prefix**: `CONCEPT:SYS-*`
> **Version**: 1.15.0
> **Bridge**: [`CONCEPT:AU-ECO.messaging.native-backend-abstraction`](https://knuckles-team.github.io/agent-utilities/concepts/) (Unified Toolkit Ingestion)

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

## Cross-Project References (from agent-utilities)

| Concept ID | Name | Origin |
|------------|------|--------|
| `CONCEPT:AU-ECO.messaging.native-backend-abstraction` | Unified Toolkit Ingestion | agent-utilities |
| `CONCEPT:AU-ORCH.adapter.hot-cache-invalidation` | Confidence-Gated Router | agent-utilities |
| `CONCEPT:AU-OS.config.secrets-authentication` | Prompt Injection Defense | agent-utilities |
| `CONCEPT:AU-OS.state.cognitive-scheduler-preemption` | Cognitive Scheduler | agent-utilities |
| `CONCEPT:AU-OS.governance.reactive-multi-axis-budget` | Guardrail Engine | agent-utilities |
| `CONCEPT:AU-OS.governance.wasm-micro-agent-sandbox` | Audit Logging | agent-utilities |
| `CONCEPT:AU-KG.query.object-graph-mapper` | Knowledge Graph Core | agent-utilities |

## Synergy with agent-utilities

This project integrates with `agent-utilities` via `CONCEPT:AU-ECO.messaging.native-backend-abstraction` (Unified Toolkit Ingestion). The `systems_manager` MCP server registers its tools with the agent-utilities FastMCP middleware, enabling automatic discovery, telemetry, and Knowledge Graph ingestion of all SYS-* concepts.
