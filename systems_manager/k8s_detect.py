"""Detect whether the LOCAL host is a live Kubernetes (RKE2) node.

CONCEPT:SM-OS.governance.k8s-lifecycle-guard: K8s Lifecycle Guard

Dependency-light, fast, local-host-only detection used to guard host-lifecycle
operations (reboot, OS update/upgrade) from running naively on a cluster node —
see ``SystemsManagerBase._k8s_lifecycle_guard`` in ``systems_manager.py``.
"""

import os
import shutil
import subprocess
from collections.abc import Callable

# systemd units that indicate this host is running RKE2 control-plane or agent.
_SYSTEMD_UNITS = ("rke2-server", "rke2-agent")

# Filesystem paths RKE2/kubelet create on any node they manage.
_K8S_PATHS = (
    "/etc/rancher/rke2/",
    "/var/lib/rancher/rke2/",
    "/var/lib/kubelet",
)

# Container-runtime / node-agent binaries that only exist on a k8s node.
_K8S_RUNTIME_BINARIES = ("kubelet", "k3s")


def _default_run_command(cmd: list[str]) -> str:
    """Run ``cmd`` and return stripped stdout, or "" on any failure."""
    try:
        result = subprocess.run(  # nosec - fixed, non-shell, read-only commands
            cmd, capture_output=True, text=True, timeout=3, check=False
        )
        return result.stdout.strip()
    except Exception:
        return ""


def is_k8s_node(
    run_command: Callable[[list[str]], str] = _default_run_command,
    path_exists: Callable[[str], bool] = os.path.exists,
    which: Callable[[str], str | None] = shutil.which,
) -> tuple[bool, str]:
    """Return whether the LOCAL host is a live Kubernetes (RKE2) node.

    Checks multiple independent signals; any one being true is sufficient:
      - ``systemctl is-active rke2-server`` / ``rke2-agent`` reports "active"
      - ``/etc/rancher/rke2/`` or ``/var/lib/rancher/rke2/`` exists
      - ``/var/lib/kubelet`` exists
      - a ``kubelet``/``k3s`` container-runtime/node-agent binary is on PATH

    ``run_command``, ``path_exists``, and ``which`` are injectable seams for
    testing — pass fakes to simulate a k8s node or a plain host without
    touching the real filesystem or shelling out.

    Returns a ``(is_node, reason)`` tuple; ``reason`` is a short human-readable
    explanation of which signal fired (or that none did).
    """
    for unit in _SYSTEMD_UNITS:
        if run_command(["systemctl", "is-active", unit]) == "active":
            return True, f"systemd unit '{unit}' is active"

    for path in _K8S_PATHS:
        if path_exists(path):
            return True, f"path '{path}' exists"

    for binary in _K8S_RUNTIME_BINARIES:
        if which(binary):
            return True, f"container-runtime binary '{binary}' found on PATH"

    return False, "no Kubernetes (RKE2/kubelet/k3s) signals detected"
