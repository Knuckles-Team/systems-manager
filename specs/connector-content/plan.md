# CONN-SYSTEMS-MANAGER-CONNECTOR-CONTENT — Design and implementation plan

Governing spec: [spec.md](spec.md).

## Architecture

`pyproject.toml` declares `systems-manager-mcp` as the connector identity. `create_mcp_server` resolves the packaged content of `systems_manager` from it.
