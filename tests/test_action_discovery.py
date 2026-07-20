"""Action-discovery behavior for systems-manager's action-routed tools.

Every action-routed tool is wired to the shared ``agent_utilities`` helper
``resolve_action``, constrained by the provider's strict current contract, which
provides:

* explicit ``list_actions`` discovery payloads, and
* a rich "Did you mean ...? Call with action='list_actions' ..." error on
  unknown actions.
"""

import json

import pytest

from systems_manager.agent_os_tools import (
    SCHEDULER_ACTIONS,
    sm_agent_scheduler_operations,
)
from systems_manager.mcp_server import get_mcp_instance

args, mcp_server, middlewares = get_mcp_instance()


def parse_mcp_result(res):
    text = getattr(res.content[0], "text", "")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


@pytest.mark.asyncio
async def test_mcp_tool_list_actions_returns_names():
    """An mcp_server action-routed tool returns its action list on discovery."""
    res = await mcp_server.call_tool(
        "sm_disk_operations",
        arguments={"action": "list_actions"},
    )
    data = parse_mcp_result(res)
    assert data["service"] == "systems-manager"
    assert "list_disks" in data["actions"]
    assert "get_disk_usage" in data["actions"]


@pytest.mark.asyncio
async def test_mcp_tool_bogus_action_mentions_list_actions():
    """An unknown action raises a rich error pointing at list_actions."""
    with pytest.raises(PermissionError) as exc_info:
        await mcp_server.call_tool(
            "sm_disk_operations",
            arguments={"action": "totally_bogus"},
        )
    assert "list_actions" in str(exc_info.value)


@pytest.mark.asyncio
async def test_historical_discovery_alias_is_rejected():
    """Only the current explicit discovery action is accepted."""
    with pytest.raises(PermissionError, match="list_actions"):
        await mcp_server.call_tool(
            "sm_disk_operations",
            arguments={"action": "actions"},
        )


@pytest.mark.asyncio
async def test_agent_os_tool_list_actions_returns_names():
    """An agent_os action-routed function returns its action list on discovery."""
    result = await sm_agent_scheduler_operations(action="list_actions")
    assert result["service"] == "systems-manager"
    assert set(result["actions"]) == set(SCHEDULER_ACTIONS)


@pytest.mark.asyncio
async def test_agent_os_tool_bogus_action_raises_value_error():
    """An unknown action on an agent_os function raises ValueError mentioning list_actions."""
    with pytest.raises(ValueError, match="list_actions"):
        await sm_agent_scheduler_operations(action="totally_bogus")
