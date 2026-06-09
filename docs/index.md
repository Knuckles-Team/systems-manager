# systems-manager

A cross-platform **CLI, API, MCP Server, and Agent** for system maintenance,
package management, and zero-script remote host orchestration in the agent-utilities
ecosystem.

!!! info "Official documentation"
    This site is the canonical reference for `systems-manager`, maintained alongside
    every release.

[![PyPI](https://img.shields.io/pypi/v/systems-manager)](https://pypi.org/project/systems-manager/)
![MCP Server](https://badge.mcpx.dev?type=server 'MCP Server')
[![License](https://img.shields.io/pypi/l/systems-manager)](https://github.com/Knuckles-Team/systems-manager/blob/main/LICENSE)
[![GitHub](https://img.shields.io/badge/source-GitHub-181717?logo=github)](https://github.com/Knuckles-Team/systems-manager)

## Overview

`systems-manager` updates the host operating system, installs and upgrades
applications, and exposes those same capabilities to AI agents through a typed,
deterministic MCP tool surface. It provides:

- **A cross-distribution package manager** — one façade (`SystemsManagerBase`) over
  `apt`, `dnf`, `zypper`, `pacman`, and Windows, selected automatically per host.
- **Action-routed MCP tools** — consolidated, togglable tool modules for system,
  service, process, network, disk, user, file, cron, and firewall operations.
- **An integrated Pydantic AI graph agent** — reachable over the Agent Control
  Protocol (ACP) and the Agent Web UI (AG-UI).
- **Zero-script remote orchestration** — telemetry and control across an inventory of
  hosts over plain SSH, with no remote daemons or packages deployed on the targets.

## Explore the documentation

<div class="grid cards" markdown>

- :material-rocket-launch: **[Installation](installation.md)** — pip, source, extras, and the prebuilt Docker image.
- :material-server-network: **[Deployment](deployment.md)** — run the MCP and agent servers, Docker Compose, Caddy + Technitium.
- :material-console: **[Usage](usage.md)** — the MCP tools, the `SystemsManager` API, and the CLI.
- :material-sitemap: **[Overview](overview.md)** — ecosystem role and the concept map.
- :material-shield-lock: **[Sudo Security](sudo_security.md)** — the least-privilege elevated-execution model.
- :material-server: **[Multi-Host](multi_host.md)** — zero-script remote telemetry and control plane.
- :material-cog-play: **[Day 0 Provisioning](day_0_provisioning.md)** — bare-metal to managed cluster node.

</div>

## Quick start

```bash
pip install "systems-manager[mcp]"
systems-manager-mcp              # stdio MCP server (default transport)
```

Run the package-management CLI directly:

```bash
systems-manager --update --install "git,curl,htop"
```

See **[Installation](installation.md)** and **[Deployment](deployment.md)** for the
full matrix (PyPI extras, Docker image, all transports, reverse proxy, DNS, and the
agent server).
