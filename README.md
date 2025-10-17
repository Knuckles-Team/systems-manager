# Systems-Manager

![PyPI - Version](https://img.shields.io/pypi/v/systems-manager)
![PyPI - Downloads](https://img.shields.io/pypi/dd/systems-manager)
![GitHub Repo stars](https://img.shields.io/github/stars/Knuckles-Team/systems-manager)
![GitHub forks](https://img.shields.io/github/forks/Knuckles-Team/systems-manager)
![GitHub contributors](https://img.shields.io/github/contributors/Knuckles-Team/systems-manager)
![PyPI - License](https://img.shields.io/pypi/l/systems-manager)
![GitHub](https://img.shields.io/github/license/Knuckles-Team/systems-manager)

![GitHub last commit (by committer)](https://img.shields.io/github/last-commit/Knuckles-Team/systems-manager)
![GitHub pull requests](https://img.shields.io/github/issues-pr/Knuckles-Team/systems-manager)
![GitHub closed pull requests](https://img.shields.io/github/issues-pr-closed/Knuckles-Team/systems-manager)
![GitHub issues](https://img.shields.io/github/issues/Knuckles-Team/systems-manager)

![GitHub top language](https://img.shields.io/github/languages/top/Knuckles-Team/systems-manager)
![GitHub language count](https://img.shields.io/github/languages/count/Knuckles-Team/systems-manager)
![GitHub repo size](https://img.shields.io/github/repo-size/Knuckles-Team/systems-manager)
![GitHub repo file count (file type)](https://img.shields.io/github/directory-file-count/Knuckles-Team/systems-manager)
![PyPI - Wheel](https://img.shields.io/pypi/wheel/systems-manager)
![PyPI - Implementation](https://img.shields.io/pypi/implementation/systems-manager)

*Version: 1.1.10*

Systems-Manager is a powerful CLI and MCP server tool to manage your system across multiple operating systems. It supports updating, installing, and optimizing applications, managing Windows features, installing Nerd Fonts, and retrieving system and hardware statistics. It now supports Ubuntu, Debian, Red Hat, Oracle Linux, SLES, Arch, and Windows, with Snap fallback for Linux application installations.

This repository is actively maintained - Contributions are welcome!

## Features

- **Multi-OS Support**: Works on Windows, Ubuntu, Debian, Red Hat, Oracle Linux, SLES, and Arch.
- **Application Management**: Install and update applications using native package managers (apt, dnf, zypper, pacman, winget) with automatic Snap fallback for Linux.
- **Font Installation**: Install specific Nerd Fonts (default: Hack) or all available fonts from the latest release.
- **Windows Feature Management**: List, enable, or disable Windows optional features (Windows only).
- **System Optimization**: Clean and optimize system resources (e.g., trash/recycle bin, autoremove, defragmentation on Windows).
- **System and Hardware Stats**: Retrieve detailed OS and hardware information using `psutil`.
- **Logging**: Optional logging to a specified file or default `systems_manager.log` in the script directory.
- **FastMCP Server**: Expose all functionality via a Model Context Protocol (MCP) server over stdio or HTTP for integration with AI or automation systems.

## Available MCP tools:
- `install_applications`: Install applications with Snap fallback (Linux).
- `update`: Update system and applications.
- `clean`: Clean system resources (e.g., trash/recycle bin).
- `optimize`: Optimize system (e.g., autoremove, defrag on Windows).
- `install_python_modules`: Install Python modules via pip.
- `install_fonts`: Install specified Nerd Fonts (default: Hack) or all fonts.
- `get_os_stats`: Retrieve OS statistics.
- `get_hardware_stats`: Retrieve hardware statistics.
- `list_windows_features`: List Windows features (Windows only).
- `enable_windows_features`: Enable Windows features (Windows only).
- `disable_windows_features`: Disable Windows features (Windows only).
- `run_command`: Run elevated commands on shell (Enable at your own risk).

<details>
  <summary><b>Usage:</b></summary>

| Short Flag | Long Flag           | Description                                              |
|------------|---------------------|----------------------------------------------------------|
| -h         | --help              | See usage for script                                     |
| -c         | --clean             | Clean Recycle/Trash bin                                  |
| -e         | --enable-features   | Enable Windows features (comma-separated, Windows only)   |
| -d         | --disable-features  | Disable Windows features (comma-separated, Windows only)  |
| -l         | --list-features     | List all Windows features and their status (Windows only) |
| -f         | --fonts             | Install Nerd Fonts (comma-separated, e.g., Hack,Meslo or 'all'; default: Hack) |
| -i         | --install           | Install applications (comma-separated, e.g., python3,git) |
| -p         | --python            | Install Python modules (comma-separated)                  |
| -s         | --silent            | Suppress output to stdout                                 |
| -u         | --update            | Update applications and Operating System                 |
| -o         | --optimize          | Optimize system (e.g., autoremove, clean cache, defrag)   |
|            | --os-stats          | Print OS statistics (e.g., system, release, version)      |
|            | --hw-stats          | Print hardware statistics (e.g., CPU, memory, disk)       |
|            | --log-file          | Log to specified file (default: systems_manager.log)      |

```bash
systems-manager --fonts Hack,Meslo --update --clean --python geniusbot --install python3,git --enable-features Microsoft-Hyper-V-All,Containers --log-file /path/to/log.log
```

### MCP CLI

| Short Flag | Long Flag                          | Description                                                                 |
|------------|------------------------------------|-----------------------------------------------------------------------------|
| -h         | --help                             | Display help information                                                    |
| -t         | --transport                        | Transport method: 'stdio', 'http', or 'sse' [legacy] (default: stdio)       |
| -s         | --host                             | Host address for HTTP transport (default: 0.0.0.0)                          |
| -p         | --port                             | Port number for HTTP transport (default: 8000)                              |
|            | --auth-type                        | Authentication type: 'none', 'static', 'jwt', 'oauth-proxy', 'oidc-proxy', 'remote-oauth' (default: none) |
|            | --token-jwks-uri                   | JWKS URI for JWT verification                                              |
|            | --token-issuer                     | Issuer for JWT verification                                                |
|            | --token-audience                   | Audience for JWT verification                                              |
|            | --oauth-upstream-auth-endpoint     | Upstream authorization endpoint for OAuth Proxy                             |
|            | --oauth-upstream-token-endpoint    | Upstream token endpoint for OAuth Proxy                                    |
|            | --oauth-upstream-client-id         | Upstream client ID for OAuth Proxy                                         |
|            | --oauth-upstream-client-secret     | Upstream client secret for OAuth Proxy                                     |
|            | --oauth-base-url                   | Base URL for OAuth Proxy                                                   |
|            | --oidc-config-url                  | OIDC configuration URL                                                     |
|            | --oidc-client-id                   | OIDC client ID                                                             |
|            | --oidc-client-secret               | OIDC client secret                                                         |
|            | --oidc-base-url                    | Base URL for OIDC Proxy                                                    |
|            | --remote-auth-servers              | Comma-separated list of authorization servers for Remote OAuth             |
|            | --remote-base-url                  | Base URL for Remote OAuth                                                  |
|            | --allowed-client-redirect-uris     | Comma-separated list of allowed client redirect URIs                       |
|            | --eunomia-type                     | Eunomia authorization type: 'none', 'embedded', 'remote' (default: none)   |
|            | --eunomia-policy-file              | Policy file for embedded Eunomia (default: mcp_policies.json)              |
|            | --eunomia-remote-url               | URL for remote Eunomia server                                              |

### Using as an MCP Server

The MCP Server can be run in two modes: `stdio` (for local testing) or `http` (for networked access). To start the server, use the following commands:

#### Run in stdio mode (default):
```bash
systems-manager-mcp --transport "stdio"
```

#### Run in HTTP mode:
```bash
systems-manager-mcp --transport "http"  --host "0.0.0.0"  --port "8000"
```


### Dependencies

The following Python packages are automatically installed if missing:
- `distro`: For Linux distribution detection.
- `psutil`: For system and hardware statistics.
- `requests`: For downloading Nerd Fonts.
- `fastmcp`: For MCP server functionality (required for `systems-manager-mcp`).


### Deploy MCP Server as a Service

The MCP server can be deployed using Docker, with configurable authentication, middleware, and Eunomia authorization.

#### Using Docker Run

```bash
docker pull knucklessg1/systems-manager:latest

docker run -d \
  --name systems-manager-mcp \
  -p 8004:8004 \
  -e HOST=0.0.0.0 \
  -e PORT=8004 \
  -e TRANSPORT=http \
  -e AUTH_TYPE=none \
  -e EUNOMIA_TYPE=none \
  knucklessg1/systems-manager:latest
```

For advanced authentication (e.g., JWT, OAuth Proxy, OIDC Proxy, Remote OAuth) or Eunomia, add the relevant environment variables:

```bash
docker run -d \
  --name systems-manager-mcp \
  -p 8004:8004 \
  -e HOST=0.0.0.0 \
  -e PORT=8004 \
  -e TRANSPORT=http \
  -e AUTH_TYPE=oidc-proxy \
  -e OIDC_CONFIG_URL=https://provider.com/.well-known/openid-configuration \
  -e OIDC_CLIENT_ID=your-client-id \
  -e OIDC_CLIENT_SECRET=your-client-secret \
  -e OIDC_BASE_URL=https://your-server.com \
  -e ALLOWED_CLIENT_REDIRECT_URIS=http://localhost:*,https://*.example.com/* \
  -e EUNOMIA_TYPE=embedded \
  -e EUNOMIA_POLICY_FILE=/app/mcp_policies.json \
  knucklessg1/systems-manager:latest
```

#### Using Docker Compose

Create a `docker-compose.yml` file:

```yaml
services:
  systems-manager-mcp:
    image: knucklessg1/systems-manager:latest
    environment:
      - HOST=0.0.0.0
      - PORT=8004
      - TRANSPORT=http
      - AUTH_TYPE=none
      - EUNOMIA_TYPE=none
    ports:
      - 8004:8004
```

For advanced setups with authentication and Eunomia:

```yaml
services:
  systems-manager-mcp:
    image: knucklessg1/systems-manager:latest
    environment:
      - HOST=0.0.0.0
      - PORT=8004
      - TRANSPORT=http
      - AUTH_TYPE=oidc-proxy
      - OIDC_CONFIG_URL=https://provider.com/.well-known/openid-configuration
      - OIDC_CLIENT_ID=your-client-id
      - OIDC_CLIENT_SECRET=your-client-secret
      - OIDC_BASE_URL=https://your-server.com
      - ALLOWED_CLIENT_REDIRECT_URIS=http://localhost:*,https://*.example.com/*
      - EUNOMIA_TYPE=embedded
      - EUNOMIA_POLICY_FILE=/app/mcp_policies.json
    ports:
      - 8004:8004
    volumes:
      - ./mcp_policies.json:/app/mcp_policies.json
```

Run the service:

```bash
docker-compose up -d
```

#### Configure `mcp.json` for AI Integration

```json
{
  "mcpServers": {
    "systems_manager": {
      "command": "uv",
      "args": [
        "run",
        "--with",
        "systems-manager",
        "systems-manager-mcp"
      ],
      "env": {
        "SYSTEMS_MANAGER_SILENT": "False",
        "SYSTEMS_MANAGER_LOG_FILE": "~/Documents/systems_manager_mcp.log"
      },
      "timeout": 200000
    }
  }
}

```
</details>

<details>
  <summary><b>Installation Instructions:</b></summary>

Install Python Package

```bash
python -m pip install systems-manager
```

or

```bash
uv pip install --upgrade systems-manager
```

</details>

<details>
  <summary><b>Repository Owners:</b></summary>

<img width="100%" height="180em" src="https://github-readme-stats.vercel.app/api?username=Knucklessg1&show_icons=true&hide_border=true&&count_private=true&include_all_commits=true" />

![GitHub followers](https://img.shields.io/github/followers/Knucklessg1)
![GitHub User's stars](https://img.shields.io/github/stars/Knucklessg1)
</details>
