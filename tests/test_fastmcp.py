from fastmcp import FastMCP
import asyncio

mcp = FastMCP("test")


@mcp.tool()
def test_dict() -> dict:
    return {"success": True, "logs": None}


async def run():
    print(await mcp.call_tool("test_dict", {}))


asyncio.run(run())
