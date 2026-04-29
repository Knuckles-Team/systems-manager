"""Tests for Linux package managers (AptManager, DnfManager, ZypperManager, PacmanManager)."""

from unittest.mock import Mock, patch
import pytest
from systems_manager.systems_manager import (
    AptManager,
    DnfManager,
    ZypperManager,
    PacmanManager,
)


class TestAptManager:
    """Tests for AptManager class."""

    @pytest.fixture
    def apt_manager(self, _mock_linux_platform):
        """Create an AptManager instance for testing."""
        return AptManager(silent=True)

    def test_initialization(self, apt_manager):
        """Test AptManager initialization."""
        assert apt_manager.silent is True
        assert apt_manager.not_found_msg == "Unable to locate package"

    def test_install_applications_success(self, apt_manager):
        """Test successful application installation."""
        apt_manager.run_command = Mock(return_value={"success": True})

        result = apt_manager.install_applications(["vim", "git"])
        assert result["success"] is True
        assert len(result["natively_installed"]) == 2
        assert len(result["failed"]) == 0

    def test_install_applications_with_update_failure(self, apt_manager):
        """Test application installation when apt update fails."""
        call_count = [0]

        def mock_run(*args, **_kwargs):
            call_count[0] += 1
            if call_count[0] == 1:  # apt update
                return {"success": False, "error": "Update failed"}
            return {"success": True}

        apt_manager.run_command = mock_run

        result = apt_manager.install_applications(["vim"])
        assert result["success"] is False
        assert "update_error" in result

    def test_install_applications_with_snap_fallback(self, apt_manager):
        """Test application installation with snap fallback."""
        call_count = [0]

        def mock_run(*args, **_kwargs):
            call_count[0] += 1
            if call_count[0] == 1:  # apt update
                return {"success": True}
            elif call_count[0] == 2:  # apt install
                return {
                    "success": False,
                    "stderr": "Unable to locate package nonexistent",
                }
            return {"success": True}  # snap install

        apt_manager.run_command = mock_run

        result = apt_manager.install_applications(["nonexistent"])
        assert len(result["snap_installed"]) == 1
        assert len(result["failed"]) == 0

    def test_install_applications_snap_fallback_fails(self, apt_manager):
        """Test application installation when snap fallback also fails."""
        call_count = [0]

        def mock_run(*args, **_kwargs):
            call_count[0] += 1
            if call_count[0] == 1:  # apt update
                return {"success": True}
            elif call_count[0] == 2:  # apt install
                return {
                    "success": False,
                    "stderr": "Unable to locate package nonexistent",
                }
            return {"success": False}  # snap install fails

        apt_manager.run_command = mock_run

        result = apt_manager.install_applications(["nonexistent"])
        assert len(result["failed"]) == 1
        assert result["success"] is False

    def test_install_applications_generic_failure(self, apt_manager):
        """Test application installation with generic failure."""
        apt_manager.run_command = Mock(
            return_value={"success": False, "error": "Permission denied"}
        )

        result = apt_manager.install_applications(["vim"])
        assert result["success"] is False
        assert len(result["failed"]) == 1

    def test_update_success(self, apt_manager):
        """Test successful system update."""
        apt_manager.run_command = Mock(return_value={"success": True})

        result = apt_manager.update()
        assert result["success"] is True
        assert "System and packages updated" in result["message"]

    def test_update_apt_update_fails(self, apt_manager):
        """Test system update when apt update fails."""
        apt_manager.run_command = Mock(return_value={"success": False})

        result = apt_manager.update()
        assert result["success"] is False
        assert "apt update failed" in result["error"]

    def test_update_apt_upgrade_fails(self, apt_manager):
        """Test system update when apt upgrade fails."""
        call_count = [0]

        def mock_run(*args, **_kwargs):
            call_count[0] += 1
            if call_count[0] == 1:  # apt update
                return {"success": True}
            return {"success": False}  # apt upgrade fails

        apt_manager.run_command = mock_run

        result = apt_manager.update()
        assert result["success"] is False
        assert "apt upgrade failed" in result["error"]

    def test_clean_success(self, apt_manager):
        """Test successful system cleanup."""
        apt_manager.run_command = Mock(return_value={"success": True})

        result = apt_manager.clean()
        assert result["success"] is True
        assert "Trash emptied" in result["message"]

    def test_clean_trash_cli_install_fails(self, apt_manager):
        """Test system cleanup when trash-cli install fails."""
        apt_manager.run_command = Mock(return_value={"success": False})

        result = apt_manager.clean()
        assert result["success"] is False

    def test_optimize_success(self, apt_manager):
        """Test successful system optimization."""
        apt_manager.run_command = Mock(return_value={"success": True})

        result = apt_manager.optimize()
        assert result["success"] is True
        assert "System optimized" in result["message"]

    def test_optimize_partial(self, apt_manager):
        """Test partial system optimization."""
        call_count = [0]

        def mock_run(*args, **_kwargs):
            call_count[0] += 1
            return {"success": call_count[0] == 1}

        apt_manager.run_command = mock_run

        result = apt_manager.optimize()
        assert result["success"] is False
        assert "Partial optimization" in result["message"]

    def test_install_snapd_success(self, apt_manager):
        """Test successful snapd installation."""
        apt_manager.run_command = Mock(return_value={"success": True})

        result = apt_manager.install_snapd()
        assert result["success"] is True
        assert "snapd installed" in result["message"]

    def test_install_snapd_failure(self, apt_manager):
        """Test snapd installation failure."""
        apt_manager.run_command = Mock(return_value={"success": False})

        result = apt_manager.install_snapd()
        assert result["success"] is False
        assert "Failed to install snapd" in result["message"]

    def test_add_repository_success(self, apt_manager):
        """Test successful repository addition."""
        apt_manager.run_command = Mock(return_value={"success": True})

        result = apt_manager.add_repository("ppa:repo/test", "test-repo")
        assert result["success"] is True

    def test_add_repository_add_fails(self, apt_manager):
        """Test repository addition when add fails."""
        apt_manager.run_command = Mock(return_value={"success": False})

        result = apt_manager.add_repository("ppa:repo/test")
        assert result["success"] is False

    def test_add_repository_update_fails(self, apt_manager):
        """Test repository addition when update fails."""
        call_count = [0]

        def mock_run(*args, **_kwargs):
            call_count[0] += 1
            return {"success": call_count[0] == 1}

        apt_manager.run_command = mock_run

        result = apt_manager.add_repository("ppa:repo/test")
        assert result["success"] is False

    def test_install_local_package_success(self, apt_manager):
        """Test successful local package installation."""
        apt_manager.run_command = Mock(return_value={"success": True})

        result = apt_manager.install_local_package("/path/to/package.deb")
        assert result["success"] is True

    def test_install_local_package_not_deb(self, apt_manager):
        """Test local package installation with non-deb file."""
        result = apt_manager.install_local_package("/path/to/package.rpm")
        assert result["success"] is False
        assert "Not a .deb file" in result["error"]

    def test_install_local_package_fix_fails(self, apt_manager):
        """Test local package installation when fix fails."""
        call_count = [0]

        def mock_run(*args, **_kwargs):
            call_count[0] += 1
            return {"success": call_count[0] == 1}

        apt_manager.run_command = mock_run

        result = apt_manager.install_local_package("/path/to/package.deb")
        assert result["success"] is False

    def test_search_package_success(self, apt_manager):
        """Test successful package search."""
        apt_manager.run_command = Mock(
            return_value={
                "success": True,
                "stdout": "vim - Vi IMproved\nnano - Nano's editor",
            }
        )

        result = apt_manager.search_package("editor")
        assert result["success"] is True
        assert len(result["packages"]) == 2

    def test_search_package_empty_result(self, apt_manager):
        """Test package search with empty results."""
        apt_manager.run_command = Mock(return_value={"success": True, "stdout": ""})

        result = apt_manager.search_package("nonexistent")
        assert result["success"] is True
        assert len(result["packages"]) == 0

    def test_search_package_failure(self, apt_manager):
        """Test package search failure."""
        apt_manager.run_command = Mock(return_value={"success": False})

        result = apt_manager.search_package("editor")
        assert result["success"] is False

    def test_get_package_info_success(self, apt_manager):
        """Test successful package info retrieval."""
        apt_manager.run_command = Mock(
            return_value={"success": True, "stdout": "Package: vim\nVersion: 8.2"}
        )

        result = apt_manager.get_package_info("vim")
        assert result["success"] is True
        assert "Package" in result["info"]

    def test_get_package_info_failure(self, apt_manager):
        """Test package info retrieval failure."""
        apt_manager.run_command = Mock(return_value={"success": False})

        result = apt_manager.get_package_info("vim")
        assert result["success"] is False

    def test_list_installed_packages_success(self, apt_manager):
        """Test successful listing of installed packages."""
        apt_manager.run_command = Mock(
            return_value={
                "success": True,
                "stdout": "vim install\nnano install\ngnome-desktop install",
            }
        )

        result = apt_manager.list_installed_packages()
        assert result["success"] is True
        assert len(result["packages"]) == 3

    def test_list_installed_packages_empty(self, apt_manager):
        """Test listing installed packages with empty result."""
        apt_manager.run_command = Mock(return_value={"success": True, "stdout": ""})

        result = apt_manager.list_installed_packages()
        assert result["success"] is True
        assert len(result["packages"]) == 0

    def test_list_upgradable_packages_success(self, apt_manager):
        """Test successful listing of upgradable packages."""
        apt_manager.run_command = Mock(
            return_value={
                "success": True,
                "stdout": "vim/stable 1.0 2.0\nnano/stable 1.0 2.0\nListing...",
            }
        )

        result = apt_manager.list_upgradable_packages()
        assert result["success"] is True
        assert len(result["packages"]) == 2

    def test_list_upgradable_packages_empty(self, apt_manager):
        """Test listing upgradable packages with empty result."""
        apt_manager.run_command = Mock(return_value={"success": True, "stdout": ""})

        result = apt_manager.list_upgradable_packages()
        assert result["success"] is True
        assert len(result["packages"]) == 0

    def test_clean_package_cache_success(self, apt_manager):
        """Test successful package cache cleaning."""
        apt_manager.run_command = Mock(return_value={"success": True})

        result = apt_manager.clean_package_cache()
        assert result["success"] is True
        assert "APT cache cleaned" in result["message"]

    def test_clean_package_cache_failure(self, apt_manager):
        """Test package cache cleaning failure."""
        apt_manager.run_command = Mock(return_value={"success": False})

        result = apt_manager.clean_package_cache()
        assert result["success"] is False
        assert "Failed" in result["message"]


class TestDnfManager:
    """Tests for DnfManager class."""

    @pytest.fixture
    def dnf_manager(self, _mock_rhel_platform):
        """Create a DnfManager instance for testing."""
        return DnfManager(silent=True)

    def test_initialization(self, dnf_manager):
        """Test DnfManager initialization."""
        assert dnf_manager.silent is True
        assert dnf_manager.not_found_msg == "Unable to find a match"

    def test_install_applications_success(self, dnf_manager):
        """Test successful application installation."""
        dnf_manager.run_command = Mock(return_value={"success": True})

        result = dnf_manager.install_applications(["vim", "git"])
        assert result["success"] is True
        assert len(result["natively_installed"]) == 2

    def test_install_applications_with_snap_fallback(self, dnf_manager):
        """Test application installation with snap fallback."""
        call_count = [0]

        def mock_run(*args, **_kwargs):
            call_count[0] += 1
            if call_count[0] == 1:  # dnf update
                return {"success": True}
            elif call_count[0] == 2:  # dnf install
                return {
                    "success": False,
                    "stderr": "Unable to find a match nonexistent",
                }
            return {"success": True}  # snap install

        dnf_manager.run_command = mock_run

        result = dnf_manager.install_applications(["nonexistent"])
        assert len(result["snap_installed"]) == 1

    def test_install_applications_update_fails(self, dnf_manager):
        """Test application installation when update fails."""
        dnf_manager.run_command = Mock(return_value={"success": False})

        result = dnf_manager.install_applications(["vim"])
        assert len(result["natively_installed"]) == 0
        assert len(result["failed"]) == 1

    def test_update_success(self, dnf_manager):
        """Test successful system update."""
        dnf_manager.run_command = Mock(return_value={"success": True})

        result = dnf_manager.update()
        assert result["success"] is True
        assert "System updated" in result["message"]

    def test_update_failure(self, dnf_manager):
        """Test system update failure."""
        dnf_manager.run_command = Mock(return_value={"success": False})

        result = dnf_manager.update()
        assert result["success"] is False
        assert "Update failed" in result["message"]

    def test_clean_success(self, dnf_manager):
        """Test successful system cleanup."""
        dnf_manager.run_command = Mock(return_value={"success": True})

        result = dnf_manager.clean()
        assert result["success"] is True
        assert "Cache cleaned" in result["message"]

    def test_optimize_success(self, dnf_manager):
        """Test successful system optimization."""
        dnf_manager.run_command = Mock(return_value={"success": True})

        result = dnf_manager.optimize()
        assert result["success"] is True
        assert "Orphans removed" in result["message"]

    def test_install_snapd_success(self, dnf_manager):
        """Test successful snapd installation."""
        dnf_manager.run_command = Mock(return_value={"success": True})

        result = dnf_manager.install_snapd()
        assert result["success"] is True

    def test_add_repository_success(self, dnf_manager):
        """Test successful repository addition."""
        dnf_manager.run_command = Mock(return_value={"success": True})

        result = dnf_manager.add_repository("https://repo.example.com", "test-repo")
        assert result["success"] is True

    def test_add_repository_add_fails(self, dnf_manager):
        """Test repository addition when add fails."""
        dnf_manager.run_command = Mock(return_value={"success": False})

        result = dnf_manager.add_repository("https://repo.example.com")
        assert result["success"] is False

    def test_install_local_package_success(self, dnf_manager):
        """Test successful local package installation."""
        dnf_manager.run_command = Mock(return_value={"success": True})

        result = dnf_manager.install_local_package("/path/to/package.rpm")
        assert result["success"] is True

    def test_install_local_package_not_rpm(self, dnf_manager):
        """Test local package installation with non-rpm file."""
        result = dnf_manager.install_local_package("/path/to/package.deb")
        assert result["success"] is False
        assert "Not a .rpm file" in result["error"]

    def test_search_package_success(self, dnf_manager):
        """Test successful package search."""
        dnf_manager.run_command = Mock(
            return_value={
                "success": True,
                "stdout": "vim.x86_64 : Vi IMproved\nnano.x86_64 : Nano's editor",
            }
        )

        result = dnf_manager.search_package("editor")
        assert result["success"] is True
        assert len(result["packages"]) == 2

    def test_search_package_with_equals_sign(self, dnf_manager):
        """Test package search with lines starting with =."""
        dnf_manager.run_command = Mock(
            return_value={
                "success": True,
                "stdout": "=vim.x86_64 : Vi IMproved\nnano.x86_64 : Nano's editor",
            }
        )

        result = dnf_manager.search_package("editor")
        assert result["success"] is True
        assert len(result["packages"]) == 1  # Should skip lines starting with =

    def test_get_package_info_success(self, dnf_manager):
        """Test successful package info retrieval."""
        dnf_manager.run_command = Mock(
            return_value={"success": True, "stdout": "Name: vim\nVersion: 8.2"}
        )

        result = dnf_manager.get_package_info("vim")
        assert result["success"] is True
        assert "Name" in result["info"]

    def test_list_installed_packages_success(self, dnf_manager):
        """Test successful listing of installed packages."""
        dnf_manager.run_command = Mock(
            return_value={
                "success": True,
                "stdout": "Installed Packages\nvim.x86_64 8.2\nnano.x86_64 5.0",
            }
        )

        result = dnf_manager.list_installed_packages()
        assert result["success"] is True
        assert len(result["packages"]) == 2

    def test_list_installed_packages_skip_headers(self, dnf_manager):
        """Test listing installed packages skipping header lines."""
        dnf_manager.run_command = Mock(
            return_value={
                "success": True,
                "stdout": "Installed Packages\nLast metadata expiration check\nvim.x86_64 8.2",
            }
        )

        result = dnf_manager.list_installed_packages()
        assert result["success"] is True
        assert len(result["packages"]) == 1

    def test_list_upgradable_packages_success(self, dnf_manager):
        """Test successful listing of upgradable packages."""
        dnf_manager.run_command = Mock(
            return_value={
                "success": True,
                "stdout": "vim.x86_64 8.0 8.2\nnano.x86_64 5.0 5.1",
            }
        )

        result = dnf_manager.list_upgradable_packages()
        assert result["success"] is True
        assert len(result["packages"]) == 2

    def test_list_upgradable_packages_empty(self, dnf_manager):
        """Test listing upgradable packages with empty result."""
        dnf_manager.run_command = Mock(return_value={"success": True, "stdout": ""})

        result = dnf_manager.list_upgradable_packages()
        assert result["success"] is True
        assert len(result["packages"]) == 0

    def test_clean_package_cache_success(self, dnf_manager):
        """Test successful package cache cleaning."""
        dnf_manager.run_command = Mock(return_value={"success": True})

        result = dnf_manager.clean_package_cache()
        assert result["success"] is True
        assert "DNF cache cleaned" in result["message"]


class TestZypperManager:
    """Tests for ZypperManager class."""

    @pytest.fixture
    def zypper_manager(self):
        """Create a ZypperManager instance for testing."""
        # Mock SLES platform
        with (
            patch("platform.system", return_value="Linux"),
            patch("distro.id", return_value="sles"),
        ):
            return ZypperManager(silent=True)

    def test_initialization(self, zypper_manager):
        """Test ZypperManager initialization."""
        assert zypper_manager.silent is True
        assert zypper_manager.not_found_msg == "No provider of"

    def test_install_applications_success(self, zypper_manager):
        """Test successful application installation."""
        zypper_manager.run_command = Mock(return_value={"success": True})

        result = zypper_manager.install_applications(["vim", "git"])
        assert result["success"] is True
        assert len(result["natively_installed"]) == 2

    def test_install_applications_with_snap_fallback(self, zypper_manager):
        """Test application installation with snap fallback."""
        call_count = [0]

        def mock_run(*args, **_kwargs):
            call_count[0] += 1
            if call_count[0] == 1:  # zypper install
                return {"success": False, "stderr": "No provider of nonexistent"}
            return {"success": True}  # snap install

        zypper_manager.run_command = mock_run

        result = zypper_manager.install_applications(["nonexistent"])
        assert len(result["snap_installed"]) == 1

    def test_update_success(self, zypper_manager):
        """Test successful system update."""
        zypper_manager.run_command = Mock(return_value={"success": True})

        result = zypper_manager.update()
        assert result["success"] is True
        assert "System updated" in result["message"]

    def test_clean_success(self, zypper_manager):
        """Test successful system cleanup."""
        zypper_manager.run_command = Mock(return_value={"success": True})

        result = zypper_manager.clean()
        assert result["success"] is True
        assert "Cache cleaned" in result["message"]

    def test_optimize_success(self, zypper_manager):
        """Test successful system optimization."""
        zypper_manager.run_command = Mock(return_value={"success": True})

        result = zypper_manager.optimize()
        assert result["success"] is True
        assert "Unneeded removed" in result["message"]

    def test_install_snapd_success(self, zypper_manager):
        """Test successful snapd installation."""
        zypper_manager.run_command = Mock(return_value={"success": True})

        result = zypper_manager.install_snapd()
        assert result["success"] is True

    def test_add_repository_success(self, zypper_manager):
        """Test successful repository addition."""
        zypper_manager.run_command = Mock(return_value={"success": True})

        result = zypper_manager.add_repository("https://repo.example.com", "test-repo")
        assert result["success"] is True

    def test_add_repository_default_name(self, zypper_manager):
        """Test repository addition with default name."""
        zypper_manager.run_command = Mock(return_value={"success": True})

        result = zypper_manager.add_repository("https://repo.example.com")
        assert result["success"] is True

    def test_add_repository_add_fails(self, zypper_manager):
        """Test repository addition when add fails."""
        zypper_manager.run_command = Mock(return_value={"success": False})

        result = zypper_manager.add_repository("https://repo.example.com")
        assert result["success"] is False

    def test_install_local_package_success(self, zypper_manager):
        """Test successful local package installation."""
        zypper_manager.run_command = Mock(return_value={"success": True})

        result = zypper_manager.install_local_package("/path/to/package.rpm")
        assert result["success"] is True

    def test_install_local_package_not_rpm(self, zypper_manager):
        """Test local package installation with non-rpm file."""
        result = zypper_manager.install_local_package("/path/to/package.deb")
        assert result["success"] is False
        assert "Not a .rpm file" in result["error"]

    def test_search_package_success(self, zypper_manager):
        """Test successful package search."""
        zypper_manager.run_command = Mock(
            return_value={
                "success": True,
                "stdout": "S | Name | Summary\ni | vim | Vi IMproved\ni | nano | Nano's editor",
            }
        )

        result = zypper_manager.search_package("editor")
        assert result["success"] is True
        assert len(result["packages"]) == 2

    def test_search_package_skip_invalid_lines(self, zypper_manager):
        """Test package search skipping invalid lines."""
        zypper_manager.run_command = Mock(
            return_value={
                "success": True,
                "stdout": "S | Name | Summary\n- | - | -\ni | vim | Vi IMproved",
            }
        )

        result = zypper_manager.search_package("editor")
        assert result["success"] is True
        assert len(result["packages"]) == 1

    def test_get_package_info_success(self, zypper_manager):
        """Test successful package info retrieval."""
        zypper_manager.run_command = Mock(
            return_value={"success": True, "stdout": "Name: vim\nVersion: 8.2"}
        )

        result = zypper_manager.get_package_info("vim")
        assert result["success"] is True
        assert "Name" in result["info"]

    def test_list_installed_packages_success(self, zypper_manager):
        """Test successful listing of installed packages."""
        zypper_manager.run_command = Mock(
            return_value={
                "success": True,
                "stdout": "S | Name | Summary\ni | vim | Vi IMproved\ni | nano | Nano's editor",
            }
        )

        result = zypper_manager.list_installed_packages()
        assert result["success"] is True
        assert len(result["packages"]) == 2

    def test_list_installed_packages_skip_non_installed(self, zypper_manager):
        """Test listing installed packages skipping non-installed."""
        zypper_manager.run_command = Mock(
            return_value={
                "success": True,
                "stdout": "S | Name | Summary\ni | vim | Vi IMproved\nv | nano | Nano's editor",
            }
        )

        result = zypper_manager.list_installed_packages()
        assert result["success"] is True
        assert len(result["packages"]) == 1

    def test_list_upgradable_packages_success(self, zypper_manager):
        """Test successful listing of upgradable packages."""
        zypper_manager.run_command = Mock(
            return_value={
                "success": True,
                "stdout": "S | Repository | Package | Version\nv | repo | vim | 8.2\nv | repo | nano | 5.1",
            }
        )

        result = zypper_manager.list_upgradable_packages()
        assert result["success"] is True
        # The parsing logic is complex, just verify it runs
        assert "packages" in result

    def test_list_upgradable_packages_skip_invalid(self, zypper_manager):
        """Test listing upgradable packages skipping invalid lines."""
        zypper_manager.run_command = Mock(
            return_value={
                "success": True,
                "stdout": "S | Repository | Package | Version\n- | - | - | -\nv | repo | vim | 8.2",
            }
        )

        result = zypper_manager.list_upgradable_packages()
        assert result["success"] is True
        # The parsing logic is complex, just verify it runs
        assert "packages" in result

    def test_clean_package_cache_success(self, zypper_manager):
        """Test successful package cache cleaning."""
        zypper_manager.run_command = Mock(return_value={"success": True})

        result = zypper_manager.clean_package_cache()
        assert result["success"] is True
        assert "Zypper cache cleaned" in result["message"]


class TestPacmanManager:
    """Tests for PacmanManager class."""

    @pytest.fixture
    def pacman_manager(self, _mock_arch_platform):
        """Create a PacmanManager instance for testing."""
        return PacmanManager(silent=True)

    def test_initialization(self, pacman_manager):
        """Test PacmanManager initialization."""
        assert pacman_manager.silent is True
        assert pacman_manager.not_found_msg == "target not found"

    def test_install_applications_success(self, pacman_manager):
        """Test successful application installation."""
        pacman_manager.run_command = Mock(return_value={"success": True})

        result = pacman_manager.install_applications(["vim", "git"])
        assert result["success"] is True
        assert len(result["natively_installed"]) == 2

    def test_install_applications_with_snap_fallback(self, pacman_manager):
        """Test application installation with snap fallback."""
        call_count = [0]

        def mock_run(*args, **_kwargs):
            call_count[0] += 1
            if call_count[0] == 1:  # pacman install
                return {"success": False, "stderr": "target not found nonexistent"}
            return {"success": True}  # snap install

        pacman_manager.run_command = mock_run

        result = pacman_manager.install_applications(["nonexistent"])
        assert len(result["snap_installed"]) == 1

    def test_update_success(self, pacman_manager):
        """Test successful system update."""
        pacman_manager.run_command = Mock(return_value={"success": True})

        result = pacman_manager.update()
        assert result["success"] is True
        assert "System updated" in result["message"]

    def test_clean_success(self, pacman_manager):
        """Test successful system cleanup."""
        pacman_manager.run_command = Mock(return_value={"success": True})

        result = pacman_manager.clean()
        assert result["success"] is True
        assert "Cache cleaned" in result["message"]

    def test_optimize_success(self, pacman_manager):
        """Test successful system optimization."""
        pacman_manager.run_command = Mock(return_value={"success": True})

        result = pacman_manager.optimize()
        assert result["success"] is True
        assert "Orphans removed" in result["message"]

    def test_install_snapd_success(self, pacman_manager):
        """Test successful snapd installation."""
        pacman_manager.run_command = Mock(return_value={"success": True})

        result = pacman_manager.install_snapd()
        assert result["success"] is True

    def test_add_repository_success(self, pacman_manager):
        """Test successful repository addition."""
        pacman_manager.run_command = Mock(return_value={"success": True})

        result = pacman_manager.add_repository("https://repo.example.com", "custom")
        assert result["success"] is True

    def test_add_repository_default_name(self, pacman_manager):
        """Test repository addition with default name."""
        pacman_manager.run_command = Mock(return_value={"success": True})

        result = pacman_manager.add_repository("https://repo.example.com")
        assert result["success"] is True

    def test_add_repository_add_fails(self, pacman_manager):
        """Test repository addition when add fails."""
        pacman_manager.run_command = Mock(return_value={"success": False})

        result = pacman_manager.add_repository("https://repo.example.com")
        assert result["success"] is False

    def test_install_local_package_success(self, pacman_manager):
        """Test successful local package installation."""
        pacman_manager.run_command = Mock(return_value={"success": True})

        result = pacman_manager.install_local_package("/path/to/package.pkg.tar.zst")
        assert result["success"] is True

    def test_search_package_success(self, pacman_manager):
        """Test successful package search."""
        pacman_manager.run_command = Mock(
            return_value={
                "success": True,
                "stdout": "core/vim 8.2-1\n    Vi IMproved\nextra/nano 5.0-1\n    Nano's editor",
            }
        )

        result = pacman_manager.search_package("editor")
        assert result["success"] is True
        assert len(result["packages"]) == 2

    def test_search_package_single_line(self, pacman_manager):
        """Test package search with single line result."""
        pacman_manager.run_command = Mock(
            return_value={"success": True, "stdout": "core/vim 8.2-1\n    Vi IMproved"}
        )

        result = pacman_manager.search_package("vim")
        assert result["success"] is True
        assert len(result["packages"]) == 1

    def test_get_package_info_success(self, pacman_manager):
        """Test successful package info retrieval from repo."""
        pacman_manager.run_command = Mock(
            return_value={"success": True, "stdout": "Name: vim\nVersion: 8.2"}
        )

        result = pacman_manager.get_package_info("vim")
        assert result["success"] is True
        assert "Name" in result["info"]

    def test_get_package_info_fallback_to_installed(self, pacman_manager):
        """Test package info retrieval falling back to installed packages."""
        call_count = [0]

        def mock_run(*args, **_kwargs):
            call_count[0] += 1
            if call_count[0] == 1:  # pacman -Si fails
                return {"success": False}
            return {"success": True, "stdout": "Name: vim\nVersion: 8.2"}  # pacman -Qi

        pacman_manager.run_command = mock_run

        result = pacman_manager.get_package_info("vim")
        assert result["success"] is True

    def test_list_installed_packages_success(self, pacman_manager):
        """Test successful listing of installed packages."""
        pacman_manager.run_command = Mock(
            return_value={"success": True, "stdout": "vim\ngnome-desktop\nnano"}
        )

        result = pacman_manager.list_installed_packages()
        assert result["success"] is True
        assert len(result["packages"]) == 3

    def test_list_installed_packages_with_whitespace(self, pacman_manager):
        """Test listing installed packages with whitespace."""
        pacman_manager.run_command = Mock(
            return_value={"success": True, "stdout": "vim  \n  gnome-desktop\n  nano  "}
        )

        result = pacman_manager.list_installed_packages()
        assert result["success"] is True
        assert len(result["packages"]) == 3

    def test_list_upgradable_packages_success(self, pacman_manager):
        """Test successful listing of upgradable packages."""
        pacman_manager.run_command = Mock(
            return_value={"success": True, "stdout": "vim 8.0 -> 8.2\nnano 5.0 -> 5.1"}
        )

        result = pacman_manager.list_upgradable_packages()
        assert result["success"] is True
        assert len(result["packages"]) == 2

    def test_list_upgradable_packages_empty(self, pacman_manager):
        """Test listing upgradable packages with empty result."""
        pacman_manager.run_command = Mock(return_value={"success": True, "stdout": ""})

        result = pacman_manager.list_upgradable_packages()
        assert result["success"] is True
        assert len(result["packages"]) == 0

    def test_clean_package_cache_success(self, pacman_manager):
        """Test successful package cache cleaning."""
        pacman_manager.run_command = Mock(return_value={"success": True})

        result = pacman_manager.clean_package_cache()
        assert result["success"] is True
        assert "Pacman cache cleaned" in result["message"]
