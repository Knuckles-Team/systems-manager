# Host lifecycle coverage

The package can perform governed maintenance on the operating system where its
process runs. It does not cross the host/container/WSL boundary: a Linux
container manages that container, WSL manages its Linux guest, and Windows host
operations require a native Windows process. Deploy one authenticated service
per managed host or place a separately reviewed privilege broker on that host.

## Current capability matrix

| Domain | Linux | Windows | Current boundary |
| --- | --- | --- | --- |
| Inventory and health | Supported | Supported | Sensitive-read policy gate |
| Application package search, inventory, install, and upgrade | Supported through apt/dnf/zypper/pacman | Supported through winget | Mutation gate plus request approval |
| Operating-system security updates | Native package update only | Not implemented; winget updates applications, not Windows Update | Windows Update orchestration is required |
| Package removal, pinning, rollback, and transaction history | Not implemented | Not implemented | Required for complete rollback |
| Service inventory and start/stop/restart/enable/disable | Supported | Supported where the service backend exposes it | Mutation gate plus request approval |
| Process inventory and termination | Supported | Supported | Reads and mutations are separately gated |
| Network inventory, port inventory, ping, and DNS | Supported | Supported | Active probes have a separate gate |
| Interface, route, DNS, VPN, and proxy configuration | Not implemented | Not implemented | Requires typed platform models |
| Disk inventory, usage, and bounded space reports | Supported | Supported | Read-only |
| Partitioning, formatting, mounting, encryption, and repair | Not implemented | Not implemented | Requires a recovery/rollback design |
| User and group inventory | Supported | Supported | Read-only |
| Account, group membership, credential, and privilege changes | Not implemented | Not implemented | Requires an identity/elevation broker |
| Log retrieval and bounded tailing | Supported | Supported where backend commands exist | Sensitive-read gate |
| Firewall status, inventory, typed add, and typed remove | Supported for known backends | Supported through Windows Firewall | Structured rules only; command fragments are not accepted |
| Scheduled task inventory/removal | Cron inventory and exact-reference removal | Inventory only | Scheduled-command creation is not part of the API |
| Managed-root file reads and edits | Supported | Supported | Explicit root; writes require host and file gates |
| SSH public-key inventory/generation/authorization | Supported | Supported when OpenSSH is installed | Secret-bearing generation requires an external broker |
| Python and Node environment bootstrap | Supported | Supported where toolchain commands exist | Version and mutation policy constraints apply |
| Backup, restore, snapshots, and disaster recovery | Not implemented | Not implemented | Required before autonomous lifecycle claims |
| Reboot | Supported with a Kubernetes-node lifecycle guard | Supported | Mutation gate plus request approval; cluster nodes require the rolling workflow or deployment override |
| Shutdown, power, firmware, drivers, and bootloader | Not implemented | Not implemented | Requires out-of-band recovery and strict approval |
| Endpoint security posture, malware scan, and policy compliance | Not implemented | Not implemented | Integrate platform security providers rather than raw shell |

“Supported” means the package has a typed implementation; it does not mean the
runtime account has permission. At startup and before mutation, operators must
verify platform tools, managed-root configuration, transport authentication,
policy gates, and the account/elevation boundary.

## Safe operating sequence

1. Install natively on the target host under a dedicated account.
2. Configure an explicit SYSTEMS_MANAGER_FILESYSTEM_ROOT.
3. Keep all mutation/read/probe gates false during discovery.
4. Authenticate every non-loopback agent and MCP listener with verified TLS.
5. Enable only the required gate for one bounded maintenance window.
6. Confirm the request through MCP elicitation or an external approval broker.
7. Verify resulting package, service, firewall, or file state before closing the
   window.

The missing rows above are release blockers for describing this package as a
complete laptop lifecycle manager. They should be added as typed, reversible
operations with platform-specific tests; they must not be filled with a generic
shell tool.
