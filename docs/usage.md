# Usage — API / CLI / MCP

`systems-manager` exposes the same capability several ways: as **MCP tools** an agent
calls, as a **Python API** you import, and as a **CLI** for direct package
management. The full ecosystem role and concept map are in [Overview](overview.md).

## As an MCP server

Once [deployed](deployment.md), the server defaults to the compact intent surface and
keeps consolidated action-routed modules as the governed backing capabilities. Load
only the domain needed for the current request, then discover its exact action schema.

| Tool | Operations |
|---|---|
| `sm_system_operations` | install / update / clean / optimize, OS + hardware statistics, package search, health check, uptime, env vars |
| `sm_service_operations` | manage system services |
| `sm_process_operations` | inspect and manage processes |
| `sm_network_operations` | network analysis |
| `sm_disk_operations` | manage disks |
| `sm_user_operations` | user and group management |
| `sm_file_operations` | file and log management |
| `sm_cron_operations` | manage cron jobs |
| `sm_firewall_operations` | firewall management |
| `sm_storage_health` | SMART, RAID, and optional BMC drive-fault diagnostics |
| `systems_ingest_host` | privacy-safe governed host graph ingestion |

Agent identity, specialist registry, scheduler, and watchdog
domains are also registered when their current provider toggles are enabled.

Example agent prompts that map onto these tools:

- *"Update the system and install git and htop"* → `sm_system_operations`
- *"Show the hardware statistics for this host"* → `sm_system_operations`
- *"Which processes are using the most memory?"* → `sm_process_operations`

Tool modules are individually togglable with environment switches (for example,
`MISCTOOL`) and can be filtered through the current Agent Utilities visibility
configuration. A denied or unavailable capability must not be translated into a raw
command or generic file mutation.

## As a Python API

`detect_and_create_manager()` returns the appropriate `SystemsManagerBase`
implementation for the current operating system (`apt`, `dnf`, `zypper`, `pacman`, or
Windows), so the same calls work across distributions.

```python
from systems_manager.systems_manager import detect_and_create_manager

manager = detect_and_create_manager(silent=True)

# Reads — telemetry that degrades gracefully
os_stats = manager.get_os_statistics()         # CPU, memory, load, OS metadata
hw_stats = manager.get_hardware_statistics()   # hardware inventory
logs = manager.get_system_logs(lines=100)      # recent journal / system logs
```

For fleet operations, delegate to an authenticated instance on the target host or
compose the governed tunnel-manager capability through GraphOS. See
[Multi-Host](multi_host.md).

## As a CLI

The `systems-manager` console script drives package management and host maintenance
directly:

```bash
# Update packages and install applications
systems-manager --update --install "git,curl,htop"

# Install Python modules
systems-manager --python "ruff,pytest"

# Clean and optimize the system
systems-manager --clean --optimize

# Display telemetry
systems-manager --os-stats
systems-manager --hw-stats
```

The optional helper must be provisioned by the deployment boundary; the CLI does not
write sudoers policy. See [Sudo Security](sudo_security.md). Run
`systems-manager --help` for the complete flag list.
