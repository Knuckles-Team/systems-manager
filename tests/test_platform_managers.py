import subprocess
import sys
import time
from unittest.mock import MagicMock, patch

import pytest

from systems_manager.systems_manager import (
    AptManager,
    CommandResult,
    DnfManager,
    PacmanManager,
    SystemsManagerBase,
    WindowsManager,
    ZypperManager,
    detect_and_create_manager,
)

# ----------------- detect_and_create_manager tests -----------------


def test_detect_and_create_manager_windows():
    with (
        patch("platform.system", return_value="Windows"),
        patch("os.path.exists", return_value=True),
    ):
        mgr = detect_and_create_manager(silent=True)
        assert isinstance(mgr, WindowsManager)


def test_detect_and_create_manager_linux_distros():
    with patch("platform.system", return_value="Linux"):
        with patch("distro.id", return_value="ubuntu"):
            assert isinstance(detect_and_create_manager(silent=True), AptManager)
        with patch("distro.id", return_value="debian"):
            assert isinstance(detect_and_create_manager(silent=True), AptManager)
        with patch("distro.id", return_value="rhel"):
            assert isinstance(detect_and_create_manager(silent=True), DnfManager)
        with patch("distro.id", return_value="centos"):
            assert isinstance(detect_and_create_manager(silent=True), DnfManager)
        with patch("distro.id", return_value="sles"):
            assert isinstance(detect_and_create_manager(silent=True), ZypperManager)
        with patch("distro.id", return_value="arch"):
            assert isinstance(detect_and_create_manager(silent=True), PacmanManager)

        with patch("distro.id", return_value="unknown_distro"):
            with pytest.raises(NotImplementedError):
                detect_and_create_manager(silent=True)


def test_detect_and_create_manager_unsupported_os():
    with patch("platform.system", return_value="FreeBSD"):
        with pytest.raises(NotImplementedError):
            detect_and_create_manager(silent=True)


# ----------------- SystemsManagerBase run_command & common logic -----------------


class DummyManager(SystemsManagerBase):
    """Concrete implementation of SystemsManagerBase for testing base class features."""

    def install_applications(self, apps: list[str]) -> CommandResult:
        return CommandResult(success=True)

    def update(self) -> CommandResult:
        return CommandResult(success=True)

    def clean(self) -> CommandResult:
        return CommandResult(success=True)

    def optimize(self) -> CommandResult:
        return CommandResult(success=True)

    def install_snapd(self) -> CommandResult:
        return CommandResult(success=True)

    def add_repository(self, repo_url: str, name: str | None = None) -> CommandResult:
        return CommandResult(success=True)

    def install_local_package(self, file_path: str) -> CommandResult:
        return CommandResult(success=True)

    def search_package(self, query: str) -> CommandResult:
        return CommandResult(success=True)

    def get_package_info(self, package: str) -> CommandResult:
        return CommandResult(success=True)

    def list_installed_packages(self) -> CommandResult:
        return CommandResult(success=True)

    def list_upgradable_packages(self) -> CommandResult:
        return CommandResult(success=True)

    def clean_package_cache(self) -> CommandResult:
        return CommandResult(success=True)


def test_systems_manager_base_run_command_linux():
    mgr = DummyManager(silent=True)

    # Non-elevated command (silent mode redirects to DEVNULL, stdout=None)
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="out", stderr="")
        res = mgr.run_command("ls -la")
        assert res.success is True
        assert res.get("stdout") is None
        mock_run.assert_called_with(
            ["ls", "-la"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            shell=False,
            check=True,
            timeout=None,
        )

    # Elevated command on Linux
    with (
        patch("platform.system", return_value="Linux"),
        patch("subprocess.run") as mock_run,
    ):
        mock_run.return_value = MagicMock(returncode=0, stdout="out", stderr="")
        res = mgr.run_command("apt update", elevated=True)
        assert res.success is True
        mock_run.assert_called_with(
            ["sudo", "apt", "update"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            shell=False,
            check=True,
            timeout=None,
        )

    # Non-silent execution
    mgr_noisy = DummyManager(silent=False)
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="out", stderr="")
        res = mgr_noisy.run_command("echo hello")
        assert res.success is True
        assert res.get("stdout") == "out"
        mock_run.assert_called_with(
            ["echo", "hello"],
            capture_output=True,
            text=True,
            shell=False,
            check=True,
            timeout=None,
        )


def test_systems_manager_base_run_command_windows_elevation():
    mgr = DummyManager(silent=True)

    with (
        patch("platform.system", return_value="Windows"),
        patch("subprocess.run") as mock_run,
    ):
        mock_run.return_value = MagicMock(returncode=0, stdout="out", stderr="")
        res = mgr.run_command("iisreset", elevated=True)
        assert res.success is True
        called_args = mock_run.call_args[0][0]
        assert "powershell.exe" in called_args
        assert "runAs" in called_args


def test_systems_manager_base_run_command_exceptions():
    mgr = DummyManager(silent=True)

    # CalledProcessError exception path
    err_process = subprocess.CalledProcessError(
        1, "false", stderr="Access Denied", output="Error output"
    )
    with patch("subprocess.run", side_effect=err_process):
        res = mgr.run_command("false")
        assert res.success is False
        assert res.get("returncode") == 1
        assert res.get("stderr") == "Access Denied"

    # General Exception path
    with patch("subprocess.run", side_effect=ValueError("Unexpected Error")):
        res = mgr.run_command("ls")
        assert res.success is False
        assert res.error is not None and "Unexpected Error" in res.error

    # subprocess.TimeoutExpired -> clear, non-hanging error (not a bare exception message)
    timeout_err = subprocess.TimeoutExpired(cmd="sleep 999", timeout=1)
    with patch("subprocess.run", side_effect=timeout_err):
        res = mgr.run_command(["sleep", "999"], timeout=1)
        assert res.success is False
        assert res.error is not None and "timed out" in res.error.lower()


def test_systems_manager_base_run_command_hung_process_is_bounded_by_timeout():
    """Regression for the systems-manager MCP hang: a real subprocess that never
    exits (simulating a stuck ipmitool/smartctl/ssh call) must not block
    ``run_command`` past its bounded ``timeout`` — it must return a clear error
    instead of hanging indefinitely."""
    mgr = DummyManager(silent=True)
    hang_forever = [sys.executable, "-c", "import time; time.sleep(60)"]

    start = time.monotonic()
    res = mgr.run_command(hang_forever, timeout=1)
    elapsed = time.monotonic() - start

    assert elapsed < 10, f"run_command blocked for {elapsed:.1f}s despite timeout=1"
    assert res.success is False
    assert res.error is not None and "timed out" in res.error.lower()

    # Non-silent (capture_output) branch is bounded the same way.
    mgr_noisy = DummyManager(silent=False)
    start = time.monotonic()
    res_noisy = mgr_noisy.run_command(hang_forever, timeout=1)
    elapsed_noisy = time.monotonic() - start

    assert elapsed_noisy < 10, (
        f"run_command (non-silent) blocked for {elapsed_noisy:.1f}s despite timeout=1"
    )
    assert res_noisy.success is False
    assert res_noisy.error is not None and "timed out" in res_noisy.error.lower()


def test_systems_manager_base_install_via_snap():
    mgr = DummyManager(silent=True)

    # Happy path: Snap already present
    with (
        patch("shutil.which", return_value="/usr/bin/snap"),
        patch.object(mgr, "run_command") as mock_run,
    ):
        mock_run.return_value = CommandResult(success=True)

        res = mgr.install_via_snap("htop")
        assert res.success is True
        assert res.get("app") == "htop"
        mock_run.assert_called_once_with(["snap", "install", "htop"], elevated=True)

    # Snap not present: triggers snapd installation, service enable, symlinking, and snap install
    with (
        patch("shutil.which", return_value=None),
        patch.object(
            mgr, "install_snapd", return_value=CommandResult(success=True)
        ) as mock_install_snapd,
        patch.object(mgr, "run_command") as mock_run,
    ):
        mock_run.return_value = CommandResult(success=True)
        res = mgr.install_via_snap("htop")
        assert res.success is True
        mock_install_snapd.assert_called_once()
        # Verify it tries to enable socket, make symlink, and install app
        assert mock_run.call_count == 3

    # Snap not present & snapd installation fails
    with (
        patch("shutil.which", return_value=None),
        patch.object(
            mgr,
            "install_snapd",
            return_value=CommandResult(success=False, error="apt failed"),
        ) as mock_install_snapd,
    ):
        res = mgr.install_via_snap("htop")
        assert res.success is False
        assert res.error is not None and "Failed to install snapd" in res.error


# ----------------- PythonManager & NodeManager tests -----------------


def test_python_manager():
    mgr = DummyManager(silent=True)
    pm = mgr.python_manager

    # install_uv Linux
    with (
        patch("platform.system", return_value="Linux"),
        patch.object(mgr, "run_command") as mock_run,
    ):
        mock_run.return_value = CommandResult(success=True)
        res = pm.install_uv()
        assert res.success is True
        mock_run.assert_called_with(
            "curl -LsSf https://astral.sh/uv/install.sh | sh", shell=True
        )

    # install_uv Windows
    with (
        patch("platform.system", return_value="Windows"),
        patch.object(mgr, "run_command") as mock_run,
    ):
        mock_run.return_value = CommandResult(success=True)
        res = pm.install_uv()
        assert res.success is True
        mock_run.assert_called_with(
            "irm https://astral.sh/uv/install.ps1 | iex", shell=True
        )

    # create_venv
    with patch.object(mgr, "run_command") as mock_run:
        mock_run.return_value = CommandResult(success=True)
        pm.create_venv("/path/to/venv", python_version="3.11")
        mock_run.assert_called_with(["uv", "venv", "/path/to/venv", "--python", "3.11"])

    # install_package
    with patch.object(mgr, "run_command") as mock_run:
        mock_run.return_value = CommandResult(success=True)
        pm.install_package("requests", venv_path="/path/to/venv")
        mock_run.assert_called_with(["uv", "pip", "install", "requests"])


def test_node_manager():
    mgr = DummyManager(silent=True)
    nm = mgr.node_manager

    # install_nvm Windows (unsupported)
    with patch("platform.system", return_value="Windows"):
        res = nm.install_nvm()
        assert res.success is False
        assert res.error is not None and "NVM for Windows not supported" in res.error

    # install_nvm Linux
    with (
        patch("platform.system", return_value="Linux"),
        patch.object(mgr, "run_command") as mock_run,
    ):
        mock_run.return_value = CommandResult(success=True)
        res = nm.install_nvm()
        assert res.success is True
        assert "raw.githubusercontent.com" in mock_run.call_args[0][0]

    # install_node
    with patch.object(mgr, "run_command") as mock_run:
        mock_run.return_value = CommandResult(success=True)
        nm.install_node("20")
        assert "nvm install 20" in mock_run.call_args[0][0]

    # use_node
    with patch.object(mgr, "run_command") as mock_run:
        mock_run.return_value = CommandResult(success=True)
        nm.use_node("20")
        assert "nvm use 20" in mock_run.call_args[0][0]


# ----------------- AptManager specific tests -----------------


def test_apt_manager_install_apps():
    mgr = AptManager(silent=True)

    # Happy Path (Natively installed)
    with patch.object(mgr, "run_elevated_tool") as mock_run:
        mock_run.side_effect = [
            {"success": True, "stdout": "", "stderr": ""},  # apt update
            {"success": True, "stdout": "", "stderr": ""},  # apt install htop
        ]
        res = mgr.install_applications(["htop"])
        assert res.get("success") is True
        assert "htop" in res.get("natively_installed")

    # Native Failure - Package Not Found, Snap fallback success
    with (
        patch.object(mgr, "run_elevated_tool") as mock_run,
        patch.object(mgr, "install_via_snap") as mock_snap,
    ):
        mock_run.side_effect = [
            {"success": True, "stdout": "", "stderr": ""},  # apt update
            {
                "success": False,
                "stderr": "Unable to locate package someapp",
            },  # apt install
        ]
        mock_snap.return_value = CommandResult(success=True)

        res = mgr.install_applications(["someapp"])
        assert res.get("success") is True
        assert "someapp" in res.get("snap_installed")

    # Native Failure - Package Not Found, Snap fallback failure
    with (
        patch.object(mgr, "run_elevated_tool") as mock_run,
        patch.object(mgr, "install_via_snap") as mock_snap,
    ):
        mock_run.side_effect = [
            {"success": True, "stdout": "", "stderr": ""},  # apt update
            {
                "success": False,
                "stderr": "Unable to locate package someapp",
            },  # apt install
        ]
        mock_snap.return_value = CommandResult(success=False, error="snap store down")

        res = mgr.install_applications(["someapp"])
        assert res.get("success") is False
        assert "someapp" in res.get("failed")

    # Native Failure - Other Error
    with patch.object(mgr, "run_elevated_tool") as mock_run:
        mock_run.side_effect = [
            {"success": True, "stdout": "", "stderr": ""},  # apt update
            {"success": False, "stderr": "dpkg locked"},  # apt install
        ]
        res = mgr.install_applications(["someapp"])
        assert res.get("success") is False
        assert "someapp" in res.get("failed")


def test_apt_manager_standard_actions():
    mgr = AptManager(silent=True)
    with (
        patch.object(mgr, "run_command", return_value=CommandResult(success=True)),
        patch.object(
            mgr,
            "run_elevated_tool",
            return_value={"success": True, "stdout": "", "stderr": ""},
        ),
    ):
        assert mgr.update().success is True
        assert mgr.clean().success is True
        assert mgr.optimize().success is True
        assert mgr.install_snapd().success is True
        assert mgr.add_repository("ppa:test").success is True
        assert mgr.install_local_package("pkg.deb").success is True
        assert mgr.search_package("htop").success is True
        assert mgr.get_package_info("htop").success is True
        assert mgr.list_installed_packages().success is True
        assert mgr.list_upgradable_packages().success is True
        assert mgr.clean_package_cache().success is True


# ----------------- DnfManager specific tests -----------------


def test_dnf_manager_install_apps():
    mgr = DnfManager(silent=True)

    # Happy Path Natively Installed
    with patch.object(mgr, "run_command") as mock_run:
        mock_run.side_effect = [
            CommandResult(success=True),  # dnf update
            CommandResult(success=True),  # dnf install
        ]
        res = mgr.install_applications(["htop"])
        assert res.get("success") is True
        assert "htop" in res.get("natively_installed")

    # Native Failure - Package Not Found, Snap fallback success
    with (
        patch.object(mgr, "run_command") as mock_run,
        patch.object(mgr, "install_via_snap") as mock_snap,
    ):
        mock_run.side_effect = [
            CommandResult(success=True),  # dnf update
            CommandResult(
                success=False, stderr="Unable to find a match someapp"
            ),  # dnf install
        ]
        mock_snap.return_value = CommandResult(success=True)

        res = mgr.install_applications(["someapp"])
        assert res.get("success") is True
        assert "someapp" in res.get("snap_installed")


def test_dnf_manager_standard_actions():
    mgr = DnfManager(silent=True)
    with patch.object(mgr, "run_command", return_value=CommandResult(success=True)):
        assert mgr.update().success is True
        assert mgr.clean().success is True
        assert mgr.optimize().success is True
        assert mgr.install_snapd().success is True
        assert mgr.add_repository("repo_url").success is True
        assert mgr.install_local_package("pkg.rpm").success is True
        assert mgr.search_package("htop").success is True
        assert mgr.get_package_info("htop").success is True
        assert mgr.list_installed_packages().success is True
        assert mgr.list_upgradable_packages().success is True
        assert mgr.clean_package_cache().success is True


# ----------------- ZypperManager specific tests -----------------


def test_zypper_manager_install_apps():
    mgr = ZypperManager(silent=True)

    # Native success
    with patch.object(mgr, "run_command") as mock_run:
        mock_run.side_effect = [
            CommandResult(success=True),  # zypper install
        ]
        res = mgr.install_applications(["htop"])
        assert res.get("success") is True
        assert "htop" in res.get("natively_installed")

    # Native fail, Snap success
    with (
        patch.object(mgr, "run_command") as mock_run,
        patch.object(mgr, "install_via_snap") as mock_snap,
    ):
        mock_run.side_effect = [
            CommandResult(success=False, stderr="No provider of someapp"),
        ]
        mock_snap.return_value = CommandResult(success=True)
        res = mgr.install_applications(["someapp"])
        assert res.get("success") is True
        assert "someapp" in res.get("snap_installed")


def test_zypper_manager_standard_actions():
    mgr = ZypperManager(silent=True)
    with patch.object(mgr, "run_command", return_value=CommandResult(success=True)):
        assert mgr.update().success is True
        assert mgr.clean().success is True
        assert mgr.optimize().success is True
        assert mgr.install_snapd().success is True
        assert mgr.add_repository("repo_url").success is True
        assert mgr.install_local_package("pkg.rpm").success is True
        assert mgr.search_package("htop").success is True
        assert mgr.get_package_info("htop").success is True
        assert mgr.list_installed_packages().success is True
        assert mgr.list_upgradable_packages().success is True
        assert mgr.clean_package_cache().success is True


# ----------------- PacmanManager specific tests -----------------


def test_pacman_manager_install_apps():
    mgr = PacmanManager(silent=True)

    # Native success
    with patch.object(mgr, "run_command") as mock_run:
        mock_run.side_effect = [
            CommandResult(success=True),  # pacman -S
        ]
        res = mgr.install_applications(["htop"])
        assert res.get("success") is True
        assert "htop" in res.get("natively_installed")

    # Native fail, Snap success
    with (
        patch.object(mgr, "run_command") as mock_run,
        patch.object(mgr, "install_via_snap") as mock_snap,
    ):
        mock_run.side_effect = [
            CommandResult(success=False, stderr="error: target not found: someapp"),
        ]
        mock_snap.return_value = CommandResult(success=True)
        res = mgr.install_applications(["someapp"])
        assert res.get("success") is True
        assert "someapp" in res.get("snap_installed")


def test_pacman_manager_standard_actions():
    mgr = PacmanManager(silent=True)
    with patch.object(mgr, "run_command", return_value=CommandResult(success=True)):
        assert mgr.update().success is True
        assert mgr.clean().success is True
        assert mgr.optimize().success is True
        assert mgr.install_snapd().success is True
        assert mgr.add_repository("repo_url").success is True
        assert mgr.install_local_package("pkg.pkg.tar.zst").success is True
        assert mgr.search_package("htop").success is True
        assert mgr.get_package_info("htop").success is True
        assert mgr.list_installed_packages().success is True
        assert mgr.list_upgradable_packages().success is True
        assert mgr.clean_package_cache().success is True


# ----------------- WindowsManager specific tests -----------------


def test_windows_manager_install_apps():
    with patch("os.path.exists", return_value=True):
        mgr = WindowsManager(silent=True)

    # Native success (winget)
    with patch.object(mgr, "run_command") as mock_run:
        mock_run.return_value = CommandResult(success=True)
        res = mgr.install_applications(["git"])
        assert res.get("success") is True
        assert "git" in res.get("installed")

    # Native failure
    with patch.object(mgr, "run_command") as mock_run:
        mock_run.return_value = CommandResult(success=False)
        res = mgr.install_applications(["git"])
        assert res.get("success") is False
        assert "git" in res.get("failed")


def test_windows_manager_standard_actions():
    with patch("os.path.exists", return_value=True):
        mgr = WindowsManager(silent=True)

    with patch.object(mgr, "run_command", return_value=CommandResult(success=True)):
        assert mgr.update().success is True
        assert mgr.clean().success is True
        assert mgr.optimize().success is True
        assert mgr.install_snapd().success is False  # Snap not supported on Windows
        assert mgr.add_repository("repo_url").success is False  # Not supported
        assert mgr.install_local_package("pkg.msi").success is False  # Not supported
        assert mgr.search_package("git").success is True
        assert mgr.get_package_info("git").success is True
        assert mgr.list_installed_packages().success is True
        assert mgr.list_upgradable_packages().success is True
        assert mgr.clean_package_cache().success is True
