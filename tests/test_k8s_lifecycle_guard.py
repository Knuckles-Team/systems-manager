"""Update and reboot of a live Kubernetes node go through the SDK destructive guard."""

import sys
from unittest.mock import patch

import pytest

from systems_manager.mcp_server import get_mcp_instance
from systems_manager.systems_manager import AptManager, WindowsManager


def _server():
    with patch.object(sys, "argv", ["systems-manager"]):
        return get_mcp_instance()[1]


@pytest.mark.asyncio
@pytest.mark.parametrize("name", ["sm_system_update", "sm_system_reboot"])
async def test_update_and_reboot_are_destructive_with_no_k8s_override(name):
    tool = {t.name: t for t in await _server().list_tools()}[name]
    properties = tool.parameters["properties"]
    assert tool.annotations.destructive_hint is True
    assert "confirm" in properties
    assert "allow_on_k8s" not in properties


@pytest.mark.asyncio
@pytest.mark.parametrize("action", ["update", "reboot"])
async def test_live_k8s_node_names_itself_in_the_approval_and_changes_nothing_unconfirmed(
    action, monkeypatch
):
    seen = {}

    async def refuse(ctx, operation, arguments=None, *, confirm=False):
        seen["operation"] = operation
        seen["confirm"] = confirm
        return {"cancelled": True}

    monkeypatch.setattr("systems_manager.confirmation.guard_destructive", refuse)
    monkeypatch.setattr(
        "systems_manager.mcp_server.is_k8s_node", lambda: (True, "kubelet active")
    )
    with patch("systems_manager.mcp_server.detect_and_create_manager") as detect:
        tool = await _server().get_tool(f"sm_system_{action}")
        result = await tool.fn(ctx=object())
    assert result["success"] is False
    assert "live Kubernetes node" in seen["operation"]
    assert seen["confirm"] is False
    getattr(detect.return_value, action).assert_not_called()


def test_no_connector_local_k8s_override_remains():
    import inspect

    assert "allow_on_k8s" not in inspect.signature(AptManager.update).parameters
    assert "allow_on_k8s" not in inspect.signature(AptManager.reboot).parameters


def test_reboot_uses_the_platform_command():
    mgr = AptManager(silent=True)
    with (
        patch("platform.system", return_value="Linux"),
        patch.object(mgr, "run_command", return_value={"success": True}),
    ):
        assert mgr.reboot()["success"] is True
        mgr.run_command.assert_called_once_with(["systemctl", "reboot"], elevated=True)
    with patch("os.path.exists", return_value=True):
        win = WindowsManager(silent=True)
    with (
        patch("platform.system", return_value="Windows"),
        patch.object(win, "run_command", return_value={"success": True}),
    ):
        assert win.reboot()["success"] is True
        win.run_command.assert_called_once_with(
            ["shutdown.exe", "/r", "/t", "0"], elevated=True
        )
