# Installation

`systems-manager` is a standard Python package and a prebuilt container image. Pick
the path that matches how you want to run it.

## Requirements

- **Python 3.11 – 3.14**.
- A Linux host (`apt`, `dnf`, `zypper`, or `pacman`) or Windows for the
  package-management surface; the MCP and agent servers run anywhere Python does.

## From PyPI (recommended)

```bash
pip install systems-manager
```

### Optional extras

The base install ships the CLI and the cross-platform package managers. Install the
extra for the interface you need:

| Extra | Install | Pulls in |
|---|---|---|
| `mcp` | `pip install "systems-manager[mcp]"` | FastMCP MCP-server runtime (`agent-utilities[mcp]`) |
| `agent` | `pip install "systems-manager[agent]"` | Pydantic-AI agent + Logfire tracing |
| `all` | `pip install "systems-manager[all]"` | The MCP server, the agent, and tracing |
| `test` | `pip install "systems-manager[test]"` | `pytest` and `pytest-asyncio` |

```bash
# Typical: run the MCP server and the agent
pip install "systems-manager[all]"
```

## From source

```bash
git clone https://github.com/Knuckles-Team/systems-manager.git
cd systems-manager
pip install -e ".[all]"          # editable install with every extra
```

With [`uv`](https://docs.astral.sh/uv/):

```bash
uv pip install -e ".[all]"
uv run systems-manager-mcp
```

## Prebuilt Docker image

A multi-stage runtime image is published on every release (installs
`systems-manager[all]`):

```bash
docker pull "${SYSTEMS_MANAGER_AGENT_IMAGE}"

docker run --rm -i \
  "${SYSTEMS_MANAGER_AGENT_IMAGE}" systems-manager-mcp
```

For an HTTP server with a published port and the agent, see
[Deployment](deployment.md).

## Verify the install

```bash
systems-manager --help
systems-manager-mcp --help
python -c "import systems_manager; print(systems_manager.__name__)"
```

## Next steps

- **[Deployment](deployment.md)** — run local or authenticated network services.
- **[Usage](usage.md)** — call the tools, the API, and the CLI.
- **[Configuration](configuration.md)** — trust, policy, privacy, and runtime values.
