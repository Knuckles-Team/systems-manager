import json
from unittest.mock import MagicMock, patch

import pytest

from systems_manager import sudo_helper
from systems_manager.systems_manager import (
    setup_sudo,
)


def test_sudo_helper_requires_root():
    with patch("os.getuid", return_value=1000):
        with pytest.raises(SystemExit) as exc:
            sudo_helper.main()
        assert exc.value.code == 1


def test_sudo_helper_invalid_service_whitelist():
    with (
        patch("os.getuid", return_value=0),
        patch(
            "sys.argv",
            ["systems-manager-helper", "service", "start", "invalid-service"],
        ),
        patch("builtins.print") as mock_print,
    ):
        with pytest.raises(SystemExit) as exc:
            sudo_helper.main()
        assert exc.value.code == 1
        printed_args = mock_print.call_args[0][0]
        data = json.loads(printed_args)
        assert data["success"] is False
        assert "secure helper whitelist" in data["error"]


def test_sudo_helper_valid_service():
    with (
        patch("os.getuid", return_value=0),
        patch("sys.argv", ["systems-manager-helper", "service", "start", "nginx"]),
        patch("subprocess.run") as mock_run,
        patch("builtins.print") as mock_print,
    ):
        mock_run.return_value = MagicMock(returncode=0, stdout="Started", stderr="")
        sudo_helper.main()
        mock_run.assert_called_once_with(
            ["/usr/bin/systemctl", "start", "nginx"],
            capture_output=True,
            text=True,
            shell=False,
            env={"SYSTEMD_PAGER": "cat", "PATH": "/usr/bin:/usr/sbin:/bin:/sbin"},
        )
        printed_args = mock_print.call_args[0][0]
        data = json.loads(printed_args)
        assert data["success"] is True
        assert data["stdout"] == "Started"


def test_sudo_helper_invalid_package_whitelist():
    with (
        patch("os.getuid", return_value=0),
        patch(
            "sys.argv",
            ["systems-manager-helper", "package", "install", "malicious-package"],
        ),
        patch("builtins.print") as mock_print,
    ):
        with pytest.raises(SystemExit) as exc:
            sudo_helper.main()
        assert exc.value.code == 1
        printed_args = mock_print.call_args[0][0]
        data = json.loads(printed_args)
        assert data["success"] is False
        assert "secure helper whitelist" in data["error"]


def test_sudo_helper_valid_package_actions():
    # Install valid package
    with (
        patch("os.getuid", return_value=0),
        patch("sys.argv", ["systems-manager-helper", "package", "install", "nginx"]),
        patch("subprocess.run") as mock_run,
        patch("builtins.print"),
    ):
        mock_run.return_value = MagicMock(returncode=0, stdout="Installed", stderr="")
        sudo_helper.main()
        mock_run.assert_called_once_with(
            ["/usr/bin/apt-get", "install", "-y", "nginx"],
            capture_output=True,
            text=True,
            shell=False,
            env={"SYSTEMD_PAGER": "cat", "PATH": "/usr/bin:/usr/sbin:/bin:/sbin"},
        )

    # General apt update action
    with (
        patch("os.getuid", return_value=0),
        patch("sys.argv", ["systems-manager-helper", "package", "update"]),
        patch("subprocess.run") as mock_run,
        patch("builtins.print"),
    ):
        mock_run.return_value = MagicMock(returncode=0, stdout="Updated", stderr="")
        sudo_helper.main()
        mock_run.assert_called_once_with(
            ["/usr/bin/apt-get", "update"],
            capture_output=True,
            text=True,
            shell=False,
            env={"SYSTEMD_PAGER": "cat", "PATH": "/usr/bin:/usr/sbin:/bin:/sbin"},
        )


def test_setup_sudo_command():
    with (
        patch("getpass.getuser", return_value="testuser"),
        patch("shutil.which", return_value="/usr/local/bin/systems-manager-helper"),
        patch("tempfile.mkstemp", return_value=(12, "/tmp/temp_sudoers")),
        patch("os.fdopen", MagicMock()),
        patch("os.path.exists", return_value=True),
        patch("os.remove", MagicMock()),
        patch("subprocess.run") as mock_run,
    ):
        mock_run.side_effect = [
            MagicMock(returncode=0),  # cp
            MagicMock(returncode=0),  # chown
            MagicMock(returncode=0),  # chmod
            MagicMock(returncode=0, stdout="", stderr=""),  # visudo check
        ]
        setup_sudo()
        assert mock_run.call_count == 4
        args = mock_run.call_args_list[3][0][0]
        assert "visudo" in args
        assert "-c" in args
