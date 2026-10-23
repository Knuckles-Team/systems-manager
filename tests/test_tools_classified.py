"""Startup refuses any registered tool that has no policy class (fail closed)."""

import pytest
from agent_connector_sdk.mcp.action_split import assert_tools_classified
from fastmcp import FastMCP

from systems_manager import mcp_server as server


def test_unclassified_tool_refuses_startup():
    mcp = FastMCP("classify-test")

    @mcp.tool()
    async def not_in_policy() -> str:
        return "x"

    with pytest.raises(RuntimeError, match="not_in_policy"):
        assert_tools_classified(mcp, server._ALL_CLASSIFIED_TOOLS)


def test_classified_tool_is_accepted():
    mcp = FastMCP("classify-test")
    server.register_misc_tools(mcp)
    assert_tools_classified(mcp, server._ALL_CLASSIFIED_TOOLS)


def test_unknown_registry_shape_fails_closed():
    with pytest.raises(AttributeError):
        assert_tools_classified(object(), server._ALL_CLASSIFIED_TOOLS)


def test_handwritten_check_is_gone():
    assert not hasattr(server, "_assert_registered_tools_are_classified")
