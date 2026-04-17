import asyncio
import sys

import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
WORKSPACE_ROOT = os.path.abspath(os.path.join(REPO_ROOT, "..", ".."))

sys.path.insert(0, REPO_ROOT)
sys.path.insert(0, os.path.join(WORKSPACE_ROOT, "agent-utilities"))

from agent_utilities.agent_utilities import create_agent
from pydantic_ai.ui.ag_ui import AGUIAdapter


async def run_test():
    print("Creating agent...")
    agent = create_agent(
        provider="openai",
        model_id="nvidia/nemotron-3-super",
        base_url="http://10.0.0.18:1234/v1",
        api_key="llama",
        mcp_url="http://localhost:8010/mcp",
        system_prompt="You must use get_system_logs immediately.",
    )

    print("Agent created. Building run input...")
    run_input = AGUIAdapter.build_run_input(b"""{
        "prompt": "Call get_system_logs with lines=50 directly and output nothing else",
        "messages": [],
        "threadId": "test_thread",
        "runId": "test_run",
        "state": {},
        "tools": [],
        "context": [],
        "forwardedProps": {}
    }""")

    adapter = AGUIAdapter(agent=agent, run_input=run_input, accept="text/event-stream")
    print("Running stream...")

    try:
        events = adapter.run_stream()
        async for event in adapter.encode_stream(events):
            print(f"EVENT: {event}")
    except Exception:
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(run_test())
