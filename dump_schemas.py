import asyncio
import os
import sys

sys.path.insert(0, "/home/genius/Workspace/agent-packages/systems-manager")
sys.path.insert(0, "/home/genius/Workspace/agent-packages/agent-utilities")
from fastmcp import FastMCP
from systems_manager.mcp import register_tools
import json

async def run_test():
    mcp = FastMCP("test")
    register_tools(mcp)
    
    if hasattr(mcp, "_tool_manager"):
        tools = mcp._tool_manager.list_tools()
        if asyncio.iscoroutine(tools):
            tools = await tools
    else:
        tools = await mcp.list_tools()
        
    for tool in tools:
        if tool.name in ("get_system_logs", "get_os_statistics"):
            print(f"--- {tool.name} ---")
            if hasattr(tool, "parameters"):
                print(json.dumps(tool.parameters, indent=2))
            elif hasattr(tool, "inputSchema"):
                print(json.dumps(tool.inputSchema, indent=2))
            else:
                print(vars(tool))

if __name__ == "__main__":
    asyncio.run(run_test())
