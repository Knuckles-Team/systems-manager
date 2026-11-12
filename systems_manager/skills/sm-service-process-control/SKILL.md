---
name: sm-service-process-control
skill_type: skill
description: >-
  Inspect and control services and processes through systems-manager: list and read services, start, stop, restart, enable and disable them (typed and provider-level tools), list and inspect processes and kill one. Use for service outages and runaway processes.
---

# sm-service-process-control

Service and process control. Read status first, change one service at a time, read it back.

## Services

- `list_services`: provider-level service inventory
- `sm_service_list_services`: list services
- `sm_service_get_service_status`: status of one service
- `sm_service_start_service`: start
- `sm_service_stop_service`: stop
- `sm_service_restart_service`: restart
- `sm_service_enable_service`: enable at boot
- `sm_service_disable_service`: disable at boot

## Provider lifecycle

- `manage_service_start`: start
- `manage_service_stop`: stop
- `manage_service_restart`: restart
- `manage_service_enable`: enable
- `manage_service_disable`: disable

## Processes

- `sm_process_list_processes`: list processes
- `sm_process_get_process_info`: read one process
- `get_process_details`: detailed process view
- `get_network_connections`: sockets and connections
- `sm_process_kill_process`: kill a process

## Rules

- Read the state before a change and again after it.
- A destructive tool needs the requester's explicit confirmation (`confirm=true`).
- A policy denial is final; never route around it with another tool.
