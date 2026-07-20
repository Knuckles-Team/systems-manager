"""Tests for SystemsManagerBase and helper classes."""

import base64
import json
import os
import platform as platform_module
from pathlib import Path
from unittest.mock import Mock, mock_open, patch

import psutil
import pytest

from systems_manager.systems_manager import (
    FileSystemManager,
    NodeManager,
    PythonManager,
    SystemsManagerBase,
    setup_logging,
)


class TestSetupLogging:
    """Tests for setup_logging function."""

    def test_setup_logging_default(self):
        """Test metadata-only stderr logging."""
        logger = setup_logging()
        assert logger is not None


class TestFileSystemManager:
    """Tests for FileSystemManager class."""

    @pytest.fixture
    def fs_manager(self, mock_logger, monkeypatch, tmp_path):
        """Create a FileSystemManager instance for testing."""
        monkeypatch.setenv("SYSTEMS_MANAGER_FILESYSTEM_ROOT", str(tmp_path))
        manager = Mock()
        manager.logger = mock_logger
        return FileSystemManager(manager)

    def test_list_files_nonexistent_path(self, fs_manager):
        """Test listing files from a non-existent path."""
        result = fs_manager.list_files("missing")
        assert result["success"] is False
        assert result["error"] == "Operation failed"

    def test_list_files_current_directory(self, fs_manager, tmp_path):
        """Test listing files from current directory."""
        # Create some test files
        (tmp_path / "test1.txt").write_text("content1")
        (tmp_path / "test2.txt").write_text("content2")
        (tmp_path / "subdir").mkdir()

        result = fs_manager.list_files(str(tmp_path))
        assert result["success"] is True
        assert result["total"] == 3
        assert len(result["items"]) == 3

    def test_list_files_recursive(self, fs_manager, tmp_path):
        """Test recursive file listing."""
        (tmp_path / "test1.txt").write_text("content1")
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        (subdir / "test2.txt").write_text("content2")

        result = fs_manager.list_files(str(tmp_path), recursive=True, depth=2)
        assert result["success"] is True
        assert result["total"] >= 2

    def test_search_files(self, fs_manager, tmp_path):
        """Test searching for files."""
        (tmp_path / "test_file.txt").write_text("content")
        (tmp_path / "other_file.txt").write_text("content")

        result = fs_manager.search_files(str(tmp_path), "test")
        assert result["success"] is True
        assert len(result["matches"]) >= 1

    def test_grep_files(self, fs_manager, tmp_path, monkeypatch):
        """Test grepping files for content."""
        (tmp_path / "test.txt").write_text("hello world")

        # Mock the run_command method
        mock_result = {"success": True, "stdout": "hello world"}
        fs_manager.manager.run_command = Mock(return_value=mock_result)

        result = fs_manager.grep_files(str(tmp_path), "hello")
        assert result["success"] is True

    def test_manage_file_create(self, fs_manager, tmp_path):
        """Test creating a file."""
        test_file = tmp_path / "new_file.txt"
        result = fs_manager.manage_file("create", str(test_file), "test content")
        assert result["success"] is True
        assert test_file.exists()
        assert test_file.read_text() == "test content"

    def test_manage_file_update(self, fs_manager, tmp_path):
        """Test updating a file."""
        test_file = tmp_path / "update_file.txt"
        test_file.write_text("old content")
        result = fs_manager.manage_file("update", str(test_file), "new content")
        assert result["success"] is True
        assert test_file.read_text() == "new content"

    def test_manage_file_delete(self, fs_manager, tmp_path):
        """Test deleting a file."""
        test_file = tmp_path / "delete_file.txt"
        test_file.write_text("content")
        result = fs_manager.manage_file("delete", str(test_file))
        assert result["success"] is True
        assert not test_file.exists()

    def test_manage_file_read(self, fs_manager, tmp_path):
        """Test reading a file."""
        test_file = tmp_path / "read_file.txt"
        test_file.write_text("file content")
        result = fs_manager.manage_file("read", str(test_file))
        assert result["success"] is True
        assert result["content"] == "file content"

    def test_manage_file_read_nonexistent(self, fs_manager):
        """Test reading a non-existent file."""
        result = fs_manager.manage_file("read", "missing.txt")
        assert result["success"] is False
        assert "not found" in result["error"]

    def test_manage_file_unknown_action(self, fs_manager):
        """Test unknown file action."""
        result = fs_manager.manage_file("unknown", "/some/path")
        assert result["success"] is False
        assert "Unknown action" in result["error"]


class TestPythonManager:
    """Tests for PythonManager class."""

    @pytest.fixture
    def python_manager(self, mock_logger, monkeypatch, tmp_path):
        """Create a PythonManager instance for testing."""
        monkeypatch.setenv("SYSTEMS_MANAGER_FILESYSTEM_ROOT", str(tmp_path))
        manager = Mock()
        manager.run_command = Mock(return_value={"success": True})
        return PythonManager(manager)

    def test_install_uv_linux(self, python_manager, monkeypatch):
        """Test installing uv on Linux."""
        monkeypatch.setattr(platform_module, "system", lambda: "Linux")
        monkeypatch.setenv("SYSTEMS_MANAGER_UV_VERSION", "1.2.3")
        result = python_manager.install_uv()
        assert result["success"] is True
        command = python_manager.manager.run_command.call_args.args[0]
        assert "uv==1.2.3" in command
        assert "|" not in command

    def test_install_uv_windows(self, python_manager, monkeypatch):
        """Test installing uv on Windows."""
        monkeypatch.setattr(platform_module, "system", lambda: "Windows")
        monkeypatch.delenv("SYSTEMS_MANAGER_UV_VERSION", raising=False)
        result = python_manager.install_uv()
        assert result["success"] is False
        assert "pin an exact release" in result["error"]

    def test_create_venv(self, python_manager):
        """Test creating a virtual environment."""
        result = python_manager.create_venv("test_venv")
        assert "success" in result
        python_manager.manager.run_command.assert_called_once()

    def test_create_venv_with_python_version(self, python_manager):
        """Test creating a virtual environment with specific Python version."""
        result = python_manager.create_venv("test_venv", "3.11")
        assert "success" in result

    def test_install_package(self, python_manager):
        """Test installing a Python package."""
        result = python_manager.install_package("requests")
        assert "success" in result

    def test_install_package_with_venv(self, python_manager, monkeypatch, tmp_path):
        """Test installing a package in a specific virtual environment."""
        monkeypatch.setattr(platform_module, "system", lambda: "Linux")
        (tmp_path / "venv").mkdir()
        result = python_manager.install_package("requests", "venv")
        assert "success" in result


class TestNodeManager:
    """Tests for NodeManager class."""

    @pytest.fixture
    def node_manager(self, mock_logger):
        """Create a NodeManager instance for testing."""
        manager = Mock()
        manager.run_command = Mock(return_value={"success": True})
        return NodeManager(manager)

    def test_install_nvm_linux(self, node_manager, monkeypatch, tmp_path):
        """Test installing nvm on Linux."""
        monkeypatch.setattr(platform_module, "system", lambda: "Linux")
        monkeypatch.setenv("SYSTEMS_MANAGER_FILESYSTEM_ROOT", str(tmp_path))
        monkeypatch.setenv("SYSTEMS_MANAGER_NVM_COMMIT", "a" * 40)
        result = node_manager.install_nvm()
        assert result["success"] is True
        for call_args in node_manager.manager.run_command.call_args_list:
            assert "|" not in call_args.args[0]

    def test_install_nvm_windows(self, node_manager, monkeypatch):
        """Test installing nvm on Windows."""
        monkeypatch.setattr(platform_module, "system", lambda: "Windows")
        result = node_manager.install_nvm()
        assert result["success"] is False
        assert "not supported" in result["error"]

    def test_install_node(self, node_manager, monkeypatch, tmp_path):
        """Test installing Node.js."""
        monkeypatch.setenv("SYSTEMS_MANAGER_FILESYSTEM_ROOT", str(tmp_path))
        nvm = tmp_path / ".agent_data" / "nvm"
        nvm.mkdir(parents=True)
        (nvm / "nvm.sh").write_text("", encoding="utf-8")
        result = node_manager.install_node("--lts")
        assert "success" in result

    def test_install_node_specific_version(self, node_manager, monkeypatch, tmp_path):
        """Test installing specific Node.js version."""
        monkeypatch.setenv("SYSTEMS_MANAGER_FILESYSTEM_ROOT", str(tmp_path))
        nvm = tmp_path / ".agent_data" / "nvm"
        nvm.mkdir(parents=True)
        (nvm / "nvm.sh").write_text("", encoding="utf-8")
        result = node_manager.install_node("18.0.0")
        assert "success" in result

    def test_use_node(self, node_manager, monkeypatch, tmp_path):
        """Test switching Node.js version."""
        monkeypatch.setenv("SYSTEMS_MANAGER_FILESYSTEM_ROOT", str(tmp_path))
        nvm = tmp_path / ".agent_data" / "nvm"
        nvm.mkdir(parents=True)
        (nvm / "nvm.sh").write_text("", encoding="utf-8")
        result = node_manager.use_node("18.0.0")
        assert "success" in result


class TestSystemsManagerBase:
    """Tests for SystemsManagerBase abstract class."""

    @pytest.fixture
    def concrete_manager(self, mock_logger, monkeypatch, tmp_path):
        """Create a concrete implementation of SystemsManagerBase for testing."""

        monkeypatch.setenv("SYSTEMS_MANAGER_FILESYSTEM_ROOT", str(tmp_path))

        class ConcreteManager(SystemsManagerBase):
            def install_applications(self, apps):
                return {"success": True, "installed": apps}

            def update(self):
                return {"success": True}

            def clean(self):
                return {"success": True}

            def optimize(self):
                return {"success": True}

            def install_snapd(self):
                return {"success": True}

            def add_repository(self, repo_url, name=None):
                return {"success": True}

            def install_local_package(self, file_path):
                return {"success": True}

            def search_package(self, query):
                return {"success": True, "packages": []}

            def get_package_info(self, package):
                return {"success": True, "info": ""}

            def list_installed_packages(self):
                return {"success": True, "packages": []}

            def list_upgradable_packages(self):
                return {"success": True, "packages": []}

            def clean_package_cache(self):
                return {"success": True}

        return ConcreteManager(silent=True)

    def test_initialization(self, concrete_manager):
        """Test manager initialization."""
        assert concrete_manager.silent is True
        assert concrete_manager.logger is not None
        assert concrete_manager.fs_manager is not None
        assert concrete_manager.python_manager is not None
        assert concrete_manager.node_manager is not None

    def test_log_command(self, concrete_manager):
        """Test command logging."""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "test output"
        mock_result.stderr = ""
        concrete_manager.log_command(["echo", "test"], mock_result)
        # Just verify it doesn't crash
        assert concrete_manager.logger is not None

    def test_log_command_with_error(self, concrete_manager):
        """Test command logging with error."""
        error = Exception("Test error")
        concrete_manager.log_command(["echo", "test"], error=error)
        # Just verify it doesn't crash
        assert concrete_manager.logger is not None

    def test_install_python_modules_success(self, concrete_manager, monkeypatch):
        """Test successful Python module installation."""

        def mock_run(*args, **kwargs):
            result = Mock()
            result.returncode = 0
            result.stdout = "success"
            result.stderr = ""
            return result

        monkeypatch.setattr("subprocess.run", mock_run)
        result = concrete_manager.install_python_modules(["requests", "pytest"])
        assert result["success"] is True
        assert len(result["installed"]) == 2
        assert result["upgraded_pip"] is False

    def test_install_python_modules_partial_failure(self, concrete_manager):
        """Test Python module installation with partial failures."""

        # Mock run_command to return failure for module install
        def mock_run(cmd, **kwargs):
            if "pip" in cmd and "install" in cmd and "upgrade" in cmd:
                return {"success": True, "returncode": 0, "stdout": "", "stderr": ""}
            else:
                return {
                    "success": False,
                    "returncode": 1,
                    "stdout": "",
                    "stderr": "error",
                }

        concrete_manager.run_command = mock_run
        result = concrete_manager.install_python_modules(["nonexistent"])
        assert result["success"] is False
        assert len(result["failed"]) == 1

    def test_get_os_statistics(self, concrete_manager):
        """Test getting OS statistics."""
        stats = concrete_manager.get_os_statistics()
        assert "system" in stats
        assert "release" in stats
        assert "version" in stats
        assert "machine" in stats

    def test_get_hardware_statistics(self, concrete_manager, monkeypatch):
        """Test getting hardware statistics."""
        mock_cpu = Mock(return_value=45.2)
        mock_memory = Mock()
        mock_memory.total = 16000000000
        mock_memory.available = 8000000000
        mock_memory.percent = 50.0
        mock_memory.used = 8000000000
        mock_memory.free = 8000000000
        mock_memory._asdict = Mock(
            return_value={
                "total": 16000000000,
                "available": 8000000000,
                "percent": 50.0,
            }
        )

        mock_disk = Mock()
        mock_disk.total = 500000000000
        mock_disk.used = 250000000000
        mock_disk.free = 250000000000
        mock_disk.percent = 50.0
        mock_disk._asdict = Mock(
            return_value={
                "total": 500000000000,
                "used": 250000000000,
                "free": 250000000000,
                "percent": 50.0,
            }
        )

        mock_net = Mock()
        mock_net._asdict = Mock(return_value={"bytes_sent": 1000, "bytes_recv": 2000})

        monkeypatch.setattr("psutil.cpu_percent", mock_cpu)
        monkeypatch.setattr("psutil.cpu_count", Mock(return_value=4))
        monkeypatch.setattr("psutil.virtual_memory", Mock(return_value=mock_memory))
        monkeypatch.setattr("psutil.disk_usage", Mock(return_value=mock_disk))
        monkeypatch.setattr("psutil.net_io_counters", Mock(return_value=mock_net))

        stats = concrete_manager.get_hardware_statistics()
        assert "cpu_percent" in stats
        assert "cpu_count" in stats
        assert "memory" in stats
        assert "disk_usage" in stats
        assert "network" in stats

    def test_list_services_linux(self, concrete_manager, monkeypatch):
        """Test listing services on Linux."""
        monkeypatch.setattr(platform_module, "system", lambda: "Linux")

        concrete_manager.run_command = Mock(
            return_value={
                "success": True,
                "stdout": "ssh.service loaded active running OpenSSH server\nnginx.service loaded active running Web server",
            }
        )

        result = concrete_manager.list_services()
        assert result["success"] is True
        assert len(result["services"]) == 2

    def test_list_services_linux_failure(self, concrete_manager, monkeypatch):
        """Test listing services on Linux with failure."""
        monkeypatch.setattr(platform_module, "system", lambda: "Linux")

        concrete_manager.run_command = Mock(
            return_value={"success": False, "error": "Command failed"}
        )

        result = concrete_manager.list_services()
        assert result["success"] is False

    def test_list_services_windows(self, concrete_manager, monkeypatch):
        """Test listing services on Windows."""
        monkeypatch.setattr(platform_module, "system", lambda: "Windows")

        concrete_manager.run_command = Mock(
            return_value={
                "success": True,
                "stdout": json.dumps(
                    [{"Name": "ssh", "Status": "Running", "DisplayName": "OpenSSH"}]
                ),
            }
        )

        result = concrete_manager.list_services()
        assert result["success"] is True
        assert len(result["services"]) == 1

    def test_list_services_windows_json_error(self, concrete_manager, monkeypatch):
        """Test listing services on Windows with JSON parse error."""
        monkeypatch.setattr(platform_module, "system", lambda: "Windows")

        concrete_manager.run_command = Mock(
            return_value={"success": True, "stdout": "invalid json"}
        )

        result = concrete_manager.list_services()
        assert result["success"] is False
        assert "parse" in result["error"]

    def test_list_services_unsupported_os(self, concrete_manager, monkeypatch):
        """Test listing services on unsupported OS."""
        monkeypatch.setattr(platform_module, "system", lambda: "Darwin")

        result = concrete_manager.list_services()
        assert result["success"] is False
        assert "Unsupported OS" in result["error"]

    def test_get_service_status_linux(self, concrete_manager, monkeypatch):
        """Test getting service status on Linux."""
        monkeypatch.setattr(platform_module, "system", lambda: "Linux")

        concrete_manager.run_command = Mock(
            return_value={
                "success": True,
                "stdout": "ssh.service - OpenSSH server\nLoaded: loaded\nActive: active (running)",
                "returncode": 0,
            }
        )

        result = concrete_manager.get_service_status("ssh")
        assert result["success"] is True
        assert result["service"] == "ssh"

    def test_get_service_status_windows(self, concrete_manager, monkeypatch):
        """Test getting service status on Windows."""
        monkeypatch.setattr(platform_module, "system", lambda: "Windows")

        concrete_manager.run_command = Mock(
            return_value={
                "success": True,
                "stdout": json.dumps({"Name": "ssh", "Status": "Running"}),
            }
        )

        result = concrete_manager.get_service_status("ssh")
        assert result["success"] is True

    def test_start_service_linux(self, concrete_manager, monkeypatch):
        """Test starting a service on Linux."""
        monkeypatch.setattr(platform_module, "system", lambda: "Linux")

        concrete_manager.run_command = Mock(return_value={"success": True})

        result = concrete_manager.start_service("ssh")
        assert result["success"] is True

    def test_start_service_windows(self, concrete_manager, monkeypatch):
        """Test starting a service on Windows."""
        monkeypatch.setattr(platform_module, "system", lambda: "Windows")

        concrete_manager.run_command = Mock(return_value={"success": True})

        result = concrete_manager.start_service("ssh")
        assert result["success"] is True

    def test_stop_service_linux(self, concrete_manager, monkeypatch):
        """Test stopping a service on Linux."""
        monkeypatch.setattr(platform_module, "system", lambda: "Linux")

        concrete_manager.run_command = Mock(return_value={"success": True})

        result = concrete_manager.stop_service("ssh")
        assert result["success"] is True

    def test_stop_service_windows(self, concrete_manager, monkeypatch):
        """Test stopping a service on Windows."""
        monkeypatch.setattr(platform_module, "system", lambda: "Windows")

        concrete_manager.run_command = Mock(return_value={"success": True})

        result = concrete_manager.stop_service("ssh")
        assert result["success"] is True

    def test_restart_service_linux(self, concrete_manager, monkeypatch):
        """Test restarting a service on Linux."""
        monkeypatch.setattr(platform_module, "system", lambda: "Linux")

        concrete_manager.run_command = Mock(return_value={"success": True})
        # Add winget_bin attribute to avoid AttributeError
        concrete_manager.winget_bin = "/usr/bin/winget"

        result = concrete_manager.restart_service("ssh")
        assert result["success"] is True

    def test_restart_service_windows(self, concrete_manager, monkeypatch):
        """Test restarting a service on Windows."""
        monkeypatch.setattr(platform_module, "system", lambda: "Windows")

        concrete_manager.run_command = Mock(return_value={"success": True})
        # Add winget_bin attribute to avoid AttributeError
        concrete_manager.winget_bin = "/usr/bin/winget"

        result = concrete_manager.restart_service("ssh")
        assert result["success"] is True

    def test_enable_service_linux(self, concrete_manager, monkeypatch):
        """Test enabling a service on Linux."""
        monkeypatch.setattr(platform_module, "system", lambda: "Linux")

        concrete_manager.run_command = Mock(return_value={"success": True})

        result = concrete_manager.enable_service("ssh")
        assert result["success"] is True

    def test_enable_service_windows(self, concrete_manager, monkeypatch):
        """Test enabling a service on Windows."""
        monkeypatch.setattr(platform_module, "system", lambda: "Windows")

        concrete_manager.run_command = Mock(return_value={"success": True})

        result = concrete_manager.enable_service("ssh")
        assert result["success"] is True

    def test_disable_service_linux(self, concrete_manager, monkeypatch):
        """Test disabling a service on Linux."""
        monkeypatch.setattr(platform_module, "system", lambda: "Linux")

        concrete_manager.run_command = Mock(return_value={"success": True})

        result = concrete_manager.disable_service("ssh")
        assert result["success"] is True

    def test_disable_service_windows(self, concrete_manager, monkeypatch):
        """Test disabling a service on Windows."""
        monkeypatch.setattr(platform_module, "system", lambda: "Windows")

        concrete_manager.run_command = Mock(return_value={"success": True})

        result = concrete_manager.disable_service("ssh")
        assert result["success"] is True

    def test_list_processes(self, concrete_manager, monkeypatch):
        """Test listing processes."""
        mock_proc = Mock()
        mock_proc.info = {
            "pid": 1,
            "name": "test",
            "username": "user",
            "cpu_percent": 1.0,
            "memory_percent": 2.0,
            "status": "running",
        }

        monkeypatch.setattr("psutil.process_iter", Mock(return_value=[mock_proc]))

        result = concrete_manager.list_processes()
        assert result["success"] is True
        assert len(result["processes"]) == 1

    def test_list_processes_access_denied(self, concrete_manager, monkeypatch):
        """Test listing processes with access denied."""

        def mock_iter(*args, **kwargs):
            raise psutil.AccessDenied(1)

        monkeypatch.setattr("psutil.process_iter", mock_iter)

        result = concrete_manager.list_processes()
        assert result["success"] is False

    def test_get_process_info(self, concrete_manager, monkeypatch):
        """Test getting process info."""
        mock_proc = Mock()
        mock_proc.pid = 1
        mock_proc.name = Mock(return_value="test")
        mock_proc.status = Mock(return_value="running")
        mock_proc.username = Mock(return_value="user")
        mock_proc.cpu_percent = Mock(return_value=1.0)
        mock_proc.memory_percent = Mock(return_value=2.0)
        mock_proc.memory_info = Mock()
        mock_proc.memory_info._asdict = Mock(return_value={})
        mock_proc.create_time = Mock(return_value=1234567890)
        mock_proc.cmdline = Mock(return_value=["test"])
        mock_proc.num_threads = Mock(return_value=1)

        # Make oneshot a context manager
        mock_proc.oneshot = Mock(return_value=mock_proc)
        mock_proc.__enter__ = Mock(return_value=mock_proc)
        mock_proc.__exit__ = Mock(return_value=False)

        def mock_process(pid):
            return mock_proc

        monkeypatch.setattr("psutil.Process", mock_process)

        result = concrete_manager.get_process_info(1)
        assert result["success"] is True
        assert result["process"]["pid"] == 1

    def test_get_process_info_no_such_process(self, concrete_manager, monkeypatch):
        """Test getting process info for non-existent process."""

        def mock_process(pid):
            raise psutil.NoSuchProcess(1)

        monkeypatch.setattr("psutil.Process", mock_process)

        result = concrete_manager.get_process_info(99999)
        assert result["success"] is False
        assert result["error"] == "Process was not found"

    def test_get_process_info_access_denied(self, concrete_manager, monkeypatch):
        """Test getting process info with access denied."""

        def mock_process(pid):
            raise psutil.AccessDenied(1)

        monkeypatch.setattr("psutil.Process", mock_process)

        result = concrete_manager.get_process_info(1)
        assert result["success"] is False
        assert result["error"] == "Process access was denied"

    def test_kill_process(self, concrete_manager, monkeypatch):
        """Test killing a process."""
        mock_proc = Mock()
        mock_proc.name = Mock(return_value="test")
        mock_proc.kill = Mock()
        mock_proc.terminate = Mock()

        def mock_process(pid):
            return mock_proc

        monkeypatch.setattr("psutil.Process", mock_process)

        result = concrete_manager.kill_process(23456, signal=9)
        assert result["success"] is True

    def test_kill_process_no_such_process(self, concrete_manager, monkeypatch):
        """Test killing a non-existent process."""

        def mock_process(pid):
            raise psutil.NoSuchProcess(1)

        monkeypatch.setattr("psutil.Process", mock_process)

        result = concrete_manager.kill_process(99999)
        assert result["success"] is False

    def test_list_network_interfaces(self, concrete_manager, monkeypatch):
        """Test listing network interfaces."""
        mock_addr = {
            "eth0": [Mock(address="192.0.2.1", netmask="255.255.255.0", broadcast=None)]
        }
        mock_stats = {"eth0": Mock(isup=True, speed=1000, mtu=1500)}

        monkeypatch.setattr("psutil.net_if_addrs", Mock(return_value=mock_addr))
        monkeypatch.setattr("psutil.net_if_stats", Mock(return_value=mock_stats))

        result = concrete_manager.list_network_interfaces()
        assert result["success"] is True
        assert "interfaces" in result

    def test_list_open_ports(self, concrete_manager, monkeypatch):
        """Test listing open ports."""
        mock_conn = Mock()
        mock_conn.status = "LISTEN"
        mock_conn.laddr = Mock(ip="0.0.0.0", port=22)
        mock_conn.pid = 1

        monkeypatch.setattr("psutil.net_connections", Mock(return_value=[mock_conn]))

        result = concrete_manager.list_open_ports()
        assert result["success"] is True
        assert len(result["ports"]) == 1

    def test_list_open_ports_access_denied(self, concrete_manager, monkeypatch):
        """Test listing open ports with access denied."""

        def mock_connections(*args, **kwargs):
            raise psutil.AccessDenied(1)

        monkeypatch.setattr("psutil.net_connections", mock_connections)
        concrete_manager.run_command = Mock(
            return_value={"success": True, "stdout": ""}
        )

        result = concrete_manager.list_open_ports()
        assert result["success"] is True

    def test_ping_host(self, concrete_manager, monkeypatch):
        """Test pinging a host."""
        concrete_manager.run_command = Mock(
            return_value={"success": True, "stdout": "pong"}
        )

        result = concrete_manager.ping_host("example.com")
        assert result["success"] is True
        assert result["host_ref"].startswith("host:")
        assert "host" not in result

    def test_ping_host_windows(self, concrete_manager, monkeypatch):
        """Test pinging a host on Windows."""
        monkeypatch.setattr(platform_module, "system", lambda: "Windows")
        concrete_manager.run_command = Mock(
            return_value={"success": True, "stdout": "pong"}
        )

        result = concrete_manager.ping_host("example.com")
        assert result["success"] is True

    def test_dns_lookup_success(self, concrete_manager):
        """Test successful DNS lookup."""
        result = concrete_manager.dns_lookup("localhost")
        assert result["success"] is True
        assert "address_refs" in result
        assert "hostname_ref" in result
        assert "addresses" not in result

    def test_dns_lookup_failure(self, concrete_manager):
        """Test failed DNS lookup."""
        result = concrete_manager.dns_lookup("nonexistent.invalid")
        assert result["success"] is False
        assert "DNS lookup failed" in result["error"]

    def test_list_disks(self, concrete_manager, monkeypatch):
        """Test listing disks."""
        mock_part = Mock()
        mock_part.device = "/dev/sda1"
        mock_part.mountpoint = "/"
        mock_part.fstype = "ext4"
        mock_part.opts = "rw"

        mock_usage = Mock()
        mock_usage.total = 500000000000
        mock_usage.used = 250000000000
        mock_usage.free = 250000000000
        mock_usage.percent = 50.0

        monkeypatch.setattr("psutil.disk_partitions", Mock(return_value=[mock_part]))
        monkeypatch.setattr("psutil.disk_usage", Mock(return_value=mock_usage))

        result = concrete_manager.list_disks()
        assert result["success"] is True
        assert len(result["disks"]) == 1

    def test_list_disks_permission_error(self, concrete_manager, monkeypatch):
        """Test listing disks with permission error."""
        mock_part = Mock()
        mock_part.device = "/dev/sda1"
        mock_part.mountpoint = "/"
        mock_part.fstype = "ext4"
        mock_part.opts = "rw"

        def mock_usage(path):
            raise PermissionError()

        monkeypatch.setattr("psutil.disk_partitions", Mock(return_value=[mock_part]))
        monkeypatch.setattr("psutil.disk_usage", mock_usage)

        result = concrete_manager.list_disks()
        assert result["success"] is True
        assert len(result["disks"]) == 1

    def test_get_disk_usage(self, concrete_manager, monkeypatch):
        """Test getting disk usage."""
        mock_usage = Mock()
        mock_usage.total = 500000000000
        mock_usage.used = 250000000000
        mock_usage.free = 250000000000
        mock_usage.percent = 50.0

        monkeypatch.setattr("psutil.disk_usage", Mock(return_value=mock_usage))

        result = concrete_manager.get_disk_usage(".")
        assert result["success"] is True
        assert result["total"] == 500000000000

    def test_list_users_linux(self, concrete_manager, monkeypatch, tmp_path):
        """Test listing users on Linux."""
        monkeypatch.setattr(platform_module, "system", lambda: "Linux")

        passwd_content = """root:x:0:0:root:/root:/bin/bash
user:x:1000:1000:User:/home/user:/bin/bash"""
        passwd_file = tmp_path / "passwd"
        passwd_file.write_text(passwd_content)

        with patch("builtins.open", mock_open(read_data=passwd_content)):
            result = concrete_manager.list_users()
            assert result["success"] is True
            assert len(result["users"]) == 2

    def test_list_users_windows(self, concrete_manager, monkeypatch):
        """Test listing users on Windows."""
        monkeypatch.setattr(platform_module, "system", lambda: "Windows")

        concrete_manager.run_command = Mock(
            return_value={
                "success": True,
                "stdout": json.dumps([{"Name": "user", "Enabled": True}]),
            }
        )

        result = concrete_manager.list_users()
        assert result["success"] is True

    def test_list_groups_linux(self, concrete_manager, monkeypatch, tmp_path):
        """Test listing groups on Linux."""
        monkeypatch.setattr(platform_module, "system", lambda: "Linux")

        group_content = """root:x:0:
user:x:1000:user"""
        with patch("builtins.open", mock_open(read_data=group_content)):
            result = concrete_manager.list_groups()
            assert result["success"] is True
            assert len(result["groups"]) == 2

    def test_list_groups_windows(self, concrete_manager, monkeypatch):
        """Test listing groups on Windows."""
        monkeypatch.setattr(platform_module, "system", lambda: "Windows")

        concrete_manager.run_command = Mock(
            return_value={"success": True, "stdout": json.dumps([{"Name": "Users"}])}
        )

        result = concrete_manager.list_groups()
        assert result["success"] is True

    def test_get_system_logs_linux(self, concrete_manager, monkeypatch):
        """Test getting system logs on Linux."""
        monkeypatch.setattr(platform_module, "system", lambda: "Linux")

        concrete_manager.run_command = Mock(
            return_value={"success": True, "stdout": "log line 1\nlog line 2"}
        )

        result = concrete_manager.get_system_logs()
        assert result["success"] is True
        assert "logs" in result

    def test_get_system_logs_linux_with_unit(self, concrete_manager, monkeypatch):
        """Test getting system logs on Linux with unit filter."""
        monkeypatch.setattr(platform_module, "system", lambda: "Linux")

        concrete_manager.run_command = Mock(
            return_value={"success": True, "stdout": "log line 1\nlog line 2"}
        )

        result = concrete_manager.get_system_logs(unit="ssh")
        assert result["success"] is True

    def test_get_system_logs_windows(self, concrete_manager, monkeypatch):
        """Test getting system logs on Windows."""
        monkeypatch.setattr(platform_module, "system", lambda: "Windows")

        concrete_manager.run_command = Mock(
            return_value={"success": True, "stdout": "log output"}
        )

        result = concrete_manager.get_system_logs()
        assert result["success"] is True

    def test_tail_log_file(self, concrete_manager, tmp_path):
        """Test tailing a log file."""
        log_file = tmp_path / "test.log"
        log_file.write_text("line 1\nline 2\nline 3\n")

        result = concrete_manager.tail_log_file(str(log_file))
        assert result["success"] is True
        assert result["lines"] == 3

    def test_tail_log_file_nonexistent(self, concrete_manager):
        """Test tailing a non-existent log file."""
        result = concrete_manager.tail_log_file("/nonexistent.log")
        assert result["success"] is False
        assert result["error"] == "Operation failed"

    def test_tail_log_file_with_lines_limit(self, concrete_manager, tmp_path):
        """Test tailing a log file with line limit."""
        log_file = tmp_path / "test.log"
        log_file.write_text("line 1\nline 2\nline 3\nline 4\nline 5\n")

        result = concrete_manager.tail_log_file(str(log_file), lines=2)
        assert result["success"] is True
        assert result["lines"] == 2

    def test_system_health_check(self, concrete_manager, monkeypatch):
        """Test system health check."""
        monkeypatch.setattr("psutil.boot_time", Mock(return_value=1234567890))
        monkeypatch.setattr("psutil.cpu_percent", Mock(return_value=45.0))

        mock_memory = Mock()
        mock_memory.percent = 50.0
        mock_memory.available = 8000000000
        monkeypatch.setattr("psutil.virtual_memory", Mock(return_value=mock_memory))

        mock_swap = Mock()
        mock_swap.percent = 30.0
        monkeypatch.setattr("psutil.swap_memory", Mock(return_value=mock_swap))

        mock_part = Mock()
        mock_part.mountpoint = "/"
        monkeypatch.setattr("psutil.disk_partitions", Mock(return_value=[mock_part]))

        mock_usage = Mock()
        mock_usage.percent = 80.0
        mock_usage.free = 100000000000
        monkeypatch.setattr("psutil.disk_usage", Mock(return_value=mock_usage))

        mock_proc = Mock()
        mock_proc.info = {
            "pid": 1,
            "name": "test",
            "cpu_percent": 1.0,
            "memory_percent": 2.0,
        }
        monkeypatch.setattr("psutil.process_iter", Mock(return_value=[mock_proc]))

        result = concrete_manager.system_health_check()
        assert result["success"] is True
        assert "status" in result
        assert "uptime_seconds" in result

    def test_get_uptime(self, concrete_manager, monkeypatch):
        """Test getting system uptime."""
        monkeypatch.setattr("psutil.boot_time", Mock(return_value=1234567890))

        result = concrete_manager.get_uptime()
        assert result["success"] is True
        assert "uptime_seconds" in result
        assert "boot_time" in result

    def test_list_cron_jobs_linux(self, concrete_manager, monkeypatch):
        """Test listing cron jobs on Linux."""
        monkeypatch.setattr(platform_module, "system", lambda: "Linux")

        concrete_manager.run_command = Mock(
            return_value={"success": True, "stdout": "# comment\n* * * * * command\n"}
        )

        result = concrete_manager.list_cron_jobs()
        assert result["success"] is True
        assert len(result["jobs"]) == 1

    def test_list_cron_jobs_linux_with_user(self, concrete_manager, monkeypatch):
        """Test listing cron jobs on Linux with user."""
        monkeypatch.setattr(platform_module, "system", lambda: "Linux")

        concrete_manager.run_command = Mock(
            return_value={"success": True, "stdout": "* * * * * command\n"}
        )

        result = concrete_manager.list_cron_jobs(user="root")
        assert result["success"] is True

    def test_list_cron_jobs_windows(self, concrete_manager, monkeypatch):
        """Test listing cron jobs on Windows."""
        monkeypatch.setattr(platform_module, "system", lambda: "Windows")

        concrete_manager.run_command = Mock(
            return_value={"success": True, "stdout": "task output"}
        )

        result = concrete_manager.list_cron_jobs()
        assert result["success"] is True

    def test_remove_cron_job_linux(self, concrete_manager, monkeypatch):
        """Test removing a cron job on Linux."""
        monkeypatch.setattr(platform_module, "system", lambda: "Linux")

        concrete_manager.run_command = Mock(
            return_value={"success": True, "stdout": "* * * * * echo test\n"}
        )
        job_ref = concrete_manager.list_cron_jobs()["jobs"][0]["job_ref"]
        result = concrete_manager.remove_cron_job(job_ref)
        assert result["success"] is True

    def test_remove_cron_job_not_found(self, concrete_manager, monkeypatch):
        """Test removing a cron job that doesn't exist."""
        monkeypatch.setattr(platform_module, "system", lambda: "Linux")

        concrete_manager.run_command = Mock(
            return_value={"success": True, "stdout": "* * * * * other command\n"}
        )

        result = concrete_manager.remove_cron_job("cron:" + "0" * 16)
        assert result["success"] is False
        assert result["error"] == "Cron job reference was not found"

    def test_get_firewall_status_linux_ufw(self, concrete_manager, monkeypatch):
        """Test getting firewall status on Linux with ufw."""
        monkeypatch.setattr(platform_module, "system", lambda: "Linux")
        monkeypatch.setattr("shutil.which", Mock(return_value="/usr/sbin/ufw"))

        concrete_manager.run_command = Mock(
            return_value={"success": True, "stdout": "Status: active"}
        )

        result = concrete_manager.get_firewall_status()
        assert result["success"] is True
        assert result["tool"] == "ufw"

    def test_get_firewall_status_linux_firewalld(self, concrete_manager, monkeypatch):
        """Test getting firewall status on Linux with firewalld."""
        monkeypatch.setattr(platform_module, "system", lambda: "Linux")
        monkeypatch.setattr(
            "shutil.which", Mock(side_effect=lambda x: x == "firewall-cmd")
        )

        concrete_manager.run_command = Mock(
            return_value={"success": True, "stdout": "running"}
        )

        result = concrete_manager.get_firewall_status()
        assert result["success"] is True
        assert result["tool"] == "firewalld"

    def test_get_firewall_status_linux_iptables(self, concrete_manager, monkeypatch):
        """Test getting firewall status on Linux with iptables."""
        monkeypatch.setattr(platform_module, "system", lambda: "Linux")
        monkeypatch.setattr("shutil.which", Mock(return_value=None))

        concrete_manager.run_command = Mock(
            return_value={"success": True, "stdout": "Chain INPUT"}
        )

        result = concrete_manager.get_firewall_status()
        assert result["success"] is True
        assert result["tool"] == "iptables"

    def test_get_firewall_status_windows(self, concrete_manager, monkeypatch):
        """Test getting firewall status on Windows."""
        monkeypatch.setattr(platform_module, "system", lambda: "Windows")

        concrete_manager.run_command = Mock(
            return_value={"success": True, "stdout": "Domain Profile"}
        )

        result = concrete_manager.get_firewall_status()
        assert result["success"] is True
        assert result["tool"] == "netsh"

    def test_list_firewall_rules_linux(self, concrete_manager, monkeypatch):
        """Test listing firewall rules on Linux."""
        monkeypatch.setattr(platform_module, "system", lambda: "Linux")
        monkeypatch.setattr("shutil.which", Mock(return_value="/usr/sbin/ufw"))

        concrete_manager.run_command = Mock(
            return_value={"success": True, "stdout": "1: ALLOW"}
        )

        result = concrete_manager.list_firewall_rules()
        assert result["success"] is True
        assert result["tool"] == "ufw"

    def test_list_firewall_rules_windows(self, concrete_manager, monkeypatch):
        """Test listing firewall rules on Windows."""
        monkeypatch.setattr(platform_module, "system", lambda: "Windows")

        concrete_manager.run_command = Mock(
            return_value={"success": True, "stdout": json.dumps([{"Name": "rule1"}])}
        )

        result = concrete_manager.list_firewall_rules()
        assert result["success"] is True
        assert result["total"] == 1
        assert result["details_redacted"] is True

    def test_add_firewall_rule_linux(self, concrete_manager, monkeypatch):
        """Test adding a firewall rule on Linux."""
        monkeypatch.setattr(platform_module, "system", lambda: "Linux")
        monkeypatch.setattr("shutil.which", Mock(return_value="/usr/sbin/ufw"))

        concrete_manager.run_command = Mock(return_value={"success": True})

        result = concrete_manager.add_firewall_rule(
            {
                "name": "ssh",
                "action": "allow",
                "protocol": "tcp",
                "port": 22,
            }
        )
        assert result["success"] is True
        assert result["tool"] == "ufw"

    def test_add_firewall_rule_windows(self, concrete_manager, monkeypatch):
        """Test adding a firewall rule on Windows."""
        monkeypatch.setattr(platform_module, "system", lambda: "Windows")

        concrete_manager.run_command = Mock(return_value={"success": True})

        result = concrete_manager.add_firewall_rule(
            {
                "name": "ssh",
                "action": "allow",
                "protocol": "tcp",
                "port": 22,
            }
        )
        assert result["success"] is True
        assert result["tool"] == "netsh"

    def test_remove_firewall_rule_linux(self, concrete_manager, monkeypatch):
        """Test removing a firewall rule on Linux."""
        monkeypatch.setattr(platform_module, "system", lambda: "Linux")
        monkeypatch.setattr("shutil.which", Mock(return_value="/usr/sbin/ufw"))

        concrete_manager.run_command = Mock(return_value={"success": True})

        result = concrete_manager.remove_firewall_rule(
            {
                "name": "ssh",
                "action": "allow",
                "protocol": "tcp",
                "port": 22,
            }
        )
        assert result["success"] is True
        assert result["tool"] == "ufw"

    def test_list_ssh_keys(self, concrete_manager, temp_home):
        """Test listing SSH keys."""
        ssh_dir = temp_home / ".ssh"
        ssh_dir.mkdir()
        (ssh_dir / "id_rsa").write_text("private key")
        (ssh_dir / "id_rsa.pub").write_text("public key")

        result = concrete_manager.list_ssh_keys()
        assert result["success"] is True
        assert len(result["keys"]) == 2
        assert all(
            "path" not in item and "filename" not in item for item in result["keys"]
        )

    def test_list_ssh_keys_no_directory(self, concrete_manager, temp_home):
        """Test listing SSH keys when .ssh directory doesn't exist."""
        result = concrete_manager.list_ssh_keys()
        assert result["success"] is True
        assert len(result["keys"]) == 0

    def test_generate_ssh_key(self, concrete_manager, temp_home, monkeypatch):
        """Test generating SSH key."""
        monkeypatch.setattr(platform_module, "system", lambda: "Linux")

        concrete_manager.run_command = Mock(return_value={"success": True})

        result = concrete_manager.generate_ssh_key("ed25519", "test", "")
        assert result["success"] is True

    def test_generate_ssh_key_exists(self, concrete_manager, temp_home):
        """Test generating SSH key when key already exists."""
        ssh_dir = temp_home / ".ssh"
        ssh_dir.mkdir()
        (ssh_dir / "id_ed25519").write_text("key")

        result = concrete_manager.generate_ssh_key("ed25519")
        assert result["success"] is False
        assert "already exists" in result["error"]

    def test_add_authorized_key(self, concrete_manager, temp_home):
        """Test adding authorized key."""
        ssh_dir = temp_home / ".ssh"
        ssh_dir.mkdir()

        public_key = "ssh-ed25519 " + base64.b64encode(b"x" * 32).decode()
        result = concrete_manager.add_authorized_key(public_key)
        assert result["success"] is True
        auth_keys = ssh_dir / "authorized_keys"
        assert auth_keys.exists()

    def test_add_authorized_key_exists(self, concrete_manager, temp_home):
        """Test adding authorized key that already exists."""
        ssh_dir = temp_home / ".ssh"
        ssh_dir.mkdir()
        auth_keys = ssh_dir / "authorized_keys"
        public_key = "ssh-ed25519 " + base64.b64encode(b"x" * 32).decode()
        auth_keys.write_text(public_key + "\n")

        result = concrete_manager.add_authorized_key(public_key)
        assert result["success"] is True
        assert "already exists" in result["message"]

    def test_list_env_vars(self, concrete_manager, monkeypatch):
        """Test listing environment variables."""
        monkeypatch.setenv("TEST_VAR", "test_value")

        result = concrete_manager.list_env_vars()
        assert result["success"] is True
        assert "TEST_VAR" in result["variables"]
        assert "test_value" not in repr(result)
        assert result["values_redacted"] is True

    def test_get_env_var(self, concrete_manager, monkeypatch):
        """Test getting environment variable."""
        monkeypatch.setenv("TEST_VAR", "test_value")
        monkeypatch.setenv("SYSTEMS_MANAGER_ENV_METADATA_ALLOWLIST", "TEST_VAR")

        result = concrete_manager.get_env_var("TEST_VAR")
        assert result["success"] is True
        assert result["configured"] is True
        assert "test_value" not in repr(result)

    def test_get_env_var_not_found(self, concrete_manager, monkeypatch):
        """Test getting non-existent environment variable."""
        monkeypatch.delenv("NONEXISTENT_VAR", raising=False)

        result = concrete_manager.get_env_var("NONEXISTENT_VAR")
        assert result["success"] is False
        assert "not allowlisted" in result["error"]

    def test_clean_temp_files(self, concrete_manager, tmp_path, monkeypatch):
        """Test cleaning temporary files."""
        temp_dir = tmp_path / "temp_test"
        temp_dir.mkdir()
        (temp_dir / "test.txt").write_text("content")
        monkeypatch.setenv("SYSTEMS_MANAGER_TEMP_ROOT", "temp_test")

        result = concrete_manager.clean_temp_files()
        assert result["success"] is True
        assert result["cleaned"] == 1

    def test_get_disk_space_report_linux(self, concrete_manager, monkeypatch):
        """Test getting disk space report on Linux."""
        monkeypatch.setattr(platform_module, "system", lambda: "Linux")
        root = Path(os.environ["SYSTEMS_MANAGER_FILESYSTEM_ROOT"])
        (root / "one").mkdir()
        (root / "one" / "data.bin").write_bytes(b"1")
        result = concrete_manager.get_disk_space_report(".")
        assert result["success"] is True
        assert "entries" in result

    def test_get_disk_space_report_windows(self, concrete_manager, monkeypatch):
        """Test getting disk space report on Windows."""
        monkeypatch.setattr(platform_module, "system", lambda: "Windows")
        root = Path(os.environ["SYSTEMS_MANAGER_FILESYSTEM_ROOT"])
        (root / "two").mkdir()
        result = concrete_manager.get_disk_space_report(".")
        assert result["success"] is True
        assert "entries" in result

    def test_install_via_snap_snap_exists(self, concrete_manager, monkeypatch):
        """Test installing via snap when snap exists."""
        monkeypatch.setattr("shutil.which", Mock(return_value="/usr/bin/snap"))

        concrete_manager.run_command = Mock(return_value={"success": True})

        result = concrete_manager.install_via_snap("test-app")
        assert result["success"] is True

    def test_install_via_snap_install_snapd(self, concrete_manager, monkeypatch):
        """Test that snapd is never bootstrapped as a hidden side effect."""
        monkeypatch.setattr("shutil.which", Mock(return_value=None))

        concrete_manager.run_command = Mock(return_value={"success": True})

        result = concrete_manager.install_via_snap("test-app")
        assert result["success"] is False
        assert result["prerequisite"] == "snapd"
        concrete_manager.run_command.assert_not_called()
