import json
from unittest.mock import MagicMock, patch

import pytest

from systems_manager.mcp_server import get_mcp_instance

args, mcp_server, middlewares = get_mcp_instance()


@pytest.fixture(autouse=True)
def authorize_provider_tool_contract(monkeypatch):
    """Exercise provider behavior only after explicit deployment authorization."""
    monkeypatch.setenv("SYSTEMS_MANAGER_ALLOW_SENSITIVE_READS", "true")
    monkeypatch.setenv("SYSTEMS_MANAGER_ALLOW_HOST_MUTATIONS", "true")


def parse_mcp_result(res):
    text = getattr(res.content[0], "text", "")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


@pytest.mark.asyncio
async def test_get_process_details():
    with patch("systems_manager.os_provider_tools.get_os_provider") as mock_get:
        provider = MagicMock()
        mock_get.return_value = provider
        provider.get_process_details.return_value = [{"pid": 123}]

        res = await mcp_server.call_tool("get_process_details", arguments={"pid": 123})
        data = parse_mcp_result(res)
        assert data["success"] is True
        assert data["processes"] == [{"pid": 123}]
        provider.get_process_details.assert_called_once_with(123)


@pytest.mark.asyncio
async def test_get_process_details_exception():
    with patch("systems_manager.os_provider_tools.get_os_provider") as mock_get:
        provider = MagicMock()
        mock_get.return_value = provider
        provider.get_process_details.side_effect = Exception("failed")

        res = await mcp_server.call_tool("get_process_details", arguments={"pid": 123})
        data = parse_mcp_result(res)
        assert data["success"] is False
        assert "failed" in data["error"]


@pytest.mark.asyncio
async def test_get_network_connections():
    with patch("systems_manager.os_provider_tools.get_os_provider") as mock_get:
        provider = MagicMock()
        mock_get.return_value = provider
        provider.get_network_connections.return_value = [{"laddr": "127.0.0.1"}]

        res = await mcp_server.call_tool("get_network_connections")
        data = parse_mcp_result(res)
        assert data["success"] is True
        assert data["connections"] == [{"laddr": "127.0.0.1"}]
        provider.get_network_connections.assert_called_once()


@pytest.mark.asyncio
async def test_get_network_connections_exception():
    with patch("systems_manager.os_provider_tools.get_os_provider") as mock_get:
        provider = MagicMock()
        mock_get.return_value = provider
        provider.get_network_connections.side_effect = Exception("error")
        res = await mcp_server.call_tool("get_network_connections")
        data = parse_mcp_result(res)
        assert data["success"] is False
        assert "error" in data


@pytest.mark.asyncio
async def test_capture_system_snapshot():
    with patch("systems_manager.os_provider_tools.get_os_provider") as mock_get:
        provider = MagicMock()
        mock_get.return_value = provider
        provider.capture_system_snapshot.return_value = {"cpu": 10}

        res = await mcp_server.call_tool("capture_system_snapshot")
        data = parse_mcp_result(res)
        assert data["success"] is True
        assert data["snapshot"] == {"cpu": 10}


@pytest.mark.asyncio
async def test_capture_system_snapshot_exception():
    with patch("systems_manager.os_provider_tools.get_os_provider") as mock_get:
        provider = MagicMock()
        mock_get.return_value = provider
        provider.capture_system_snapshot.side_effect = Exception("error")
        res = await mcp_server.call_tool("capture_system_snapshot")
        data = parse_mcp_result(res)
        assert data["success"] is False
        assert "error" in data


@pytest.mark.asyncio
async def test_list_services():
    with patch("systems_manager.os_provider_tools.get_os_provider") as mock_get:
        provider = MagicMock()
        mock_get.return_value = provider
        provider.list_services.return_value = [{"name": "service"}]

        res = await mcp_server.call_tool("list_services")
        data = parse_mcp_result(res)
        assert data["success"] is True
        assert data["services"] == [{"name": "service"}]


@pytest.mark.asyncio
async def test_list_services_exception():
    with patch("systems_manager.os_provider_tools.get_os_provider") as mock_get:
        provider = MagicMock()
        mock_get.return_value = provider
        provider.list_services.side_effect = Exception("error")
        res = await mcp_server.call_tool("list_services")
        data = parse_mcp_result(res)
        assert data["success"] is False
        assert "error" in data


@pytest.mark.asyncio
async def test_manage_service():
    with (
        patch("systems_manager.os_provider_tools.get_os_provider") as mock_get,
        patch(
            "systems_manager.os_provider_tools.ctx_confirm_destructive",
            return_value=True,
        ),
    ):
        provider = MagicMock()
        mock_get.return_value = provider
        provider.manage_service.return_value = {"status": "ok"}

        res = await mcp_server.call_tool(
            "manage_service", arguments={"service_name": "nginx", "action": "restart"}
        )
        data = parse_mcp_result(res)
        assert data["success"] is True
        assert data["result"] == {"status": "ok"}
        provider.manage_service.assert_called_once_with("nginx", "restart")


@pytest.mark.asyncio
async def test_manage_service_cancelled():
    with patch(
        "systems_manager.os_provider_tools.ctx_confirm_destructive", return_value=False
    ):
        res = await mcp_server.call_tool(
            "manage_service", arguments={"service_name": "nginx", "action": "restart"}
        )
        data = parse_mcp_result(res)
        assert data["success"] is False
        assert "cancelled" in data["error"]


@pytest.mark.asyncio
async def test_manage_service_exception():
    with (
        patch("systems_manager.os_provider_tools.get_os_provider") as mock_get,
        patch(
            "systems_manager.os_provider_tools.ctx_confirm_destructive",
            return_value=True,
        ),
    ):
        provider = MagicMock()
        mock_get.return_value = provider
        provider.manage_service.side_effect = Exception("error")
        res = await mcp_server.call_tool(
            "manage_service", arguments={"service_name": "nginx", "action": "restart"}
        )
        data = parse_mcp_result(res)
        assert data["success"] is False
        assert "error" in data


@pytest.mark.asyncio
async def test_list_kernel_modules():
    with patch("systems_manager.os_provider_tools.get_os_provider") as mock_get:
        provider = MagicMock()
        mock_get.return_value = provider
        provider.list_kernel_modules.return_value = [{"name": "mod"}]

        res = await mcp_server.call_tool("list_kernel_modules")
        data = parse_mcp_result(res)
        assert data["success"] is True
        assert data["modules"] == [{"name": "mod"}]


@pytest.mark.asyncio
async def test_list_kernel_modules_exception():
    with patch("systems_manager.os_provider_tools.get_os_provider") as mock_get:
        provider = MagicMock()
        mock_get.return_value = provider
        provider.list_kernel_modules.side_effect = Exception("error")
        res = await mcp_server.call_tool("list_kernel_modules")
        data = parse_mcp_result(res)
        assert data["success"] is False
        assert "error" in data


@pytest.mark.asyncio
async def test_query_system_logs():
    with patch("systems_manager.os_provider_tools.get_os_provider") as mock_get:
        provider = MagicMock()
        mock_get.return_value = provider
        provider.query_system_logs.return_value = ["log1"]

        res = await mcp_server.call_tool("query_system_logs", arguments={"limit": 10})
        data = parse_mcp_result(res)
        assert data["success"] is True
        assert data["logs"] == ["log1"]
        provider.query_system_logs.assert_called_once_with(10)


@pytest.mark.asyncio
async def test_query_system_logs_exception():
    with patch("systems_manager.os_provider_tools.get_os_provider") as mock_get:
        provider = MagicMock()
        mock_get.return_value = provider
        provider.query_system_logs.side_effect = Exception("error")
        res = await mcp_server.call_tool("query_system_logs")
        data = parse_mcp_result(res)
        assert data["success"] is False
        assert "error" in data


@pytest.mark.asyncio
async def test_system_trace():
    with (
        patch("systems_manager.os_provider_tools.get_os_provider") as mock_get,
        patch(
            "systems_manager.os_provider_tools.ctx_confirm_destructive",
            return_value=True,
        ),
    ):
        provider = MagicMock()
        mock_get.return_value = provider
        provider.start_system_trace.return_value = {"trace": "ok"}
        provider.stop_system_trace.return_value = {"trace": "stopped"}

        # start
        res = await mcp_server.call_tool(
            "start_system_trace", arguments={"session_name": "test_session"}
        )
        data = parse_mcp_result(res)
        assert data["success"] is True
        assert data["result"] == {"trace": "ok"}
        provider.start_system_trace.assert_called_once_with("test_session")

        # stop
        res2 = await mcp_server.call_tool(
            "stop_system_trace", arguments={"session_name": "test_session"}
        )
        data2 = parse_mcp_result(res2)
        assert data2["success"] is True
        assert data2["result"] == {"trace": "stopped"}
        provider.stop_system_trace.assert_called_once_with("test_session")


@pytest.mark.asyncio
async def test_start_system_trace_cancelled():
    with patch(
        "systems_manager.os_provider_tools.ctx_confirm_destructive", return_value=False
    ):
        res = await mcp_server.call_tool(
            "start_system_trace", arguments={"session_name": "test"}
        )
        data = parse_mcp_result(res)
        assert data["success"] is False
        assert "cancelled" in data["error"]


@pytest.mark.asyncio
async def test_system_trace_exception():
    with (
        patch("systems_manager.os_provider_tools.get_os_provider") as mock_get,
        patch(
            "systems_manager.os_provider_tools.ctx_confirm_destructive",
            return_value=True,
        ),
    ):
        provider = MagicMock()
        mock_get.return_value = provider
        provider.start_system_trace.side_effect = Exception("error")
        provider.stop_system_trace.side_effect = Exception("error")

        res1 = await mcp_server.call_tool(
            "start_system_trace", arguments={"session_name": "test"}
        )
        data1 = parse_mcp_result(res1)
        assert data1["success"] is False

        res2 = await mcp_server.call_tool(
            "stop_system_trace", arguments={"session_name": "test"}
        )
        data2 = parse_mcp_result(res2)
        assert data2["success"] is False
