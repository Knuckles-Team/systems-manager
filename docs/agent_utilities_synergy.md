# Agent-Utilities Synergy

Because `systems-manager` acts as the physical execution layer (Agent OS Layer) for the `agent-utilities` OS Kernel, their integration unlocks emergent capabilities that neither project possesses independently.

## 1. Automated Anomaly Defense (Security Operations)

The `AgentHealthTools` inside `agent-utilities` continuously monitors the environment. By leveraging `SM-OS.deployment.deep-introspection-telemetry` (Deep Introspection Telemetry) from `systems-manager`, the kernel can achieve EDR-like (Endpoint Detection and Response) capabilities.

**Workflow:**
1. `agent-utilities` detects an unknown IP address communicating on the network.
2. It invokes `systems-manager`'s `get_network_connections()`.
3. `systems-manager` maps the unknown TCP socket to `PID 4092`.
4. `agent-utilities` analyzes the executable path and command-line arguments using `get_process_details(pid=4092)`.
5. If determined to be malicious, `agent-utilities` invokes a destructive action to terminate the PID and ban the IP.

## 2. Self-Healing Infrastructure

When paired with `agent-utilities`' capability to read alerts (e.g., from Prometheus or PagerDuty), `systems-manager` provides the remediation engine.

**Workflow:**
1. `agent-utilities` receives an alert: "Web Server 502 Bad Gateway".
2. It uses `systems-manager`'s `query_system_logs(limit=100)` to read the `journalctl` output for the `nginx` service.
3. The LLM diagnoses an Out-of-Memory (OOM) error.
4. `agent-utilities` uses `manage_service(service_name="nginx", action="restart")` to perform a self-healing action securely, generating an audit trail automatically.

## 3. Fleet-Wide Configuration Audits

Using the Distributed Fleet Control Plane (`SYS-1.1`), `agent-utilities` can audit 10,000+ hosts simultaneously.

**Workflow:**
1. Agent intent: "Ensure all production servers are running the updated OpenSSL package."
2. The Orchestrator calls the `systems-manager` MCP.
3. The `systems-manager` Control Plane broadcasts the package query via NATS.
4. `agent-utilities` receives a summarized context: "9,500 patched. 500 vulnerable."
5. `agent-utilities` generates an automated remediation plan, utilizing Sub-Agent Dispatch to patch the 500 vulnerable hosts in parallel.
