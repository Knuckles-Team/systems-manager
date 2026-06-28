# Concept Registry — systems-manager

> **Prefix**: `CONCEPT:SYS-*`
> **Version**: 1.15.0
> **Bridge**: [`CONCEPT:ECO-4.0`](https://knuckles-team.github.io/agent-utilities/concepts/) (Unified Toolkit Ingestion)

---

## Project-Specific Concepts

| Concept ID | Name | Description |
|------------|------|-------------|
| `CONCEPT:SYS-001` | Agent Health Operations | MCP tool domain `agent_health` — Action-routed dynamic tool registration |
| `CONCEPT:SYS-002` | Identity Operations | MCP tool domain `identity` — Action-routed dynamic tool registration |
| `CONCEPT:SYS-003` | Maintenance Operations | MCP tool domain `maintenance` — Action-routed dynamic tool registration |
| `CONCEPT:SYS-004` | Os Provider Operations | MCP tool domain `os_provider` — Action-routed dynamic tool registration |
| `CONCEPT:SYS-005` | Policy Operations | MCP tool domain `policy` — Action-routed dynamic tool registration |
| `CONCEPT:SYS-006` | Specialist Registry Operations | MCP tool domain `specialist_registry` — Action-routed dynamic tool registration |
| `CONCEPT:SYS-007` | Watchdog Operations | MCP tool domain `watchdog` — Action-routed dynamic tool registration |
| `CONCEPT:SYS-1.4` | Physical Storage Health | MCP tool domain `storage_health` — SMART (incl. RAID megaraid passthrough), RAID physical-disk state, and a combined `report` correlating media health with controller state. Manager-seam (local or remote host). |
| `CONCEPT:SYS-1.5` | BMC Drive-Fault Correlation | BMC/IPMI drive-slot fault detection (reusing the `fan-manager` IPMI wrapper, in-band or OpenBao-credentialed out-of-band) wired into `system_health_check`; a BMC-flagged disk with clean SMART media is classified as a link/aging fault, not media wear. |

## Cross-Project References (from agent-utilities)

| Concept ID | Name | Origin |
|------------|------|--------|
| `CONCEPT:ECO-4.0` | Unified Toolkit Ingestion | agent-utilities |
| `CONCEPT:ORCH-1.2` | Confidence-Gated Router | agent-utilities |
| `CONCEPT:OS-5.1` | Prompt Injection Defense | agent-utilities |
| `CONCEPT:OS-5.2` | Cognitive Scheduler | agent-utilities |
| `CONCEPT:OS-5.3` | Guardrail Engine | agent-utilities |
| `CONCEPT:OS-5.4` | Audit Logging | agent-utilities |
| `CONCEPT:KG-2.0` | Knowledge Graph Core | agent-utilities |

## Synergy with agent-utilities

This project integrates with `agent-utilities` via `CONCEPT:ECO-4.0` (Unified Toolkit Ingestion). The `systems_manager` MCP server registers its tools with the agent-utilities FastMCP middleware, enabling automatic discovery, telemetry, and Knowledge Graph ingestion of all SYS-* concepts.
