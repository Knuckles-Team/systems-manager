---
name: sm-host-inspection
skill_type: skill
description: >-
  Assess host health and read logs, traces and graph snapshots through systems-manager: capabilities, uptime, OS and hardware statistics, health check, snapshot capture, host graph ingest, system logs and kernel modules. Use for health reviews and fault investigation. Read-only apart from the graph ingest.
---

# sm-host-inspection

Read-only host assessment. Start broad with the health tools, then narrow to logs.

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
