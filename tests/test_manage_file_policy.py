"""CONN-SYSTEMS-MANAGER-CONNECTOR-IDENTITY-R004: file actions match the manager."""

import pytest
from fastmcp.exceptions import ToolError

from systems_manager import mcp_server as server


class _Message:
    def __init__(self, name, arguments):
        self.name = name
        self.arguments = arguments


class _Context:
    def __init__(self, name, arguments):
        self.message = _Message(name, arguments)


async def _allowed(_context):
    return {"success": True}


@pytest.mark.asyncio
async def test_manage_file_actions_match_the_manager_and_denial_is_explained(
    monkeypatch,
):
    monkeypatch.setenv("SYSTEMS_MANAGER_ALLOW_HOST_MUTATIONS", "true")
    monkeypatch.setenv("SYSTEMS_MANAGER_ALLOW_FILESYSTEM_MUTATIONS", "true")
    middleware = server.SystemsSecurityMiddleware()

    update = _Context(
        "sm_file_operations", {"action": "manage_file", "file_action": "update"}
    )
    assert await middleware.on_call_tool(update, _allowed) == {"success": True}
    assert (
        server._classify_tool("sm_file_operations", update.message.arguments)
        == "filesystem-mutation"
    )

    write = _Context(
        "sm_file_operations", {"action": "manage_file", "file_action": "write"}
    )
    with pytest.raises(PermissionError):
        await middleware.on_call_tool(write, _allowed)

    monkeypatch.delenv("SYSTEMS_MANAGER_ALLOW_FILESYSTEM_MUTATIONS")
    with pytest.raises(ToolError, match="filesystem mutation") as caught:
        await middleware.on_call_tool(update, _allowed)
    assert isinstance(caught.value, PermissionError)
