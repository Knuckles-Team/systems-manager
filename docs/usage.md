# Usage — API / CLI / MCP

`systems-manager` exposes the same capability multiple ways: as **MCP tools** an agent
calls, as a **Python API** the operator import, and as a **CLI** for direct package
management. The full ecosystem role and concept map are in [Overview](overview.md).

## As an MCP server

Once [deployed](deployment.md), the server exposes one typed tool per host operation.
Load only the domain needed for the current request and read each tool's schema.

| Tool family | Operations |
|---|---|
| `sm_system_*` | install, update, clean, optimize, reboot, OS and hardware statistics, package search and inventory, uptime, env vars, Windows features |
| `sm_service_*`, `manage_service_*`, `list_services` | list, inspect, start, stop, restart, enable and disable system services |
| `sm_process_*`, `get_process_details` | list, inspect and kill processes |
| `sm_network_*`, `get_network_connections` | interfaces, open ports, ping, DNS lookup, connections |
| `sm_disk_*` | disks, usage and space report |
| `sm_user_*` | list users and groups |
| `sm_file_*`, `query_system_logs` | file listing, search, grep, managed edits, logs |
| `sm_cron_*` | list and remove cron jobs |
| `sm_firewall_*` | firewall status and rules |
| `sm_storage_health_*` | SMART, RAID, drive faults and the combined report |
| `sm_advanced_*` | uv, nvm, Node, virtual environments, authorized keys |
| `systems_ingest_host` | privacy-safe governed host graph ingestion |

Example agent prompts that map onto these tools:

- *"Update the system and install git and htop"* -> `sm_system_update`, `sm_system_install_applications`
- *"Show the hardware statistics for this host"* -> `sm_system_get_hardware_statistics`
- *"Which processes are using the most memory?"* -> `sm_process_list_processes`

Tool modules are individually togglable with environment switches (for example,
`MISCTOOL`) and can be filtered through the current Scion SDK visibility
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
compose the governed tunnel-manager capability through Arbora. See
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
