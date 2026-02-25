import asyncio
from systems_manager.mcp import register_tools
from fastmcp import FastMCP
import logging

logging.basicConfig(level=logging.DEBUG)

async def run():
    try:
        mcp = FastMCP("test_sm")
        register_tools(mcp)
        print("Calling get_system_logs...")
        result = await mcp.call_tool("get_system_logs", {"lines": 50})
        print("Result:", result)
    except Exception as e:
        import traceback
        traceback.print_exc()

asyncio.run(run())
