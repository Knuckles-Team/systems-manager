---
name: sm-host-inspection
skill_type: skill
description: >-
  Assess host health and read logs, traces and graph snapshots through systems-manager: capabilities, uptime, OS and hardware statistics, health check, snapshot capture, host graph ingest, system logs and kernel modules. Use for health reviews and fault investigation. Read-only apart from the graph ingest.
---

# sm-host-inspection

Read-only host assessment. Start broad with the health tools, then narrow to logs.

## Steps

1. Confirm the provider is alive with `health_check` and verify the response reports a healthy status before reading anything else.
2. Read what this host supports with `get_management_capabilities` and verify the tool you plan to use appears in the returned list.
3. Collect the baseline with `sm_system_get_uptime`, `sm_system_get_os_statistics` and `sm_system_get_hardware_statistics`, and verify each returns data for the expected host.
4. Get the aggregate verdict with `sm_system_system_health_check` and verify its status field before drilling into logs.
5. Narrow to the fault with `query_system_logs`, `sm_file_tail_log_file` or `list_kernel_modules`, and verify the entries fall inside the time window of the reported problem.
6. Write the host projection to the graph only when asked, using `systems_ingest_host`, and verify the call returns an accepted result.

## Failure recovery

| Failure | Cause | Recovery |
|---|---|---|
| `health_check` returns an error or no response | The systems-manager MCP server is not running or not reachable from this session | Start the server with `systems-manager-mcp` and call `health_check` again after the process is listed as running |
| Log or trace tool is denied | The deployment gate for sensitive reads is closed | Report the denial to the requester and stop, because a policy denial is final |
| `sm_file_tail_log_file` reports the path is outside the managed root | The requested log file is not under the managed filesystem root | Pick a path returned by `sm_file_get_system_logs` instead |
| `systems_ingest_host` is rejected | The pseudonymization key is not provided by the deployment | Ask the operator to set the key in the deployment configuration and leave the call unchanged until then |

## Health

- `health_check`: service liveness
- `get_management_capabilities`: what this host supports
- `sm_system_get_uptime`: uptime
- `sm_system_get_os_statistics`: OS statistics
- `sm_system_get_hardware_statistics`: CPU and memory
- `sm_system_system_health_check`: aggregate host health
- `capture_system_snapshot`: bounded host snapshot

## Graph

- `systems_ingest_host`: write a privacy-safe host projection to the knowledge graph

## Logs and traces

- `query_system_logs`: query system logs
- `sm_file_get_system_logs`: read system log files
- `sm_file_tail_log_file`: tail one log file
- `list_kernel_modules`: loaded kernel modules
- `start_system_trace`: start a bounded trace
- `stop_system_trace`: stop the trace

## Rules

- Read the state before a change and again after it.
- A destructive tool needs the requester's explicit confirmation (`confirm=true`).
- A policy denial is final; never route around it with another tool.
