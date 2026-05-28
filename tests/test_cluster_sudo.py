from unittest.mock import MagicMock, patch

import pytest

from systems_manager.systems_manager import bootstrap_cluster_sudo


def test_bootstrap_cluster_sudo_hostmanager_error():
    with (
        patch(
            "tunnel_manager.tunnel_manager.HostManager",
            side_effect=Exception("Failed to load inventory"),
        ),
        pytest.raises(SystemExit) as exc_info,
    ):
        bootstrap_cluster_sudo()
    assert exc_info.value.code == 1


def test_bootstrap_cluster_sudo_all_configured_or_offline():
    mock_hm = MagicMock()
    mock_hm.config_file = "/fake/inventory.yaml"
    mock_hm.hosts = {
        "gr1080": {
            "hostname": "gr1080.local",
            "user": "genius",
            "port": 22,
        },
        "r820": {
            "hostname": "r820.local",
            "user": "genius",
            "port": 22,
            "key_path": "~/my-key",
        },
    }

    # For r820:
    # 1. Connection check (ssh ... echo reachable) -> returns 0
    # 2. Sudo check (ssh ... sudo -n true) -> returns 0
    mock_res_connection = MagicMock()
    mock_res_connection.returncode = 0

    mock_res_sudo = MagicMock()
    mock_res_sudo.returncode = 0

    with (
        patch("tunnel_manager.tunnel_manager.HostManager", return_value=mock_hm),
        patch("subprocess.run") as mock_run,
    ):
        mock_run.side_effect = [mock_res_connection, mock_res_sudo]

        # This should complete without calling getpass because all hosts are either offline or already configured
        with patch("getpass.getpass") as mock_getpass:
            bootstrap_cluster_sudo()
            mock_getpass.assert_not_called()


def test_bootstrap_cluster_sudo_unreachable():
    mock_hm = MagicMock()
    mock_hm.config_file = "/fake/inventory.yaml"
    mock_hm.hosts = {
        "r710": {
            "hostname": "r710.local",
            "user": "genius",
            "port": 22,
        }
    }

    # Connection check fails
    mock_res_connection = MagicMock()
    mock_res_connection.returncode = 1

    with (
        patch("tunnel_manager.tunnel_manager.HostManager", return_value=mock_hm),
        patch("subprocess.run", return_value=mock_res_connection),
        patch("getpass.getpass") as mock_getpass,
    ):
        bootstrap_cluster_sudo()
        mock_getpass.assert_not_called()


def test_bootstrap_cluster_sudo_unreachable_exception():
    mock_hm = MagicMock()
    mock_hm.config_file = "/fake/inventory.yaml"
    mock_hm.hosts = {
        "r710": {
            "hostname": "r710.local",
            "user": "genius",
            "port": 22,
        }
    }

    with (
        patch("tunnel_manager.tunnel_manager.HostManager", return_value=mock_hm),
        patch("subprocess.run", side_effect=RuntimeError("SSH command failed")),
        patch("getpass.getpass") as mock_getpass,
    ):
        bootstrap_cluster_sudo()
        mock_getpass.assert_not_called()


def test_bootstrap_cluster_sudo_requires_password_success():
    mock_hm = MagicMock()
    mock_hm.config_file = "/fake/inventory.yaml"
    mock_hm.hosts = {
        "r510": {
            "hostname": "r510.local",
            "user": "genius",
            "port": 22,
        }
    }

    # 1. Connection check -> 0 (reachable)
    # 2. Sudo check -> 1 (requires password)
    mock_res_connection = MagicMock()
    mock_res_connection.returncode = 0

    mock_res_sudo = MagicMock()
    mock_res_sudo.returncode = 1

    # Mock Popen for writing the file (cat) and remote setup command
    mock_proc_cat = MagicMock()
    mock_proc_cat.returncode = 0
    mock_proc_cat.communicate.return_value = ("stdout_cat", "stderr_cat")

    mock_proc_setup = MagicMock()
    mock_proc_setup.returncode = 0
    mock_proc_setup.communicate.return_value = ("stdout_setup", "stderr_setup")

    with (
        patch("tunnel_manager.tunnel_manager.HostManager", return_value=mock_hm),
        patch("subprocess.run") as mock_run,
        patch("subprocess.Popen") as mock_popen,
        patch("getpass.getpass", return_value="my-secret-password") as mock_getpass,
    ):
        mock_run.side_effect = [
            mock_res_connection,
            mock_res_sudo,
            MagicMock(),
        ]  # third run is the cleanup command
        mock_popen.side_effect = [mock_proc_cat, mock_proc_setup]

        bootstrap_cluster_sudo()

        mock_getpass.assert_called_once()
        assert mock_popen.call_count == 2

        # Verify first Popen communicating helper rule
        first_communicate_call = mock_proc_cat.communicate.call_args_list[0]
        assert "NOPASSWD" in first_communicate_call[1]["input"]

        # Verify second Popen communicating password
        second_communicate_call = mock_proc_setup.communicate.call_args_list[0]
        assert "my-secret-password" in second_communicate_call[1]["input"]


def test_bootstrap_cluster_sudo_empty_password():
    mock_hm = MagicMock()
    mock_hm.config_file = "/fake/inventory.yaml"
    mock_hm.hosts = {
        "r510": {
            "hostname": "r510.local",
            "user": "genius",
            "port": 22,
        }
    }

    mock_res_connection = MagicMock()
    mock_res_connection.returncode = 0

    mock_res_sudo = MagicMock()
    mock_res_sudo.returncode = 1

    with (
        patch("tunnel_manager.tunnel_manager.HostManager", return_value=mock_hm),
        patch("subprocess.run") as mock_run,
        patch("getpass.getpass", return_value=""),
        pytest.raises(SystemExit) as exc_info,
    ):
        mock_run.side_effect = [mock_res_connection, mock_res_sudo]

        bootstrap_cluster_sudo()
    assert exc_info.value.code == 1


def test_bootstrap_cluster_sudo_file_copy_fails():
    mock_hm = MagicMock()
    mock_hm.config_file = "/fake/inventory.yaml"
    mock_hm.hosts = {
        "r510": {
            "hostname": "r510.local",
            "user": "genius",
            "port": 22,
        }
    }

    mock_res_connection = MagicMock()
    mock_res_connection.returncode = 0

    mock_res_sudo = MagicMock()
    mock_res_sudo.returncode = 1

    mock_proc_cat = MagicMock()
    mock_proc_cat.returncode = 1
    mock_proc_cat.communicate.return_value = ("stdout_cat", "permission denied")

    with (
        patch("tunnel_manager.tunnel_manager.HostManager", return_value=mock_hm),
        patch("subprocess.run") as mock_run,
        patch("subprocess.Popen", return_value=mock_proc_cat) as mock_popen,
        patch("getpass.getpass", return_value="my-secret-password"),
    ):
        mock_run.side_effect = [mock_res_connection, mock_res_sudo]

        # Should log error but not crash (gracefully continue loop)
        bootstrap_cluster_sudo()
        assert mock_popen.call_count == 1


def test_bootstrap_cluster_sudo_file_copy_exception():
    mock_hm = MagicMock()
    mock_hm.config_file = "/fake/inventory.yaml"
    mock_hm.hosts = {
        "r510": {
            "hostname": "r510.local",
            "user": "genius",
            "port": 22,
        }
    }

    mock_res_connection = MagicMock()
    mock_res_connection.returncode = 0

    mock_res_sudo = MagicMock()
    mock_res_sudo.returncode = 1

    with (
        patch("tunnel_manager.tunnel_manager.HostManager", return_value=mock_hm),
        patch("subprocess.run") as mock_run,
        patch(
            "subprocess.Popen", side_effect=RuntimeError("Popen failed")
        ) as mock_popen,
        patch("getpass.getpass", return_value="my-secret-password"),
    ):
        mock_run.side_effect = [mock_res_connection, mock_res_sudo]

        bootstrap_cluster_sudo()
        assert mock_popen.call_count == 1
