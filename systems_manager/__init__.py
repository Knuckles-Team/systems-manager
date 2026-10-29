"""Systems Manager provider package.

Import concrete clients and entry points from their owning modules. The package root
does not expose dynamic optional-dependency aliases.
"""

from agent_connector_sdk.connector import Connector  # noqa: E402

from systems_manager.mcp_server import register_systems_tools  # noqa: E402

connector = Connector(
    instructions="Systems Manager MCP Server",
    extra_registrations=(register_systems_tools,),
)

__all__ = ["connector"]
