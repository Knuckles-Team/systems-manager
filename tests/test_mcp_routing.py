import json
from unittest.mock import MagicMock, patch

import pytest
from fastmcp.exceptions import ToolError

from systems_manager.mcp_server import get_mcp_instance
from systems_manager.systems_manager import CommandResult, WindowsManager

# Since FastMCP tool routing can be tested directly with call_tool,
# we initialize get_mcp_instance once at module level for speed.
args, mcp_server, middlewares = get_mcp_instance()


def parse_mcp_result(res):
    text = getattr(res.content[0], "text", "")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def assert_result_equals(actual, expected):
    if isinstance(expected, CommandResult):
        assert isinstance(actual, dict)
        assert actual["success"] == expected.success
        if expected.message is not None:
            assert actual["message"] == expected.message
        if expected.error is not None:
            assert actual["error"] == expected.error
    else:
        assert actual == expected


@pytest.mark.asyncio
async def test_health_check():
    res = await mcp_server.call_tool("health_check")
    assert getattr(res.content[0], "text", "") == "OK"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "action, manager_method, arguments, expected_return",
    [
        (
            "install_applications",
            "install_applications",
            {"packages": ["htop"]},
            {"success": True},
        ),
        ("update", "update", {}, CommandResult(success=True)),
        ("clean", "clean", {}, CommandResult(success=True)),
        ("optimize", "optimize", {}, CommandResult(success=True)),
        (
            "install_python_modules",
            "install_python_modules",
            {"packages": ["requests"]},
            CommandResult(success=True),
        ),
        ("get_os_statistics", "get_os_statistics", {}, CommandResult(success=True)),
        (
            "get_hardware_statistics",
            "get_hardware_statistics",
            {},
            CommandResult(success=True),
        ),
        (
            "search_package",
            "search_package",
            {"package": "git"},
            CommandResult(success=True),
        ),
        (
            "get_package_info",
            "get_package_info",
            {"package": "git"},
            CommandResult(success=True),
        ),
        (
            "list_installed_packages",
            "list_installed_packages",
            {},
            CommandResult(success=True),
        ),
        (
            "list_upgradable_packages",
            "list_upgradable_packages",
            {},
            CommandResult(success=True),
        ),
        ("system_health_check", "system_health_check", {}, CommandResult(success=True)),
        ("get_uptime", "get_uptime", {}, CommandResult(success=True)),
        ("list_env_vars", "list_env_vars", {}, CommandResult(success=True)),
        (
            "get_env_var",
            "get_env_var",
            {"env_var": "PATH"},
            CommandResult(success=True),
        ),
        ("clean_temp_files", "clean_temp_files", {}, CommandResult(success=True)),
        ("clean_package_cache", "clean_package_cache", {}, CommandResult(success=True)),
        (
            "add_repository",
            "add_repository",
            {"repository": "ppa:test"},
            CommandResult(success=True),
        ),
        (
            "install_local_package",
            "install_local_package",
            {"file_path": "/path/to/pkg"},
            CommandResult(success=True),
        ),
    ],
)
async def test_sm_system_operations(action, manager_method, arguments, expected_return):
    with patch("systems_manager.mcp_server.detect_and_create_manager") as mock_detect:
        mgr = MagicMock()
        mock_detect.return_value = mgr
        getattr(mgr, manager_method).return_value = expected_return

        args_payload = {"action": action, **arguments}
        res = await mcp_server.call_tool("sm_system_operations", arguments=args_payload)

        actual = parse_mcp_result(res)
        assert_result_equals(actual, expected_return)
        getattr(mgr, manager_method).assert_called_once()


@pytest.mark.asyncio
async def test_sm_system_operations_windows_features():
    # Test WindowsManager optional feature paths
    with patch("systems_manager.mcp_server.detect_and_create_manager") as mock_detect:
        win_mgr = MagicMock(spec=WindowsManager)
        mock_detect.return_value = win_mgr

        # list_windows_features
        win_mgr.list_windows_features.return_value = ["Feature1"]
        res = await mcp_server.call_tool(
            "sm_system_operations", arguments={"action": "list_windows_features"}
        )
        actual = parse_mcp_result(res)
        assert actual == ["Feature1"]
        win_mgr.list_windows_features.assert_called_once()

        # enable_windows_features
        win_mgr.enable_windows_features.return_value = {"success": True}
        res = await mcp_server.call_tool(
            "sm_system_operations",
            arguments={"action": "enable_windows_features", "feature_name": "IIS"},
        )
        actual = parse_mcp_result(res)
        assert actual == {"success": True}
        win_mgr.enable_windows_features.assert_called_with(["IIS"])

        # disable_windows_features
        win_mgr.disable_windows_features.return_value = {"success": True}
        res = await mcp_server.call_tool(
            "sm_system_operations",
            arguments={"action": "disable_windows_features", "feature_name": "IIS"},
        )
        actual = parse_mcp_result(res)
        assert actual == {"success": True}
        win_mgr.disable_windows_features.assert_called_with(["IIS"])


@pytest.mark.asyncio
async def test_sm_system_operations_windows_features_not_supported():
    # If not a WindowsManager, list/enable/disable features return "Not supported"
    with patch("systems_manager.mcp_server.detect_and_create_manager") as mock_detect:
        non_win_mgr = MagicMock()  # generic manager, not WindowsManager
        mock_detect.return_value = non_win_mgr

        res = await mcp_server.call_tool(
            "sm_system_operations", arguments={"action": "list_windows_features"}
        )
        assert getattr(res.content[0], "text", "") == "Not supported"

        res = await mcp_server.call_tool(
            "sm_system_operations",
            arguments={"action": "enable_windows_features", "feature_name": "IIS"},
        )
        assert getattr(res.content[0], "text", "") == "Not supported"

        res = await mcp_server.call_tool(
            "sm_system_operations",
            arguments={"action": "disable_windows_features", "feature_name": "IIS"},
        )
        assert getattr(res.content[0], "text", "") == "Not supported"


@pytest.mark.asyncio
async def test_sm_system_operations_error_handling():
    with patch(
        "systems_manager.mcp_server.detect_and_create_manager",
        side_effect=Exception("System Crash"),
    ):
        with pytest.raises(ToolError) as exc_info:
            await mcp_server.call_tool(
                "sm_system_operations", arguments={"action": "update"}
            )
        assert "System Crash" in str(exc_info.value)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "action, manager_method, arguments, expected_return",
    [
        ("list_services", "list_services", {}, ["service1"]),
        (
            "get_service_status",
            "get_service_status",
            {"service_name": "nginx"},
            "running",
        ),
        ("start_service", "start_service", {"service_name": "nginx"}, "started"),
        ("stop_service", "stop_service", {"service_name": "nginx"}, "stopped"),
        ("restart_service", "restart_service", {"service_name": "nginx"}, "restarted"),
        ("enable_service", "enable_service", {"service_name": "nginx"}, "enabled"),
        ("disable_service", "disable_service", {"service_name": "nginx"}, "disabled"),
    ],
)
async def test_sm_service_operations(
    action, manager_method, arguments, expected_return
):
    with patch("systems_manager.mcp_server.detect_and_create_manager") as mock_detect:
        mgr = MagicMock()
        mock_detect.return_value = mgr
        getattr(mgr, manager_method).return_value = expected_return

        args_payload = {"action": action, **arguments}
        res = await mcp_server.call_tool(
            "sm_service_operations", arguments=args_payload
        )

        actual = parse_mcp_result(res)
        assert_result_equals(actual, expected_return)
        getattr(mgr, manager_method).assert_called_once()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "action, manager_method, arguments, expected_return, verify_args",
    [
        ("list_processes", "list_processes", {}, ["proc1"], ()),
        ("get_process_info", "get_process_info", {"pid": 1234}, "info_dict", (1234,)),
        ("get_process_info", None, {}, "pid is required", None),
        ("kill_process", "kill_process", {"pid": 5678}, "killed", (5678,)),
        ("kill_process", None, {}, "pid is required", None),
    ],
)
async def test_sm_process_operations(
    action, manager_method, arguments, expected_return, verify_args
):
    with patch("systems_manager.mcp_server.detect_and_create_manager") as mock_detect:
        mgr = MagicMock()
        mock_detect.return_value = mgr
        if manager_method:
            getattr(mgr, manager_method).return_value = expected_return

        args_payload = {"action": action, **arguments}
        res = await mcp_server.call_tool(
            "sm_process_operations", arguments=args_payload
        )

        actual = parse_mcp_result(res)
        assert_result_equals(actual, expected_return)
        if manager_method:
            getattr(mgr, manager_method).assert_called_once_with(*verify_args)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "action, manager_method, arguments, expected_return, verify_args",
    [
        ("list_network_interfaces", "list_network_interfaces", {}, ["eth0"], ()),
        ("list_open_ports", "list_open_ports", {}, [80, 443], ()),
        (
            "ping_host",
            "ping_host",
            {"host": "google.com", "count": 2},
            "ping ok",
            ("google.com", 2),
        ),
        (
            "dns_lookup",
            "dns_lookup",
            {"host": "google.com"},
            "127.0.0.1",
            ("google.com",),
        ),
    ],
)
async def test_sm_network_operations(
    action, manager_method, arguments, expected_return, verify_args
):
    with patch("systems_manager.mcp_server.detect_and_create_manager") as mock_detect:
        mgr = MagicMock()
        mock_detect.return_value = mgr
        getattr(mgr, manager_method).return_value = expected_return

        args_payload = {"action": action, **arguments}
        res = await mcp_server.call_tool(
            "sm_network_operations", arguments=args_payload
        )

        actual = parse_mcp_result(res)
        assert_result_equals(actual, expected_return)
        getattr(mgr, manager_method).assert_called_once_with(*verify_args)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "action, manager_method, arguments, expected_return, verify_args",
    [
        ("list_disks", "list_disks", {}, ["/dev/sda"], ()),
        ("get_disk_usage", "get_disk_usage", {"path": "/var"}, "usage_str", ("/var",)),
        (
            "get_disk_usage",
            "get_disk_usage",
            {},
            "usage_str",
            ("/",),
        ),  # default path '/'
        ("get_disk_space_report", "get_disk_space_report", {}, "report_str", ()),
    ],
)
async def test_sm_disk_operations(
    action, manager_method, arguments, expected_return, verify_args
):
    with patch("systems_manager.mcp_server.detect_and_create_manager") as mock_detect:
        mgr = MagicMock()
        mock_detect.return_value = mgr
        getattr(mgr, manager_method).return_value = expected_return

        args_payload = {"action": action, **arguments}
        res = await mcp_server.call_tool("sm_disk_operations", arguments=args_payload)

        actual = parse_mcp_result(res)
        assert_result_equals(actual, expected_return)
        getattr(mgr, manager_method).assert_called_once_with(*verify_args)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "action, manager_method, expected_return",
    [
        ("list_users", "list_users", ["root"]),
        ("list_groups", "list_groups", ["wheel"]),
    ],
)
async def test_sm_user_operations(action, manager_method, expected_return):
    with patch("systems_manager.mcp_server.detect_and_create_manager") as mock_detect:
        mgr = MagicMock()
        mock_detect.return_value = mgr
        getattr(mgr, manager_method).return_value = expected_return

        res = await mcp_server.call_tool(
            "sm_user_operations", arguments={"action": action}
        )

        actual = parse_mcp_result(res)
        assert_result_equals(actual, expected_return)
        getattr(mgr, manager_method).assert_called_once()


@pytest.mark.asyncio
async def test_sm_file_operations():
    with patch("systems_manager.mcp_server.detect_and_create_manager") as mock_detect:
        mgr = MagicMock()
        mock_detect.return_value = mgr

        # run_command
        mgr.run_command.return_value = CommandResult(success=True)
        res = await mcp_server.call_tool(
            "sm_file_operations",
            arguments={"action": "run_command", "command": "whoami"},
        )
        actual = parse_mcp_result(res)
        assert actual["success"] is True
        mgr.run_command.assert_called_once_with("whoami")

        # get_system_logs
        mgr.get_system_logs.return_value = ["log1"]
        res = await mcp_server.call_tool(
            "sm_file_operations", arguments={"action": "get_system_logs", "lines": 50}
        )
        actual = parse_mcp_result(res)
        assert actual == ["log1"]
        mgr.get_system_logs.assert_called_once_with(lines=50)

        # tail_log_file
        mgr.tail_log_file.return_value = ["log2"]
        res = await mcp_server.call_tool(
            "sm_file_operations",
            arguments={
                "action": "tail_log_file",
                "filepath": "/var/log/syslog",
                "lines": 20,
            },
        )
        actual = parse_mcp_result(res)
        assert actual == ["log2"]
        mgr.tail_log_file.assert_called_once_with("/var/log/syslog", 20)

        # list_files
        mgr.fs_manager.list_files.return_value = ["file1.txt"]
        res = await mcp_server.call_tool(
            "sm_file_operations",
            arguments={
                "action": "list_files",
                "filepath": "/home",
                "recursive": True,
                "depth": 3,
            },
        )
        actual = parse_mcp_result(res)
        assert actual == ["file1.txt"]
        mgr.fs_manager.list_files.assert_called_once_with("/home", True, 3)

        # search_files
        mgr.fs_manager.search_files.return_value = ["found.txt"]
        res = await mcp_server.call_tool(
            "sm_file_operations",
            arguments={
                "action": "search_files",
                "filepath": "/etc",
                "pattern": "*.conf",
            },
        )
        actual = parse_mcp_result(res)
        assert actual == ["found.txt"]
        mgr.fs_manager.search_files.assert_called_once_with("/etc", "*.conf")

        # grep_files
        mgr.fs_manager.grep_files.return_value = ["matched line"]
        res = await mcp_server.call_tool(
            "sm_file_operations",
            arguments={
                "action": "grep_files",
                "filepath": "/var",
                "pattern": "error",
                "recursive": True,
            },
        )
        actual = parse_mcp_result(res)
        assert actual == ["matched line"]
        mgr.fs_manager.grep_files.assert_called_once_with("/var", "error", True)

        # manage_file
        mgr.fs_manager.manage_file.return_value = "file_content"
        res = await mcp_server.call_tool(
            "sm_file_operations",
            arguments={
                "action": "manage_file",
                "file_action": "write",
                "filepath": "/tmp/test",
                "content": "hello",
            },
        )
        actual = parse_mcp_result(res)
        assert actual == "file_content"
        mgr.fs_manager.manage_file.assert_called_once_with(
            "write", "/tmp/test", "hello"
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "action, manager_method, arguments, expected_return, verify_args",
    [
        ("list_cron_jobs", "list_cron_jobs", {"user": "admin"}, ["job1"], ("admin",)),
        (
            "add_cron_job",
            "add_cron_job",
            {"command": "echo hello", "schedule": "* * * * *", "user": "admin"},
            "added",
            ("echo hello", "* * * * *", "admin"),
        ),
        (
            "remove_cron_job",
            "remove_cron_job",
            {"command": "echo hello", "user": "admin"},
            "removed",
            ("echo hello", "admin"),
        ),
    ],
)
async def test_sm_cron_operations(
    action, manager_method, arguments, expected_return, verify_args
):
    with patch("systems_manager.mcp_server.detect_and_create_manager") as mock_detect:
        mgr = MagicMock()
        mock_detect.return_value = mgr
        getattr(mgr, manager_method).return_value = expected_return

        args_payload = {"action": action, **arguments}
        res = await mcp_server.call_tool("sm_cron_operations", arguments=args_payload)

        actual = parse_mcp_result(res)
        assert_result_equals(actual, expected_return)
        getattr(mgr, manager_method).assert_called_once_with(*verify_args)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "action, manager_method, arguments, expected_return, verify_args",
    [
        ("get_firewall_status", "get_firewall_status", {}, "active", ()),
        (
            "add_firewall_rule",
            "add_firewall_rule",
            {"rule": "allow 80/tcp"},
            "added",
            ("allow 80/tcp",),
        ),
        (
            "remove_firewall_rule",
            "remove_firewall_rule",
            {"rule": "allow 80/tcp"},
            "removed",
            ("allow 80/tcp",),
        ),
    ],
)
async def test_sm_firewall_operations(
    action, manager_method, arguments, expected_return, verify_args
):
    with patch("systems_manager.mcp_server.detect_and_create_manager") as mock_detect:
        mgr = MagicMock()
        mock_detect.return_value = mgr
        getattr(mgr, manager_method).return_value = expected_return

        args_payload = {"action": action, **arguments}
        res = await mcp_server.call_tool(
            "sm_firewall_operations", arguments=args_payload
        )

        actual = parse_mcp_result(res)
        assert_result_equals(actual, expected_return)
        getattr(mgr, manager_method).assert_called_once_with(*verify_args)


@pytest.mark.asyncio
async def test_sm_advanced_operations():
    with patch("systems_manager.mcp_server.detect_and_create_manager") as mock_detect:
        mgr = MagicMock()
        mock_detect.return_value = mgr

        # add_authorized_key
        mgr.add_authorized_key.return_value = CommandResult(success=True)
        res = await mcp_server.call_tool(
            "sm_advanced_operations",
            arguments={"action": "add_authorized_key", "public_key": "ssh-rsa aaa"},
        )
        actual = parse_mcp_result(res)
        assert actual["success"] is True
        mgr.add_authorized_key.assert_called_once_with("ssh-rsa aaa")

        # add_alias
        mgr.shell_manager.add_alias.return_value = CommandResult(success=True)
        res = await mcp_server.call_tool(
            "sm_advanced_operations",
            arguments={"action": "add_alias", "name": "ll", "command": "ls -l"},
        )
        actual = parse_mcp_result(res)
        assert actual["success"] is True
        mgr.shell_manager.add_alias.assert_called_once_with("ll", "ls -l")

        # install_uv
        mgr.python_manager.install_uv.return_value = CommandResult(success=True)
        res = await mcp_server.call_tool(
            "sm_advanced_operations", arguments={"action": "install_uv"}
        )
        actual = parse_mcp_result(res)
        assert actual["success"] is True
        mgr.python_manager.install_uv.assert_called_once()

        # create_venv
        mgr.python_manager.create_venv.return_value = CommandResult(success=True)
        res = await mcp_server.call_tool(
            "sm_advanced_operations",
            arguments={"action": "create_venv", "path": "/venv", "version": "3.11"},
        )
        actual = parse_mcp_result(res)
        assert actual["success"] is True
        mgr.python_manager.create_venv.assert_called_once_with("/venv", "3.11")

        # install_package
        mgr.python_manager.install_package.return_value = CommandResult(success=True)
        res = await mcp_server.call_tool(
            "sm_advanced_operations",
            arguments={
                "action": "install_package",
                "package": "requests",
                "path": "/venv",
            },
        )
        actual = parse_mcp_result(res)
        assert actual["success"] is True
        mgr.python_manager.install_package.assert_called_once_with("requests", "/venv")

        # install_nvm
        mgr.node_manager.install_nvm.return_value = CommandResult(success=True)
        res = await mcp_server.call_tool(
            "sm_advanced_operations", arguments={"action": "install_nvm"}
        )
        actual = parse_mcp_result(res)
        assert actual["success"] is True
        mgr.node_manager.install_nvm.assert_called_once()

        # install_node
        mgr.node_manager.install_node.return_value = CommandResult(success=True)
        res = await mcp_server.call_tool(
            "sm_advanced_operations",
            arguments={"action": "install_node", "version": "20"},
        )
        actual = parse_mcp_result(res)
        assert actual["success"] is True
        mgr.node_manager.install_node.assert_called_once_with("20")

        # use_node
        mgr.node_manager.use_node.return_value = CommandResult(success=True)
        res = await mcp_server.call_tool(
            "sm_advanced_operations", arguments={"action": "use_node", "version": "20"}
        )
        actual = parse_mcp_result(res)
        assert actual["success"] is True
        mgr.node_manager.use_node.assert_called_once_with("20")
