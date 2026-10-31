"""Windows-portability tests: Windows branches exercised by monkeypatching."""

import ast
import os
from pathlib import Path
from unittest.mock import Mock

import pytest

from systems_manager import k8s_detect, sudo_helper
from systems_manager import systems_manager as sm
from systems_manager.systems_manager import NodeManager, filesystem_anchor


def test_package_imports_no_posix_only_modules():
    """No module of the package may import pwd/grp/fcntl/termios/resource."""
    banned = {"pwd", "grp", "fcntl", "termios", "resource"}
    root = Path(sm.__file__).parent
    for source in root.rglob("*.py"):
        for node in ast.walk(ast.parse(source.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                names = {a.name.split(".")[0] for a in node.names}
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = {node.module.split(".")[0]}
            else:
                continue
            assert not names & banned, f"{source.name} imports {names & banned}"


def test_node_manager_bash_bootstrap_is_typed_unsupported_on_windows(
    mock_windows_platform,
):
    manager = Mock()
    node = NodeManager(manager)
    for result in (node.install_node(), node.use_node("20")):
        assert result["success"] is False
        assert result["unsupported_platform"] == "Windows"
        assert "Unsupported on this platform" in result["error"]
    manager.run_command.assert_not_called()


def test_k8s_detection_skips_systemctl_and_posix_paths_on_windows(monkeypatch):
    monkeypatch.setattr(k8s_detect.platform, "system", lambda: "Windows")
    run = Mock(return_value="active")
    is_node, reason = k8s_detect.is_k8s_node(
        run_command=run, path_exists=lambda p: True, which=lambda b: "x"
    )
    assert is_node is False
    assert "Linux" in reason
    run.assert_not_called()


def test_sudo_helper_refuses_on_windows_with_typed_result(monkeypatch, capsys):
    monkeypatch.setattr(sudo_helper.os, "name", "nt")
    with pytest.raises(SystemExit) as exit_info:
        sudo_helper.main()
    assert exit_info.value.code == 1
    out = capsys.readouterr().out
    assert "unsupported_platform" in out and "POSIX-only" in out


def test_filesystem_anchor_follows_current_volume(monkeypatch):
    assert filesystem_anchor() == (Path.cwd().anchor or os.sep)

    class FakeCwd:
        anchor = "D:\\"

    monkeypatch.setattr(sm.Path, "cwd", classmethod(lambda cls: FakeCwd()))
    assert filesystem_anchor() == "D:\\"


def test_hardware_statistics_never_queries_posix_root(
    mock_windows_platform, monkeypatch
):
    seen = []
    monkeypatch.setattr(sm, "filesystem_anchor", lambda: "C:\\")
    monkeypatch.setattr(
        sm.psutil, "disk_usage", lambda p: seen.append(p) or Mock(_asdict=dict)
    )
    monkeypatch.setattr(sm.psutil, "cpu_percent", lambda interval=1: 0.0)
    manager = sm.WindowsManager(silent=True)
    manager.get_hardware_statistics()
    assert seen == ["C:\\"]


def test_os_statistics_without_getloadavg(mock_windows_platform, monkeypatch):
    monkeypatch.delattr(os, "getloadavg", raising=False)
    stats = sm.WindowsManager(silent=True).get_os_statistics()
    assert stats["load_avg"] == "N/A"


def test_run_command_elevation_on_windows_never_uses_sudo(
    mock_windows_platform, monkeypatch
):
    monkeypatch.setattr(sm, "_windows_process_is_admin", lambda: False)
    spawn = Mock()
    monkeypatch.setattr(sm, "_spawn_managed_process", spawn)
    monkeypatch.setattr(sm, "_resolve_trusted_executable", lambda e: e)
    result = sm.WindowsManager(silent=True).run_command(["shutdown.exe"], elevated=True)
    assert result["success"] is False
    spawn.assert_not_called()


def test_spawn_uses_new_process_group_not_session_on_windows(monkeypatch):
    monkeypatch.setattr(sm.os, "name", "nt")
    popen = Mock()
    monkeypatch.setattr(sm.subprocess, "Popen", popen)
    monkeypatch.setattr(sm, "_minimal_child_environment", lambda o: {})
    monkeypatch.setattr(sm.subprocess, "CREATE_NEW_PROCESS_GROUP", 512, raising=False)
    sm._spawn_managed_process(["x"], None)
    kwargs = popen.call_args.kwargs
    assert kwargs["start_new_session"] is False
    assert kwargs["creationflags"] == 512
