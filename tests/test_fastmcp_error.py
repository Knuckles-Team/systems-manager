import pytest
from fastmcp import FastMCP
from pydantic_core import ValidationError


@pytest.mark.asyncio
async def test_fastmcp_validation_error():
    """Test that FastMCP properly validates tool input."""
    mcp = FastMCP("test")

    @mcp.tool()
    def test_tool(num: int) -> int:
        return num

    with pytest.raises(ValidationError):
        await mcp.call_tool("test_tool", {"num": {}})
