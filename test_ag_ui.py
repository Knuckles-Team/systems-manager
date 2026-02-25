import asyncio
import os
import sys

sys.path.insert(0, "/home/genius/Workspace/agent-packages/systems-manager")
sys.path.insert(0, "/home/genius/Workspace/agent-packages/agent-utilities")

from agent_utilities.agent_utilities import create_agent
from pydantic_ai.ui.ag_ui import AGUIAdapter

async def run_test():
    print("Creating agent...")
    agent = create_agent(
        provider="openai",
        model_id="qwen/qwen3-coder-next",
        base_url="http://10.0.0.18:1234/v1",
        api_key="llama",
        mcp_url="http://localhost:8010/mcp",
        system_prompt="You must use get_os_statistics immediately." # FORCING IT
    )
    
    print("Agent created. Building run input...")
    run_input = AGUIAdapter.build_run_input(b'''{
        "prompt": "Call get_os_statistics directly and output absolutely no text, thoughts, or explanations before the tool call",
        "messages": [],
        "threadId": "test_thread",
        "runId": "test_run",
        "state": {},
        "tools": [],
        "context": [],
        "forwardedProps": {}
    }''')
    
    adapter = AGUIAdapter(agent=agent, run_input=run_input, accept="text/event-stream")
    print("Running stream...")
    
    try:
        events = adapter.run_stream()
        async for event in adapter.encode_stream(events):
            print(f"EVENT: {event}")
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(run_test())
