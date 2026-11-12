"""Every mutating host tool is declared destructive and asks through the SDK guard."""

from __future__ import annotations

import sys
from unittest.mock import patch

import pytest

from systems_manager.mcp_server import get_mcp_instance

_SYSTEM = (
    "install_applications update reboot clean optimize install_python_modules "
    "clean_temp_files clean_package_cache enable_windows_features "
    "disable_windows_features add_repository install_local_package"
).split()
_ADVANCED = (
    "add_authorized_key install_uv create_venv install_package install_nvm "
    "install_node use_node"
).split()
MUTATING = (
    [f"sm_system_{a}" for a in _SYSTEM]
    + [f"sm_service_{a}_service" for a in "start stop restart enable disable".split()]
    + [f"manage_service_{a}" for a in "start stop restart enable disable".split()]
    + [
        "sm_process_kill_process",
        "sm_file_manage_file",
        "sm_cron_remove_cron_job",
        "sm_firewall_add_firewall_rule",
        "sm_firewall_remove_firewall_rule",
        "start_system_trace",
        "stop_system_trace",
    ]
    + [f"sm_advanced_{a}" for a in _ADVANCED]
)


@pytest.mark.asyncio
async def test_mutating_tools_are_declared_destructive_and_take_confirm():
    with patch.object(sys, "argv", ["systems-manager"]):
        server = get_mcp_instance()[1]
    tools = {tool.name: tool for tool in await server.list_tools()}
    for name in MUTATING:
        assert name in tools, name
        assert tools[name].annotations.destructive_hint is True, name
        assert "confirm" in tools[name].parameters["properties"], name
        assert "allow_destructive" not in tools[name].parameters["properties"], name


@pytest.mark.asyncio
async def test_operator_setting_is_the_sdks_only(monkeypatch):
    from systems_manager import confirmation

    monkeypatch.setenv("SCION_ALLOW_DESTRUCTIVE", "true")
    assert await confirmation.require_approval(object(), "update") is None
