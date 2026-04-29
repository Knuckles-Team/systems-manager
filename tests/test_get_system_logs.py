import pytest
from fastmcp import FastMCP
from systems_manager.mcp_server import register_log_tools


@pytest.mark.asyncio
async def test_get_system_logs():
    """Test getting system logs through MCP tool."""
    mcp = FastMCP("test_sm")
    register_log_tools(mcp)

    result = await mcp.call_tool("get_system_logs", {"lines": 10})
    assert result is not None
    # MCP tools return ToolResult objects with content attribute
    assert hasattr(result, "content")
    assert len(result.content) > 0
