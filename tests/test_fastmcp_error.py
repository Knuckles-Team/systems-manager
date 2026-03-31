import asyncio
from fastmcp import FastMCP

mcp = FastMCP("test")


@mcp.tool()
def test_tool(num: int) -> int:
    return num


async def run():
                                                                              
    print(await mcp.call_tool("test_tool", {"num": {}}))


asyncio.run(run())
