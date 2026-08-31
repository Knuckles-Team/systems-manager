"""Tests for platform detection and the managed-process timeout boundary."""

import sys
import time
from unittest.mock import patch

import pytest

from systems_manager.systems_manager import (
    AptManager,
    DnfManager,
    PacmanManager,
    WindowsManager,
    ZypperManager,
    _await_managed_process,
    _managed_command_result,
    _spawn_managed_process,
    _start_output_readers,
    detect_and_create_manager,
)


@pytest.fixture(autouse=True)
def _not_a_k8s_node():
    """Keep platform detection independent of the host running the tests."""
    with patch(
        "systems_manager.systems_manager.is_k8s_node",
        return_value=(False, "not a k8s node"),
    ):
        yield


def test_detect_and_create_manager_windows():
    with (
        patch("platform.system", return_value="Windows"),
        patch("os.path.exists", return_value=True),
    ):
        manager = detect_and_create_manager(silent=True)
        assert isinstance(manager, WindowsManager)


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


def test_managed_process_hung_child_is_bounded_by_timeout():
    """A managed child that never exits must be killed at its bounded deadline."""
    process = _spawn_managed_process(
        [sys.executable, "-c", "import time; time.sleep(60)"], None
    )
    readers, stdout_buffer, stderr_buffer = _start_output_readers(process)

    start = time.monotonic()
    run = _await_managed_process(process, readers, timeout_seconds=1)
    elapsed = time.monotonic() - start
    result = _managed_command_result(
        run,
        timeout_seconds=1,
        stdout_buffer=stdout_buffer,
        stderr_buffer=stderr_buffer,
        capture_output=True,
    )

    assert elapsed < 10, f"managed child blocked for {elapsed:.1f}s after timeout"
    assert result["success"] is False
    assert result["returncode"] != 0
    assert result["timed_out"] is True
    assert result["timeout_seconds"] == 1
    assert result["reader_cleanup_failed"] is False
    assert result["output_truncated"] is False
    assert result["stdout"] == ""
    assert result["stderr"] == ""
    assert result["error"] == "Managed command timed out"
