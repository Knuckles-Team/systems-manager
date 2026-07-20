"""Adversarial source tests for host execution and filesystem boundaries."""

import hashlib
import json
import os
from importlib import import_module
from pathlib import Path
from unittest.mock import Mock

import pytest
from pydantic import ValidationError

from systems_manager.mcp_server import SystemsSecurityMiddleware

systems_module = import_module("systems_manager.systems_manager")
from systems_manager.systems_manager import (
    AptManager,
    DnfManager,
    FileSystemManager,
    FirewallRuleSpec,
    NodeManager,
    SystemsManagerBase,
    _validated_command_argv,
    _validated_firewall_args,
    _validated_local_package,
    _validated_repository_url,
    _validated_timeout_seconds,
    managed_filesystem_root,
    resolve_managed_path,
)


class _Manager:
    logger = None


@pytest.mark.parametrize(
    "argv",
    [
        ["sh", "-c", "id"],
        ["bash", "-c", "id"],
        ["powershell.exe", "-Command", "Get-ChildItem"],
        ["python", "-c", "print('unsafe')"],
        ["/tmp/attacker/apt", "update"],
    ],
)
def test_arbitrary_executables_and_interpreter_programs_are_rejected(argv):
    with pytest.raises((PermissionError, ValueError)):
        _validated_command_argv(argv)


def test_package_operations_receive_longer_bounded_deadlines(monkeypatch):
    monkeypatch.delenv("SYSTEMS_MANAGER_COMMAND_TIMEOUT_SECONDS", raising=False)
    assert _validated_timeout_seconds(["apt", "upgrade", "-y"]) == 1_800
    assert _validated_timeout_seconds(["ping", "example.invalid"]) == 120


@pytest.mark.parametrize(
    "url",
    [
        "http://packages.example.invalid/repo",
        "https://user:password@packages.example.invalid/repo",
        "https://packages.example.invalid/repo?token=value",
    ],
)
def test_repository_urls_are_credential_free_https(url):
    with pytest.raises(ValueError):
        _validated_repository_url(url)


def test_repository_requires_deployment_allowlist(monkeypatch):
    url = "https://packages.example.invalid/repo"
    monkeypatch.delenv("SYSTEMS_MANAGER_REPOSITORY_ALLOWLIST_JSON", raising=False)
    with pytest.raises(PermissionError, match="allowlist"):
        _validated_repository_url(url)
    monkeypatch.setenv("SYSTEMS_MANAGER_REPOSITORY_ALLOWLIST_JSON", json.dumps([url]))
    assert _validated_repository_url(url) == url


def test_local_package_requires_matching_deployment_digest(monkeypatch, tmp_path):
    root = tmp_path / "managed"
    root.mkdir()
    package = root / "update.deb"
    package.write_bytes(b"signed-by-release-pipeline")
    monkeypatch.setenv("SYSTEMS_MANAGER_FILESYSTEM_ROOT", str(root))
    monkeypatch.delenv("SYSTEMS_MANAGER_LOCAL_PACKAGE_SHA256_MAP", raising=False)
    with pytest.raises(PermissionError, match="digest"):
        _validated_local_package("update.deb", (".deb",))

    expected = hashlib.sha256(package.read_bytes()).hexdigest()
    monkeypatch.setenv(
        "SYSTEMS_MANAGER_LOCAL_PACKAGE_SHA256_MAP",
        json.dumps({"update.deb": expected}),
    )
    assert _validated_local_package("update.deb", (".deb",)) == package


def test_local_package_rejects_digest_mismatch(monkeypatch, tmp_path):
    root = tmp_path / "managed"
    root.mkdir()
    (root / "update.rpm").write_bytes(b"untrusted")
    monkeypatch.setenv("SYSTEMS_MANAGER_FILESYSTEM_ROOT", str(root))
    monkeypatch.setenv(
        "SYSTEMS_MANAGER_LOCAL_PACKAGE_SHA256_MAP",
        json.dumps({"update.rpm": "0" * 64}),
    )
    with pytest.raises(ValueError, match="verification failed"):
        _validated_local_package("update.rpm", (".rpm",))


def test_managed_path_rejects_parent_and_absolute_escape(monkeypatch, tmp_path):
    root = tmp_path / "workspace"
    root.mkdir()
    monkeypatch.setenv("SYSTEMS_MANAGER_FILESYSTEM_ROOT", str(root))
    with pytest.raises(PermissionError):
        resolve_managed_path("../secret")
    with pytest.raises(PermissionError):
        resolve_managed_path(str(tmp_path / "outside"))


def test_managed_root_must_be_explicit(monkeypatch, tmp_path):
    monkeypatch.delenv("SYSTEMS_MANAGER_FILESYSTEM_ROOT", raising=False)
    monkeypatch.setenv("WORKSPACE_PATH", str(tmp_path))
    with pytest.raises(PermissionError, match="must explicitly select"):
        managed_filesystem_root()


def test_managed_root_rejects_relative_and_writable_directory(monkeypatch, tmp_path):
    monkeypatch.setenv("SYSTEMS_MANAGER_FILESYSTEM_ROOT", "relative/path")
    with pytest.raises(ValueError, match="absolute"):
        managed_filesystem_root()

    root = tmp_path / "writable"
    root.mkdir(mode=0o777)
    root.chmod(0o777)
    monkeypatch.setenv("SYSTEMS_MANAGER_FILESYSTEM_ROOT", str(root))
    if os.name != "nt":
        with pytest.raises(PermissionError, match="group/world writable"):
            managed_filesystem_root()


def test_managed_path_rejects_symlink_escape(monkeypatch, tmp_path):
    root = tmp_path / "workspace"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    (root / "link").symlink_to(outside, target_is_directory=True)
    monkeypatch.setenv("SYSTEMS_MANAGER_FILESYSTEM_ROOT", str(root))
    with pytest.raises(PermissionError):
        resolve_managed_path("link/secret")


def test_file_results_do_not_disclose_absolute_root(monkeypatch, tmp_path):
    root = tmp_path / "workspace"
    root.mkdir()
    (root / "document.txt").write_text("content", encoding="utf-8")
    monkeypatch.setenv("SYSTEMS_MANAGER_FILESYSTEM_ROOT", str(root))
    result = FileSystemManager(_Manager()).list_files(".")
    assert result["success"] is True
    assert result["path"] == "."
    assert result["items"][0]["path"] == "document.txt"
    assert str(Path(root)) not in repr(result)


@pytest.mark.parametrize("value", ["20; touch owned", "$(id)", "--lts && id"])
def test_node_version_rejects_shell_metacharacters(value):
    with pytest.raises(ValueError, match="version selector"):
        NodeManager._validated_version(value)


@pytest.mark.parametrize("value", ["service'; id", "$(id)", "name\nsecond"])
def test_service_name_rejects_interpreter_metacharacters(value):
    with pytest.raises(ValueError, match="service name"):
        SystemsManagerBase._validated_service_name(value)


class _Message:
    def __init__(self, name: str, arguments: dict | None = None):
        self.name = name
        self.arguments = arguments or {}


class _Context:
    def __init__(self, name: str, arguments: dict | None = None):
        self.message = _Message(name, arguments)


async def _allowed(_context):
    return {"success": True}


@pytest.mark.asyncio
async def test_host_mutations_are_default_deny(monkeypatch):
    monkeypatch.delenv("SYSTEMS_MANAGER_ALLOW_HOST_MUTATIONS", raising=False)
    middleware = SystemsSecurityMiddleware()
    with pytest.raises(PermissionError, match="Host mutation"):
        await middleware.on_call_tool(
            _Context("sm_advanced_operations", {"action": "install_uv"}), _allowed
        )


@pytest.mark.asyncio
async def test_read_only_editor_requires_sensitive_read_opt_in(monkeypatch):
    monkeypatch.delenv("SYSTEMS_MANAGER_ALLOW_HOST_MUTATIONS", raising=False)
    monkeypatch.delenv("SYSTEMS_MANAGER_ALLOW_SENSITIVE_READS", raising=False)
    middleware = SystemsSecurityMiddleware()
    with pytest.raises(PermissionError, match="Sensitive host reads"):
        await middleware.on_call_tool(
            _Context(
                "sm_file_operations",
                {"action": "manage_file", "file_action": "read"},
            ),
            _allowed,
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("tool", "arguments"),
    [
        ("sm_system_operations", {"action": "get_env_var"}),
        ("sm_network_operations", {"action": "ping_host"}),
    ],
)
async def test_sensitive_reads_and_network_probes_are_default_deny(
    monkeypatch, tool, arguments
):
    monkeypatch.delenv("SYSTEMS_MANAGER_ALLOW_SENSITIVE_READS", raising=False)
    monkeypatch.delenv("SYSTEMS_MANAGER_ALLOW_NETWORK_PROBES", raising=False)
    with pytest.raises(PermissionError):
        await SystemsSecurityMiddleware().on_call_tool(
            _Context(tool, arguments), _allowed
        )


def test_environment_values_are_never_returned(monkeypatch):
    monkeypatch.setenv("SYSTEMS_MANAGER_ENV_METADATA_ALLOWLIST", "SAFE_SETTING")
    monkeypatch.setenv("SAFE_SETTING", "private-value")
    result = SystemsManagerBase.__dict__["get_env_var"]

    class _Instance:
        pass

    metadata = result(_Instance(), "SAFE_SETTING")
    assert metadata["configured"] is True
    assert "value" not in metadata
    assert "private-value" not in repr(metadata)


@pytest.fixture
def firewall_rule() -> FirewallRuleSpec:
    return FirewallRuleSpec(
        name="agent-ssh",
        action="allow",
        direction="in",
        protocol="tcp",
        port=22,
        source="192.0.2.15/24",
        destination="198.51.100.4/32",
    )


@pytest.mark.parametrize("backend", ["ufw", "firewalld", "iptables", "netsh"])
@pytest.mark.parametrize(
    "legacy_rule",
    [
        "allow 22/tcp",
        "-A INPUT --modprobe=/tmp/pwn",
        "--add-port=22/tcp --panic-on",
        "name=all dir=in action=allow",
    ],
)
def test_legacy_firewall_strings_are_rejected(backend, legacy_rule):
    with pytest.raises(TypeError, match="structured objects"):
        _validated_firewall_args(legacy_rule, backend=backend, remove=False)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("name", "all"),
        ("name", "safe --panic-on"),
        ("protocol", "all"),
        ("port", 0),
        ("source", "192.0.2.1 --modprobe=/tmp/pwn"),
    ],
)
def test_firewall_model_rejects_semantic_injection(field, value):
    payload = {
        "name": "agent-ssh",
        "action": "allow",
        "protocol": "tcp",
        "port": 22,
        field: value,
    }
    with pytest.raises(ValidationError):
        FirewallRuleSpec.model_validate(payload)


def test_firewall_model_forbids_unknown_options():
    with pytest.raises(ValidationError):
        FirewallRuleSpec.model_validate(
            {
                "name": "agent-ssh",
                "action": "allow",
                "protocol": "tcp",
                "port": 22,
                "panic_on": True,
            }
        )


def test_firewall_generates_exact_ufw_argv(firewall_rule):
    assert _validated_firewall_args(firewall_rule, backend="ufw", remove=False) == [
        "allow",
        "in",
        "proto",
        "tcp",
        "from",
        "192.0.2.0/24",
        "to",
        "198.51.100.4/32",
        "port",
        "22",
        "comment",
        "agent-ssh",
    ]


def test_firewall_generates_exact_firewalld_argv(firewall_rule):
    assert _validated_firewall_args(
        firewall_rule, backend="firewalld", remove=False
    ) == [
        '--add-rich-rule=rule family="ipv4" source address="192.0.2.0/24" '
        'destination address="198.51.100.4/32" port port="22" '
        'protocol="tcp" accept'
    ]


def test_firewall_generates_exact_iptables_argv(firewall_rule):
    arguments = _validated_firewall_args(
        firewall_rule, backend="iptables", remove=False
    )
    assert arguments == [
        "-A",
        "INPUT",
        "-p",
        "tcp",
        "-m",
        "tcp",
        "--dport",
        "22",
        "-s",
        "192.0.2.0/24",
        "-d",
        "198.51.100.4/32",
        "-m",
        "comment",
        "--comment",
        "agent-ssh",
        "-j",
        "ACCEPT",
    ]
    assert "--modprobe" not in arguments


def test_firewall_generates_exact_netsh_delete_argv(firewall_rule):
    assert _validated_firewall_args(firewall_rule, backend="netsh", remove=True) == [
        "name=agent-ssh",
        "dir=in",
        "protocol=TCP",
        "localport=22",
        "localip=198.51.100.4/32",
        "remoteip=192.0.2.0/24",
    ]


def test_apt_upgrade_inventory_does_not_refresh_metadata():
    manager = AptManager(silent=True)
    manager.run_command = Mock(
        return_value={"success": True, "stdout": "Listing...\nlinux/stable 1 amd64"}
    )
    result = manager.list_upgradable_packages()
    assert result["success"] is True
    manager.run_command.assert_called_once_with(
        ["apt", "list", "--upgradable"], capture_output=True
    )


def test_dnf_install_does_not_upgrade_the_system():
    manager = DnfManager(silent=True)
    manager.run_command = Mock(return_value={"success": True, "stderr": ""})
    result = manager.install_applications(["curl"])
    assert result["success"] is True
    manager.run_command.assert_called_once_with(
        ["dnf", "install", "-y", "--", "curl"],
        elevated=True,
        capture_output=True,
    )


def test_apt_clean_never_installs_trash_cli():
    manager = AptManager(silent=True)
    manager.run_command = Mock(
        return_value={"success": False, "error": "Executable unavailable"}
    )
    result = manager.clean()
    assert result["success"] is False
    manager.run_command.assert_called_once_with(["trash-empty"])


def test_snap_fallback_never_bootstraps_snapd(monkeypatch):
    manager = AptManager(silent=True)
    manager.run_command = Mock()
    manager.install_snapd = Mock()
    monkeypatch.setattr(systems_module.shutil, "which", lambda _name: None)
    result = manager.install_via_snap("example")
    assert result["success"] is False
    assert result["prerequisite"] == "snapd"
    manager.install_snapd.assert_not_called()
    manager.run_command.assert_not_called()


def test_python_install_does_not_upgrade_pip_as_hidden_side_effect():
    manager = AptManager(silent=True)
    manager.run_command = Mock(return_value={"success": True})
    result = manager.install_python_modules(["example==1.2.3"])
    assert result["success"] is True
    assert result["upgraded_pip"] is False
    manager.run_command.assert_called_once_with(
        [
            "python",
            "-m",
            "pip",
            "install",
            "--upgrade",
            "--",
            "example==1.2.3",
        ]
    )


def test_filesystem_search_has_global_entry_budget(monkeypatch, tmp_path):
    root = tmp_path / "managed"
    root.mkdir()
    for index in range(10):
        (root / f"file-{index}.txt").write_text("data", encoding="utf-8")
    monkeypatch.setenv("SYSTEMS_MANAGER_FILESYSTEM_ROOT", str(root))
    monkeypatch.setattr(systems_module, "_MAX_FILESYSTEM_VISITED_ENTRIES", 3)
    result = FileSystemManager(_Manager()).search_files(".", "absent")
    assert result["success"] is True
    assert result["truncated"] is True
    assert result["visited_entries"] == 3


def test_grep_streams_long_lines_into_bounded_response(monkeypatch, tmp_path):
    root = tmp_path / "managed"
    root.mkdir()
    (root / "long.txt").write_bytes(b"x" * 256 + b"needle\n")
    monkeypatch.setenv("SYSTEMS_MANAGER_FILESYSTEM_ROOT", str(root))
    monkeypatch.setattr(systems_module, "_MAX_GREP_LINE_BYTES", 32)
    monkeypatch.setattr(systems_module, "_MAX_FILESYSTEM_RESPONSE_BYTES", 128)
    result = FileSystemManager(_Manager()).grep_files(".", "needle")
    assert result["success"] is True
    assert result["truncated"] is True
    assert len(result["matches"].encode()) <= 128


def test_cli_main_delegates_to_existing_cli(monkeypatch):
    cli = Mock()
    monkeypatch.setattr(systems_module, "systems_manager", cli)
    systems_module.main()
    cli.assert_called_once_with()
