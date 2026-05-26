import json
from unittest.mock import MagicMock, patch
import pytest

from systems_manager.mcp_server import get_mcp_instance
from systems_manager.systems_manager import CommandResult

args, mcp_server, middlewares = get_mcp_instance()

@pytest.mark.asyncio
async def test_remote_routing_sm_system_operations():
    # Mock HostManager to return custom connection details
    mock_host_manager = MagicMock()
    
    # Mock the hosts inventory dictionary and config path
    mock_host_manager.hosts = {
        "node-alpha": {
            "hostname": "192.168.1.50",
            "port": 2222,
            "user": "test-remote-user",
            "identity_file": "/path/to/key",
        }
    }
    mock_host_manager.config_file = "/fake/inventory.yaml"
    mock_host_manager.get_host_connection_details.return_value = {
        "hostname": "192.168.1.50",
        "port": 2222,
        "user": "test-remote-user",
        "identity_file": "/path/to/key",
    }

    # Mock subprocess.run to intercept remote ssh executions
    with patch("tunnel_manager.tunnel_manager.HostManager", return_value=mock_host_manager), \
         patch("subprocess.run") as mock_run:
        
        # Setup mock execution return value for ssh remote command check (e.g. uname check)
        mock_uname_res = MagicMock()
        mock_uname_res.returncode = 0
        mock_uname_res.stdout = "Linux\n"
        mock_uname_res.stderr = ""
        
        mock_stats_res = MagicMock()
        mock_stats_res.returncode = 0
        mock_stats_res.stdout = '{"cpu_count": 8, "cpu_percent": 12.5}'
        mock_stats_res.stderr = ""
        
        mock_run.side_effect = [mock_uname_res, mock_stats_res]

        # Call sm_system_operations targeting a remote host
        res = await mcp_server.call_tool(
            "sm_system_operations",
            arguments={
                "action": "get_os_statistics",
                "target_host": "node-alpha"
            }
        )
        
        # Verify result was deserialized correctly from remote_eval stdout
        text = res.content[0].text
        data = json.loads(text)
        assert data["cpu_count"] == 8
        assert data["cpu_percent"] == 12.5

        # Check that subprocess.run was called with ssh parameters
        assert mock_run.call_count >= 1
        first_call_args = mock_run.call_args_list[0][0][0]
        assert "ssh" in first_call_args
        assert "test-remote-user@192.168.1.50" in first_call_args
        assert "-p" in first_call_args
        assert "2222" in first_call_args
