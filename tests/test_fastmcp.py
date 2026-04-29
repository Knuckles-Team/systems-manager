import pytest
from fastmcp import FastMCP


@pytest.mark.asyncio
async def test_dict():
    """Test that FastMCP can handle dict return types."""
    mcp = FastMCP("test")

    @mcp.tool()
    def test_dict_tool() -> dict:
        return {"success": True, "logs": None}

    result = await mcp.call_tool("test_dict_tool", {})
    assert result is not None
    assert hasattr(result, "content")
