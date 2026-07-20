# Provider workflow catalog

Load only the workflow relevant to the current request. Start with `list_actions` on an
action-routed tool when the live schema is not already present in the delegated tool
description.

## Tool map

| Need | Current typed tool |
| --- | --- |
| OS, packages, cleanup, statistics, uptime | `sm_system_operations` |
| Service lifecycle | `sm_service_operations` or provider `manage_service` |
| Process inspection or termination | `sm_process_operations`, `get_process_details` |
| Interfaces, ports, DNS, bounded probes | `sm_network_operations`, `get_network_connections` |
| Filesystems and volume capacity | `sm_disk_operations` |
| SMART, RAID, and BMC drive-fault correlation | `sm_storage_health` |
| Managed files and system logs | `sm_file_operations`, `query_system_logs` |
| Firewall rules | `sm_firewall_operations` |
| Cron inventory and removal | `sm_cron_operations` |
| Agent identity | `sm_agent_identity_operations` |
| Specialist registry | `sm_agent_specialist_operations` |
| Scheduler and watchdog | `sm_agent_scheduler_operations`, `sm_agent_watchdog_operations` |
| Privacy-safe host graph projection | `systems_ingest_host` |

## Read and troubleshoot

1. Confirm the GraphSession, tenant, authenticated service boundary, and direct or
   proxy-terminated TLS boundary.
2. Use the narrowest read action. Sensitive reads and active probes require their deployment
   policy gates even when they do not mutate the host.
3. Keep returned evidence bounded. Do not repeat hostnames, addresses, file paths, environment
   values, or log content unless the authorized request needs the value in the immediate
   response; never persist it in a skill, trace, or graph projection.
4. Correlate observations only after each underlying read succeeds. Treat partial or unknown
   state as unknown, not healthy.

## Mutate and verify

1. Read the current state and identify the exact target by its runtime opaque alias.
2. State impact and request the provider's destructive-operation confirmation.
3. Respect `SYSTEMS_MANAGER_ALLOW_HOST_MUTATIONS`,
   `SYSTEMS_MANAGER_ALLOW_FILESYSTEM_MUTATIONS`, and tool-specific restrictions.
4. Send only typed parameters. Do not translate a denied or unavailable operation into a raw
   command, generic file write, scheduled command, or another provider.
5. Read the same state again and report the observed outcome. Never infer success from the
   mutation response alone.

## Storage and BMC health

Use `sm_storage_health` with `report`, `smart`, `faults`, or `raid`. Start in-band. Set
`out_of_band=true` only when the deployment has projected a checked
`SYSTEMS_MANAGER_BMC_CREDENTIALS` secret containing exactly `host`, `user`, and `password`.
The provider consumes that value internally and must never return it. An optional `bmc_host`
may select a configured controller, but it is not a credential channel.

The current contract is diagnostic. It does not expose BMC power control, serial consoles,
LAN/user configuration, or NIC-bond provisioning. Return an unsupported-capability result
when those operations are requested.

## Host graph ingestion

1. Obtain current host telemetry through typed reads.
2. Confirm `SYSTEMS_MANAGER_PSEUDONYMIZATION_KEY` is available through AgentConfig and the
   epistemic-graph session is authorized for a governed write.
3. Call `systems_ingest_host`. Its allowlisted projection emits only `HardwareNode`,
   `NetworkInterface`, and `DiskVolume` fields and `hasInterface` / `hasVolume` edges.
4. Verify node and edge counts. Do not add arbitrary fields, raw names, addresses, identifiers,
   or paths to compensate for rejected content.

## Tracing

Keep `LANGFUSE_CAPTURE_CONTENT=false`. Emit status, duration, action class, opaque correlation
references, and sanitized errors only. TLS trust, endpoints, keys, and private identifiers
remain runtime AgentConfig inputs.
