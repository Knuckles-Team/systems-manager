from unittest.mock import patch

from systems_manager.systems_manager import AptManager, WindowsManager


def _patch_k8s_node(is_node: bool, reason: str = "test signal"):
    return patch(
        "systems_manager.systems_manager.is_k8s_node",
        return_value=(is_node, reason),
    )


# ----------------- update() guard -----------------


def test_update_refuses_on_k8s_node_without_override():
    mgr = AptManager(silent=True)
    with (
        _patch_k8s_node(True, "systemd unit 'rke2-agent' is active"),
        patch.object(mgr, "run_command") as mock_run,
    ):
        res = mgr.update()
        assert res["success"] is False
        assert "Kubernetes" in res["error"]
        assert "governed rolling update workflow" in res["error"]
        mock_run.assert_not_called()


def test_update_proceeds_on_k8s_node_with_override():
    mgr = AptManager(silent=True)
    with (
        _patch_k8s_node(True, "systemd unit 'rke2-agent' is active"),
        patch.object(
            mgr,
            "run_command",
            return_value={"success": True},
        ),
    ):
        res = mgr.update(allow_on_k8s=True)
        assert res["success"] is True


def test_update_proceeds_on_k8s_node_with_env_override(monkeypatch):
    monkeypatch.setenv("ALLOW_UPDATE_ON_K8S", "1")
    mgr = AptManager(silent=True)
    with (
        _patch_k8s_node(True, "systemd unit 'rke2-agent' is active"),
        patch.object(
            mgr,
            "run_command",
            return_value={"success": True},
        ),
    ):
        res = mgr.update()
        assert res["success"] is True


def test_update_proceeds_normally_on_non_k8s_host():
    mgr = AptManager(silent=True)
    with (
        _patch_k8s_node(False, "no Kubernetes signals detected"),
        patch.object(
            mgr,
            "run_command",
            return_value={"success": True},
        ),
    ):
        res = mgr.update()
        assert res["success"] is True


def test_windows_manager_update_refuses_on_k8s_node_without_override():
    with patch("os.path.exists", return_value=True):
        mgr = WindowsManager(silent=True)
    with (
        _patch_k8s_node(True, "path '/var/lib/kubelet' exists"),
        patch.object(mgr, "run_command") as mock_run,
    ):
        res = mgr.update()
        assert res["success"] is False
        assert "Kubernetes" in res["error"]
        mock_run.assert_not_called()


# ----------------- reboot() guard -----------------


def test_reboot_refuses_on_k8s_node_without_override():
    mgr = AptManager(silent=True)
    with (
        _patch_k8s_node(True, "systemd unit 'rke2-server' is active"),
        patch.object(mgr, "run_command") as mock_run,
    ):
        res = mgr.reboot()
        assert res["success"] is False
        assert "Kubernetes" in res["error"]
        assert "governed rolling update workflow" in res["error"]
        mock_run.assert_not_called()


def test_reboot_proceeds_on_k8s_node_with_override():
    mgr = AptManager(silent=True)
    with (
        _patch_k8s_node(True, "systemd unit 'rke2-server' is active"),
        patch.object(mgr, "run_command", return_value={"success": True}),
    ):
        res = mgr.reboot(allow_on_k8s=True)
        assert res["success"] is True


def test_reboot_proceeds_normally_on_non_k8s_host():
    mgr = AptManager(silent=True)
    with (
        _patch_k8s_node(False, "no Kubernetes signals detected"),
        patch.object(mgr, "run_command", return_value={"success": True}),
    ):
        res = mgr.reboot()
        assert res["success"] is True
        mgr.run_command.assert_called_once_with(["systemctl", "reboot"], elevated=True)


def test_windows_manager_reboot_uses_windows_command():
    with patch("os.path.exists", return_value=True):
        mgr = WindowsManager(silent=True)
    with (
        _patch_k8s_node(False, "no Kubernetes signals detected"),
        patch("platform.system", return_value="Windows"),
        patch.object(mgr, "run_command", return_value={"success": True}),
    ):
        res = mgr.reboot()
        assert res["success"] is True
        mgr.run_command.assert_called_once_with(
            ["shutdown.exe", "/r", "/t", "0"], elevated=True
        )
