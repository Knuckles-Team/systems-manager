"""Tests for mcp_server.py - the declared connector builds the server with its tools."""

import asyncio
from importlib.metadata import version

from agent_connector_sdk.mcp.tool_surface import registered_tools


class TestToolRegistration:
    def test_tools_registered(self):
        from systems_manager.mcp_server import get_mcp_instance

        _, mcp, _ = get_mcp_instance()
        assert "sm_service_operations" in registered_tools(mcp)


class TestGetMcpInstance:
    def test_get_mcp_instance(self):
        from systems_manager.mcp_server import get_mcp_instance

        args, mcp, middlewares = get_mcp_instance()
        assert mcp is not None
        assert asyncio.run(mcp.list_tools()) is not None


class TestVersion:
    def test_version_from_metadata(self):
        assert isinstance(version("systems-manager"), str)
