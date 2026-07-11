from systems_manager.k8s_detect import is_k8s_node


def _no_signal(**overrides):
    """Return injected seams that report no Kubernetes signal, with overrides."""
    seams = {
        "run_command": lambda cmd: "",
        "path_exists": lambda path: False,
        "which": lambda binary: None,
    }
    seams.update(overrides)
    return seams


def test_is_k8s_node_false_when_no_signals():
    is_node, reason = is_k8s_node(**_no_signal())
    assert is_node is False
    assert "no Kubernetes" in reason


def test_is_k8s_node_true_when_rke2_server_active():
    def run_command(cmd):
        if cmd == ["systemctl", "is-active", "rke2-server"]:
            return "active"
        return ""

    is_node, reason = is_k8s_node(**_no_signal(run_command=run_command))
    assert is_node is True
    assert "rke2-server" in reason


def test_is_k8s_node_true_when_rke2_agent_active():
    def run_command(cmd):
        if cmd == ["systemctl", "is-active", "rke2-agent"]:
            return "active"
        return ""

    is_node, reason = is_k8s_node(**_no_signal(run_command=run_command))
    assert is_node is True
    assert "rke2-agent" in reason


def test_is_k8s_node_false_when_unit_inactive():
    def run_command(cmd):
        return "inactive"

    is_node, reason = is_k8s_node(**_no_signal(run_command=run_command))
    assert is_node is False


def test_is_k8s_node_true_when_rancher_config_path_exists():
    def path_exists(path):
        return path == "/etc/rancher/rke2/"

    is_node, reason = is_k8s_node(**_no_signal(path_exists=path_exists))
    assert is_node is True
    assert "/etc/rancher/rke2/" in reason


def test_is_k8s_node_true_when_rancher_var_lib_path_exists():
    def path_exists(path):
        return path == "/var/lib/rancher/rke2/"

    is_node, reason = is_k8s_node(**_no_signal(path_exists=path_exists))
    assert is_node is True
    assert "/var/lib/rancher/rke2/" in reason


def test_is_k8s_node_true_when_kubelet_var_lib_path_exists():
    def path_exists(path):
        return path == "/var/lib/kubelet"

    is_node, reason = is_k8s_node(**_no_signal(path_exists=path_exists))
    assert is_node is True
    assert "/var/lib/kubelet" in reason


def test_is_k8s_node_true_when_kubelet_binary_present():
    def which(binary):
        return "/usr/bin/kubelet" if binary == "kubelet" else None

    is_node, reason = is_k8s_node(**_no_signal(which=which))
    assert is_node is True
    assert "kubelet" in reason


def test_is_k8s_node_true_when_k3s_binary_present():
    def which(binary):
        return "/usr/local/bin/k3s" if binary == "k3s" else None

    is_node, reason = is_k8s_node(**_no_signal(which=which))
    assert is_node is True
    assert "k3s" in reason


def test_is_k8s_node_default_run_command_survives_missing_binary():
    # No injected seams -> exercises the real default_run_command / os.path.exists
    # / shutil.which seams. It must not raise even if systemctl is absent.
    is_node, reason = is_k8s_node()
    assert isinstance(is_node, bool)
    assert isinstance(reason, str)
