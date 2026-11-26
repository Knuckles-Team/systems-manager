---
name: sm-service-process-control
skill_type: skill
description: >-
  Inspect and control services and processes through systems-manager: list and read services, start, stop, restart, enable and disable them (typed and provider-level tools), list and inspect processes and kill one. Use for service outages and runaway processes.
---

# sm-service-process-control

Service and process control. Read status first, change one service at a time, read it back.

## Steps

1. Read the service with `sm_service_get_service_status` and verify the reported state before changing anything.
2. Change one service with `sm_service_start_service`, `sm_service_stop_service` or `sm_service_restart_service`, and verify by calling `sm_service_get_service_status` again.
3. Set boot behaviour with `sm_service_enable_service` or `sm_service_disable_service`, and verify the enabled flag in the next status read.
4. Inspect processes with `sm_process_list_processes` and `sm_process_get_process_info`, and verify the process id and owner before acting on it.
5. Stop a process with `sm_process_kill_process` only on explicit confirmation, passing `confirm=true`, and verify the process no longer appears in `sm_process_list_processes`.

## Failure recovery

| Failure | Cause | Recovery |
|---|---|---|
| `sm_service_get_service_status` reports the unit is unknown | The service name is wrong for this host | List names with `sm_service_list_services` and use the exact one returned |
| `sm_process_kill_process` is rejected | `confirm=true` was not supplied | Obtain the requester's confirmation and pass `confirm=true` |
| A restart is denied by policy | Host mutation is not enabled for this deployment | Report the denial and stop, because a policy denial is final |
| The service returns to failed after a restart | The underlying fault is not fixed | Read `query_system_logs` for the unit and report the error to the requester |

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
