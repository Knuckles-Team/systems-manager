import subprocess
from unittest.mock import MagicMock, patch

import psutil
import pytest

from systems_manager.os_provider import (
    LinuxProvider,
    WindowsProvider,
    get_os_provider,
)

# ----------------- OSProvider base tests -----------------


def test_get_process_details_all():
    """Test get_process_details when pid is None (iterates process list)."""
    provider = LinuxProvider()  # OSProvider is abstract, instantiate subclass

    mock_proc = MagicMock()
    mock_proc.info = {"pid": 123, "name": "python"}

    with patch("psutil.process_iter", return_value=[mock_proc]) as mock_iter:
        procs = provider.get_process_details()
        assert len(procs) == 1
        assert procs[0]["pid"] == 123
        mock_iter.assert_called_once()


def test_get_process_details_specific():
    """Test get_process_details for a specific PID."""
    provider = LinuxProvider()

    mock_proc = MagicMock()
    mock_proc.as_dict.return_value = {"pid": 456, "name": "pytest"}

    with patch("psutil.Process", return_value=mock_proc) as mock_pclass:
        procs = provider.get_process_details(pid=456)
        assert len(procs) == 1
        assert procs[0]["pid"] == 456
        mock_pclass.assert_called_once_with(456)


def test_get_process_details_no_such_process():
    """Test get_process_details handling psutil.NoSuchProcess."""
    provider = LinuxProvider()
    with patch("psutil.Process", side_effect=psutil.NoSuchProcess(pid=999)):
        procs = provider.get_process_details(pid=999)
        assert len(procs) == 0


def test_get_network_connections():
    """Test get_network_connections formatting addresses and error handling."""
    provider = LinuxProvider()

    # Create mock address tuples
    laddr_mock = MagicMock()
    laddr_mock.ip = "127.0.0.1"
    laddr_mock.port = 8080

    raddr_mock = MagicMock()
    raddr_mock.ip = "8.8.8.8"
    raddr_mock.port = 53

    family_mock = MagicMock()
    family_mock.name = "AF_INET"

    type_mock = MagicMock()
    type_mock.name = "SOCK_STREAM"

    mock_conn = MagicMock()
    mock_conn.fd = 5
    mock_conn.family = family_mock
    mock_conn.type = type_mock
    mock_conn.laddr = laddr_mock
    mock_conn.raddr = raddr_mock
    mock_conn.status = "ESTABLISHED"
    mock_conn.pid = 123

    # Test happy path
    with patch("psutil.net_connections", return_value=[mock_conn]):
        conns = provider.get_network_connections()
        assert len(conns) == 1
        assert conns[0]["laddr"] == "127.0.0.1:8080"
        assert conns[0]["raddr"] == "8.8.8.8:53"
        assert conns[0]["family"] == "AF_INET"
        assert conns[0]["type"] == "SOCK_STREAM"

    # Test address formatting variants (missing raddr, string address)
    mock_conn_str = MagicMock()
    mock_conn_str.laddr = "some_address_str"
    mock_conn_str.raddr = None
    mock_conn_str.family = "AF_UNIX"
    mock_conn_str.type = "SOCK_DGRAM"
    with patch("psutil.net_connections", return_value=[mock_conn_str]):
        conns2 = provider.get_network_connections()
        assert len(conns2) == 1
        assert conns2[0]["laddr"] == "some_address_str"
        assert conns2[0]["raddr"] is None

    # Test AccessDenied exception
    with patch("psutil.net_connections", side_effect=psutil.AccessDenied):
        conns3 = provider.get_network_connections()
        assert len(conns3) == 0


def test_capture_system_snapshot():
    """Test capture_system_snapshot fetches metrics correctly."""
    provider = LinuxProvider()

    mem_mock = MagicMock()
    mem_mock._asdict.return_value = {"total": 8000, "free": 4000}

    disk_mock = MagicMock()
    disk_mock._asdict.return_value = {"total": 100000, "free": 50000}

    user_mock = MagicMock()
    user_mock.name = "testuser"

    with (
        patch("psutil.cpu_percent", return_value=12.5),
        patch("psutil.virtual_memory", return_value=mem_mock),
        patch("psutil.disk_usage", return_value=disk_mock),
        patch("psutil.pids", return_value=[1, 2]),
        patch("psutil.users", return_value=[user_mock]),
        patch("psutil.boot_time", return_value=1000000.0),
    ):
        snapshot = provider.capture_system_snapshot()
        assert snapshot["cpu_percent"] == 12.5
        assert snapshot["memory"]["total"] == 8000
        assert snapshot["disk"]["total"] == 100000
        assert snapshot["processes_count"] == 2
        assert snapshot["users"] == ["testuser"]
        assert snapshot["boot_time"] == 1000000.0


# ----------------- LinuxProvider specific tests -----------------


def test_linux_provider_list_services():
    """Test Linux-specific list_services using systemctl."""
    provider = LinuxProvider()

    # Happy path
    fake_stdout = (
        "UNIT                                                      LOAD   ACTIVE SUB     DESCRIPTION\n"
        "ssh.service                                               loaded active running OpenSSH Daemon\n"
        "cron.service                                              loaded active running Regular background program processing daemon\n"
    )
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=fake_stdout, stderr="")
        services = provider.list_services()
        assert len(services) == 2
        assert services[0]["name"] == "ssh.service"
        assert services[0]["load"] == "loaded"
        assert services[0]["active"] == "active"
        assert services[0]["sub"] == "running"
        assert "OpenSSH Daemon" in services[0]["description"]

    # Error path
    with patch(
        "subprocess.run", side_effect=subprocess.CalledProcessError(1, "systemctl")
    ):
        services_err = provider.list_services()
        assert len(services_err) == 1
        assert "error" in services_err[0]


def test_linux_provider_manage_service():
    """Test Linux-specific manage_service using systemctl."""
    provider = LinuxProvider()

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="done", stderr="")
        res = provider.manage_service("ssh", "restart")
        assert res["success"] is True
        assert res["action"] == "restart"
        assert res["service"] == "ssh"
        mock_run.assert_called_with(
            ["sudo", "systemctl", "restart", "ssh"], capture_output=True, text=True
        )

    # Exception path
    with patch("subprocess.run", side_effect=Exception("Timeout")):
        res_err = provider.manage_service("ssh", "restart")
        assert res_err["success"] is False
        assert "Timeout" in res_err["error"]


def test_linux_provider_list_kernel_modules():
    """Test Linux-specific list_kernel_modules using lsmod."""
    provider = LinuxProvider()

    fake_stdout = (
        "Module                  Size  Used by\n"
        "ext4                  704512  1\n"
        "jbd2                  126976  1 ext4\n"
    )
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=fake_stdout, stderr="")
        modules = provider.list_kernel_modules()
        assert len(modules) == 2
        assert modules[0]["name"] == "ext4"
        assert modules[0]["size"] == "704512"
        assert modules[0]["used_by"] == "1"

    # Error path
    with patch("subprocess.run", side_effect=Exception("lsmod not found")):
        modules_err = provider.list_kernel_modules()
        assert len(modules_err) == 1
        assert "error" in modules_err[0]


def test_linux_provider_query_system_logs():
    """Test Linux-specific query_system_logs using journalctl."""
    provider = LinuxProvider()

    fake_json_line = '{"__REALTIME_TIMESTAMP": "1620000000000", "MESSAGE": "User logged in", "PRIORITY": "6"}'
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=0, stdout=fake_json_line, stderr=""
        )
        logs = provider.query_system_logs(limit=10)
        assert len(logs) == 1
        assert logs[0]["MESSAGE"] == "User logged in"
        mock_run.assert_called_with(
            ["journalctl", "-n", "10", "-o", "json"],
            capture_output=True,
            text=True,
            check=True,
        )

    # Error path
    with patch("subprocess.run", side_effect=Exception("No journald")):
        logs_err = provider.query_system_logs(limit=10)
        assert len(logs_err) == 1
        assert "error" in logs_err[0]


def test_linux_provider_tracing():
    """Test start and stop trace functions on Linux (unimplemented)."""
    provider = LinuxProvider()
    res_start = provider.start_system_trace("trace_session")
    assert res_start["success"] is False
    res_stop = provider.stop_system_trace("trace_session")
    assert res_stop["success"] is False


# ----------------- WindowsProvider specific tests -----------------


def test_windows_provider_run_powershell_json():
    """Test Windows-specific powershell conversion wrapper."""
    provider = WindowsProvider()

    # Happy path returning list
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=0, stdout='[{"Status": "Running"}]', stderr=""
        )
        res = provider._run_powershell_json("Get-Service")
        assert isinstance(res, list)
        assert res[0]["Status"] == "Running"

    # Happy path returning empty string
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="   ", stderr="")
        res = provider._run_powershell_json("Get-Service")
        assert res == []

    # Error path
    with patch("subprocess.run", side_effect=Exception("Powershell crash")):
        res_err = provider._run_powershell_json("Get-Service")
        assert "error" in res_err


def test_windows_provider_list_services():
    """Test Windows list_services under list, dict, or error results."""
    provider = WindowsProvider()

    # Service list return
    with patch.object(
        provider, "_run_powershell_json", return_value=[{"Name": "wuauserv"}]
    ):
        services = provider.list_services()
        assert len(services) == 1
        assert services[0]["Name"] == "wuauserv"

    # Single service return (dict)
    with patch.object(
        provider, "_run_powershell_json", return_value={"Name": "wuauserv"}
    ):
        services_dict = provider.list_services()
        assert len(services_dict) == 1
        assert services_dict[0]["Name"] == "wuauserv"

    # Error return
    with patch.object(
        provider, "_run_powershell_json", return_value={"error": "Failed"}
    ):
        services_err = provider.list_services()
        assert len(services_err) == 1
        assert "error" in services_err[0]


def test_windows_provider_manage_service():
    """Test Windows manage_service with action mapping."""
    provider = WindowsProvider()

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="Stopped", stderr="")
        res = provider.manage_service("wuauserv", "stop")
        assert res["success"] is True
        assert res["action"] == "stop"
        assert res["service"] == "wuauserv"
        mock_run.assert_called_with(
            ["powershell", "-Command", "Stop-Service -Name wuauserv"],
            capture_output=True,
            text=True,
        )

    # Exception path
    with patch("subprocess.run", side_effect=Exception("Access denied")):
        res_err = provider.manage_service("wuauserv", "start")
        assert res_err["success"] is False
        assert "Access denied" in res_err["error"]


def test_windows_provider_list_kernel_modules():
    """Test Windows list_kernel_modules using driverquery."""
    provider = WindowsProvider()

    fake_csv = (
        '"Module Name","Display Name","Driver Type","Link Date"\n'
        '"intelpep","Intel Power Engine Plug-in","Kernel ","1/1/2026"\n'
    )
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=fake_csv, stderr="")
        modules = provider.list_kernel_modules()
        assert len(modules) == 1
        assert modules[0]["Module Name"] == "intelpep"

    # Empty / short return path
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=0, stdout='"Module Name"\n', stderr=""
        )
        modules_empty = provider.list_kernel_modules()
        assert len(modules_empty) == 0

    # Exception path
    with patch("subprocess.run", side_effect=Exception("driverquery failed")):
        modules_err = provider.list_kernel_modules()
        assert len(modules_err) == 1
        assert "error" in modules_err[0]


def test_windows_provider_query_system_logs():
    """Test Windows query_system_logs with event log commands."""
    provider = WindowsProvider()

    with patch.object(
        provider,
        "_run_powershell_json",
        return_value=[{"Message": "Event log message"}],
    ):
        logs = provider.query_system_logs(limit=5)
        assert len(logs) == 1
        assert logs[0]["Message"] == "Event log message"

    # Single dict return path
    with patch.object(
        provider, "_run_powershell_json", return_value={"Message": "Event log message"}
    ):
        logs_dict = provider.query_system_logs(limit=5)
        assert len(logs_dict) == 1


def test_windows_provider_tracing():
    """Test logman trace start and stop on Windows."""
    provider = WindowsProvider()

    # Tracing start
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=0, stdout="Tracing started", stderr=""
        )
        res = provider.start_system_trace("WindowsTrace")
        assert res["success"] is True
        assert "started" in res["stdout"]

    # Exception tracing start
    with patch("subprocess.run", side_effect=Exception("Logman error")):
        res_start_err = provider.start_system_trace("WindowsTrace")
        assert res_start_err["success"] is False

    # Tracing stop
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=0, stdout="Tracing stopped", stderr=""
        )
        res = provider.stop_system_trace("WindowsTrace")
        assert res["success"] is True
        assert "stopped" in res["stdout"]

    # Exception tracing stop
    with patch("subprocess.run", side_effect=Exception("Logman error")):
        res_stop_err = provider.stop_system_trace("WindowsTrace")
        assert res_stop_err["success"] is False


# ----------------- get_os_provider tests -----------------


def test_get_os_provider():
    """Map only explicitly supported operating-system providers."""
    with patch("platform.system", return_value="Windows"):
        assert isinstance(get_os_provider(), WindowsProvider)

    with patch("platform.system", return_value="Linux"):
        assert isinstance(get_os_provider(), LinuxProvider)

    with patch("platform.system", return_value="Darwin"):
        with pytest.raises(RuntimeError, match="Unsupported"):
            get_os_provider()

    with patch("platform.system", return_value="UnknownOS"):
        with pytest.raises(RuntimeError, match="Unsupported"):
            get_os_provider()
