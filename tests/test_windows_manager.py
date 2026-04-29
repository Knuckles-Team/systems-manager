"""Tests for WindowsManager class."""

import json
from unittest.mock import Mock, patch
import pytest
from systems_manager.systems_manager import WindowsManager


class TestWindowsManager:
    """Tests for WindowsManager class."""

    @pytest.fixture
    def windows_manager(self, _mock_windows_platform, tmp_path):
        """Create a WindowsManager instance for testing."""
        # Mock the winget path
        winget_path = tmp_path / "WindowsApps" / "winget.exe"
        winget_path.parent.mkdir(parents=True)
        winget_path.write_text("fake winget")

        with patch("os.path.exists", return_value=True):
            manager = WindowsManager(silent=True)
            manager.winget_bin = str(winget_path)
            return manager

    @pytest.fixture
    def windows_manager_no_winget(self, _mock_windows_platform, tmp_path):
        """Create a WindowsManager instance without winget installed."""
        with patch("os.path.exists", return_value=False):
            manager = WindowsManager(silent=True)
            return manager

    def test_initialization_with_winget(self, windows_manager):
        """Test WindowsManager initialization with winget present."""
        assert windows_manager.silent is True
        assert "winget" in windows_manager.winget_bin

    def test_initialization_without_winget(self, windows_manager_no_winget):
        """Test WindowsManager initialization without winget."""
        assert windows_manager_no_winget.silent is True
        # Should attempt to install winget

    def test_install_applications_success(self, windows_manager):
        """Test successful application installation."""
        windows_manager.run_command = Mock(return_value={"success": True})

        result = windows_manager.install_applications(
            ["Microsoft.VisualStudioCode", "Git.Git"]
        )
        assert result["success"] is True
        assert len(result["installed"]) == 2
        assert len(result["failed"]) == 0

    def test_install_applications_partial_failure(self, windows_manager):
        """Test application installation with partial failures."""
        call_count = [0]

        def mock_run(*args, **_kwargs):
            call_count[0] += 1
            return {"success": call_count[0] == 1}

        windows_manager.run_command = mock_run

        result = windows_manager.install_applications(["app1", "app2"])
        assert result["success"] is False
        assert len(result["installed"]) == 1
        assert len(result["failed"]) == 1

    def test_install_applications_all_fail(self, windows_manager):
        """Test application installation when all fail."""
        windows_manager.run_command = Mock(return_value={"success": False})

        result = windows_manager.install_applications(["app1", "app2"])
        assert result["success"] is False
        assert len(result["installed"]) == 0
        assert len(result["failed"]) == 2

    def test_update_success(self, windows_manager):
        """Test successful system update."""
        windows_manager.run_command = Mock(return_value={"success": True})

        result = windows_manager.update()
        assert result["success"] is True
        assert "System and apps updated" in result["message"]

    def test_update_winget_fails(self, windows_manager):
        """Test system update when winget fails."""
        call_count = [0]

        def mock_run(*args, **_kwargs):
            call_count[0] += 1
            return {"success": call_count[0] == 2}  # Only Windows Update succeeds

        windows_manager.run_command = mock_run

        result = windows_manager.update()
        assert result["success"] is False
        assert "Partial update" in result["message"]

    def test_update_windows_update_fails(self, windows_manager):
        """Test system update when Windows Update fails."""
        call_count = [0]

        def mock_run(*args, **_kwargs):
            call_count[0] += 1
            return {"success": call_count[0] == 1}  # Only winget succeeds

        windows_manager.run_command = mock_run

        result = windows_manager.update()
        assert result["success"] is False
        assert "Partial update" in result["message"]

    def test_clean_success(self, windows_manager):
        """Test successful system cleanup."""
        windows_manager.run_command = Mock(return_value={"success": True})

        result = windows_manager.clean()
        assert result["success"] is True
        assert "Cleanup initiated" in result["message"]

    def test_clean_failure(self, windows_manager):
        """Test system cleanup failure."""
        windows_manager.run_command = Mock(return_value={"success": False})

        result = windows_manager.clean()
        assert result["success"] is False
        assert "Cleanup failed" in result["message"]

    def test_optimize_success(self, windows_manager):
        """Test successful system optimization."""
        windows_manager.run_command = Mock(return_value={"success": True})

        result = windows_manager.optimize()
        assert result["success"] is True
        assert "System optimized" in result["message"]

    def test_optimize_partial(self, windows_manager):
        """Test partial system optimization."""
        call_count = [0]

        def mock_run(*args, **_kwargs):
            call_count[0] += 1
            return {"success": call_count[0] == 1}

        windows_manager.run_command = mock_run

        result = windows_manager.optimize()
        assert result["success"] is False
        assert "Partial optimization" in result["message"]

    def test_list_windows_features_success(self, windows_manager):
        """Test successful listing of Windows features."""
        windows_manager.run_command = Mock(
            return_value={
                "success": True,
                "stdout": json.dumps(
                    [
                        {"Name": "TelnetClient", "State": "Disabled"},
                        {
                            "Name": "Microsoft-Windows-Subsystem-Linux",
                            "State": "Enabled",
                        },
                    ]
                ),
            }
        )

        result = windows_manager.list_windows_features()
        assert len(result) == 2
        assert result[0]["Name"] == "TelnetClient"

    def test_list_windows_features_single_item(self, windows_manager):
        """Test listing Windows features with single item."""
        windows_manager.run_command = Mock(
            return_value={
                "success": True,
                "stdout": json.dumps({"Name": "TelnetClient", "State": "Disabled"}),
            }
        )

        result = windows_manager.list_windows_features()
        assert len(result) == 1
        assert isinstance(result, list)

    def test_list_windows_features_command_failure(self, windows_manager):
        """Test listing Windows features when command fails."""
        windows_manager.run_command = Mock(return_value={"success": False})

        result = windows_manager.list_windows_features()
        assert len(result) == 0

    def test_list_windows_features_json_error(self, windows_manager):
        """Test listing Windows features with JSON parse error."""
        windows_manager.run_command = Mock(
            return_value={"success": True, "stdout": "invalid json"}
        )

        result = windows_manager.list_windows_features()
        assert len(result) == 0

    def test_enable_windows_features_success(self, windows_manager):
        """Test successful enabling of Windows features."""
        windows_manager.run_command = Mock(return_value={"success": True})

        result = windows_manager.enable_windows_features(["TelnetClient", "WSL"])
        assert result["success"] is True
        assert len(result["enabled"]) == 2
        assert len(result["failed"]) == 0

    def test_enable_windows_features_partial_failure(self, windows_manager):
        """Test enabling Windows features with partial failures."""
        call_count = [0]

        def mock_run(*args, **_kwargs):
            call_count[0] += 1
            return {"success": call_count[0] == 1}

        windows_manager.run_command = mock_run

        result = windows_manager.enable_windows_features(["feature1", "feature2"])
        assert result["success"] is False
        assert len(result["enabled"]) == 1
        assert len(result["failed"]) == 1

    def test_enable_windows_features_all_fail(self, windows_manager):
        """Test enabling Windows features when all fail."""
        windows_manager.run_command = Mock(return_value={"success": False})

        result = windows_manager.enable_windows_features(["feature1", "feature2"])
        assert result["success"] is False
        assert len(result["enabled"]) == 0
        assert len(result["failed"]) == 2

    def test_disable_windows_features_success(self, windows_manager):
        """Test successful disabling of Windows features."""
        windows_manager.run_command = Mock(return_value={"success": True})

        result = windows_manager.disable_windows_features(["TelnetClient"])
        assert result["success"] is True
        assert len(result["disabled"]) == 1
        assert len(result["failed"]) == 0

    def test_disable_windows_features_partial_failure(self, windows_manager):
        """Test disabling Windows features with partial failures."""
        call_count = [0]

        def mock_run(*args, **_kwargs):
            call_count[0] += 1
            return {"success": call_count[0] == 1}

        windows_manager.run_command = mock_run

        result = windows_manager.disable_windows_features(["feature1", "feature2"])
        assert result["success"] is False
        assert len(result["disabled"]) == 1
        assert len(result["failed"]) == 1

    def test_install_snapd(self, windows_manager):
        """Test that snapd installation is not supported on Windows."""
        result = windows_manager.install_snapd()
        assert result["success"] is False
        assert "not supported on Windows" in result["error"]

    def test_add_repository(self, windows_manager):
        """Test that repository addition is not supported on Windows."""
        result = windows_manager.add_repository("https://repo.example.com")
        assert result["success"] is False
        assert "not supported on Windows" in result["error"]

    def test_install_local_package(self, windows_manager):
        """Test that local package installation is not supported on Windows."""
        result = windows_manager.install_local_package("/path/to/package.msi")
        assert result["success"] is False
        assert "not supported on Windows" in result["error"]

    def test_search_package_success(self, windows_manager):
        """Test successful package search using winget."""
        windows_manager.run_command = Mock(
            return_value={
                "success": True,
                "stdout": "Name: Visual Studio Code\nId: Microsoft.VisualStudioCode",
            }
        )

        result = windows_manager.search_package("Visual Studio")
        assert result["success"] is True
        assert "Visual Studio Code" in result["output"]

    def test_search_package_failure(self, windows_manager):
        """Test package search failure."""
        windows_manager.run_command = Mock(return_value={"success": False})

        result = windows_manager.search_package("nonexistent")
        assert result["success"] is False

    def test_get_package_info_success(self, windows_manager):
        """Test successful package info retrieval."""
        windows_manager.run_command = Mock(
            return_value={
                "success": True,
                "stdout": "Name: Visual Studio Code\nVersion: 1.0.0",
            }
        )

        result = windows_manager.get_package_info("Microsoft.VisualStudioCode")
        assert result["success"] is True
        assert "Visual Studio Code" in result["info"]

    def test_get_package_info_failure(self, windows_manager):
        """Test package info retrieval failure."""
        windows_manager.run_command = Mock(return_value={"success": False})

        result = windows_manager.get_package_info("nonexistent")
        assert result["success"] is False

    def test_list_installed_packages_success(self, windows_manager):
        """Test successful listing of installed packages."""
        windows_manager.run_command = Mock(
            return_value={
                "success": True,
                "stdout": "Name: Visual Studio Code\nName: Git",
            }
        )

        result = windows_manager.list_installed_packages()
        assert result["success"] is True
        assert "Visual Studio Code" in result["output"]

    def test_list_installed_packages_failure(self, windows_manager):
        """Test listing installed packages failure."""
        windows_manager.run_command = Mock(return_value={"success": False})

        result = windows_manager.list_installed_packages()
        assert result["success"] is False

    def test_list_upgradable_packages_success(self, windows_manager):
        """Test successful listing of upgradable packages."""
        windows_manager.run_command = Mock(
            return_value={
                "success": True,
                "stdout": "Name: Visual Studio Code (update available)\nName: Git (update available)",
            }
        )

        result = windows_manager.list_upgradable_packages()
        assert result["success"] is True
        assert "update available" in result["output"]

    def test_list_upgradable_packages_failure(self, windows_manager):
        """Test listing upgradable packages failure."""
        windows_manager.run_command = Mock(return_value={"success": False})

        result = windows_manager.list_upgradable_packages()
        assert result["success"] is False

    def test_clean_package_cache(self, windows_manager):
        """Test package cache cleaning."""
        windows_manager.run_command = Mock(
            return_value={"success": True, "stdout": "Cache cleaned"}
        )

        result = windows_manager.clean_package_cache()
        assert result["success"] is True
        assert "Windows package cache cleaned" in result["message"]

    def test_clean_package_cache_failure(self, windows_manager):
        """Test package cache cleaning failure."""
        windows_manager.run_command = Mock(
            return_value={"success": False, "stderr": "Access denied"}
        )

        result = windows_manager.clean_package_cache()
        # This method returns success: True even if the command fails
        assert result["success"] is True

    def test_winget_bin_path_expansion(self, _mock_windows_platform, tmp_path):
        """Test that winget binary path contains WindowsApps."""
        with patch("os.path.exists", return_value=True):
            manager = WindowsManager(silent=True)
            assert "WindowsApps" in manager.winget_bin
            assert "winget" in manager.winget_bin

    def test_restart_service_winget_bin_fallback(self, windows_manager):
        """Test restart_service with winget_bin fallback."""
        # Set winget_bin to a non-existent path
        windows_manager.winget_bin = "/nonexistent/winget.exe"
        windows_manager.run_command = Mock(return_value={"success": True})

        result = windows_manager.restart_service("ssh")
        assert result["success"] is True
        # Should have updated winget_bin to "winget.exe"

    def test_install_applications_command_structure(self, windows_manager):
        """Test that install_applications constructs correct winget command."""
        windows_manager.run_command = Mock(return_value={"success": True})

        windows_manager.install_applications(["Microsoft.VisualStudioCode"])

        # Verify the command structure
        call_args = windows_manager.run_command.call_args[0][0]
        assert "winget" in call_args
        assert "install" in call_args
        assert "--id" in call_args
        assert "--silent" in call_args
        assert "--accept-package-agreements" in call_args
        assert "--accept-source-agreements" in call_args

    def test_update_command_structure(self, windows_manager):
        """Test that update constructs correct commands."""
        windows_manager.run_command = Mock(return_value={"success": True})

        windows_manager.update()

        # Should have called run_command twice
        assert windows_manager.run_command.call_count == 2

        # First call should be winget upgrade
        first_call = windows_manager.run_command.call_args_list[0][0][0]
        assert "winget" in first_call
        assert "upgrade" in first_call

        # Second call should be PowerShell Windows Update
        second_call = windows_manager.run_command.call_args_list[1][0][0]
        assert "powershell.exe" in second_call

    def test_optimize_command_structure(self, windows_manager):
        """Test that optimize constructs correct commands."""
        windows_manager.run_command = Mock(return_value={"success": True})

        windows_manager.optimize()

        # Should have called run_command twice
        assert windows_manager.run_command.call_count == 2

        # First call should be cleanmgr
        first_call = windows_manager.run_command.call_args_list[0][0][0]
        assert "cleanmgr" in first_call

        # Second call should be PowerShell Optimize-Volume
        second_call = windows_manager.run_command.call_args_list[1][0][0]
        assert "powershell.exe" in second_call
        assert "Optimize-Volume" in str(second_call)

    def test_enable_windows_features_command_structure(self, windows_manager):
        """Test that enable_windows_features constructs correct command."""
        windows_manager.run_command = Mock(return_value={"success": True})

        windows_manager.enable_windows_features(["TelnetClient"])

        call_args = windows_manager.run_command.call_args[0][0]
        assert "powershell.exe" in call_args
        assert "Enable-WindowsOptionalFeature" in str(call_args)
        assert "TelnetClient" in str(call_args)
        assert "-NoRestart" in str(call_args)

    def test_disable_windows_features_command_structure(self, windows_manager):
        """Test that disable_windows_features constructs correct command."""
        windows_manager.run_command = Mock(return_value={"success": True})

        windows_manager.disable_windows_features(["TelnetClient"])

        call_args = windows_manager.run_command.call_args[0][0]
        assert "powershell.exe" in call_args
        assert "Disable-WindowsOptionalFeature" in str(call_args)
        assert "TelnetClient" in str(call_args)

    def test_list_windows_features_command_structure(self, windows_manager):
        """Test that list_windows_features constructs correct command."""
        windows_manager.run_command = Mock(
            return_value={"success": True, "stdout": "[]"}
        )

        windows_manager.list_windows_features()

        call_args = windows_manager.run_command.call_args[0][0]
        assert "powershell.exe" in call_args
        assert "Get-WindowsOptionalFeature" in str(call_args)
        assert "ConvertTo-Json" in str(call_args)

    def test_search_package_uses_winget_bin(self, windows_manager):
        """Test that search_package uses winget_bin."""
        windows_manager.run_command = Mock(return_value={"success": True})

        windows_manager.search_package("test")

        call_args = windows_manager.run_command.call_args[0][0]
        assert windows_manager.winget_bin in call_args
        assert "search" in call_args

    def test_get_package_info_uses_winget_bin(self, windows_manager):
        """Test that get_package_info uses winget_bin."""
        windows_manager.run_command = Mock(return_value={"success": True})

        windows_manager.get_package_info("test")

        call_args = windows_manager.run_command.call_args[0][0]
        assert windows_manager.winget_bin in call_args
        assert "show" in call_args

    def test_list_installed_packages_uses_winget_bin(self, windows_manager):
        """Test that list_installed_packages uses winget_bin."""
        windows_manager.run_command = Mock(return_value={"success": True})

        windows_manager.list_installed_packages()

        call_args = windows_manager.run_command.call_args[0][0]
        assert windows_manager.winget_bin in call_args
        assert "list" in call_args

    def test_list_upgradable_packages_uses_winget_bin(self, windows_manager):
        """Test that list_upgradable_packages uses winget_bin."""
        windows_manager.run_command = Mock(return_value={"success": True})

        windows_manager.list_upgradable_packages()

        call_args = windows_manager.run_command.call_args[0][0]
        assert windows_manager.winget_bin in call_args
        assert "upgrade" in call_args

    def test_inherits_base_class_methods(self, windows_manager):
        """Test that WindowsManager inherits all base class methods."""
        from systems_manager.systems_manager import SystemsManagerBase

        assert isinstance(windows_manager, SystemsManagerBase)
        assert hasattr(windows_manager, "run_command")
        assert hasattr(windows_manager, "install_python_modules")
        assert hasattr(windows_manager, "font")
        assert hasattr(windows_manager, "get_os_statistics")
        assert hasattr(windows_manager, "get_hardware_statistics")
        assert hasattr(windows_manager, "list_services")
        assert hasattr(windows_manager, "list_processes")
        assert hasattr(windows_manager, "list_network_interfaces")
        assert hasattr(windows_manager, "ping_host")
        assert hasattr(windows_manager, "dns_lookup")
        assert hasattr(windows_manager, "list_disks")
        assert hasattr(windows_manager, "list_users")
        assert hasattr(windows_manager, "list_groups")
        assert hasattr(windows_manager, "get_system_logs")
        assert hasattr(windows_manager, "system_health_check")
        assert hasattr(windows_manager, "list_ssh_keys")
        assert hasattr(windows_manager, "generate_ssh_key")
        assert hasattr(windows_manager, "add_authorized_key")
        assert hasattr(windows_manager, "list_env_vars")
        assert hasattr(windows_manager, "clean_temp_files")
        assert hasattr(windows_manager, "get_disk_space_report")

    def test_helper_managers_initialized(self, windows_manager):
        """Test that helper managers are initialized."""
        assert windows_manager.fs_manager is not None
        assert windows_manager.shell_manager is not None
        assert windows_manager.python_manager is not None
        assert windows_manager.node_manager is not None

    def test_silent_mode(self, windows_manager):
        """Test that silent mode is set correctly."""
        assert windows_manager.silent is True

        manager_not_silent = WindowsManager(silent=False)
        assert manager_not_silent.silent is False

    def test_logger_initialized(self, windows_manager):
        """Test that logger is initialized."""
        assert windows_manager.logger is not None
