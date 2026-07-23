#!/usr/bin/env python
import argparse
import base64
import hashlib
import ipaddress
import json
import logging
import os
import platform
import re
import shutil
import signal
import socket
import stat
import subprocess
import sys
import tempfile
import threading
import time
from abc import ABC, abstractmethod
from collections import deque
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlsplit

import distro
import psutil
from agent_utilities.core.config import setting
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from systems_manager.k8s_detect import is_k8s_node

__version__ = "2.0.0"

_MAX_MANAGED_FILE_BYTES = 8 * 1024 * 1024
_MAX_LOCAL_PACKAGE_BYTES = 2 * 1024 * 1024 * 1024
_MAX_FILESYSTEM_RESULTS = 10_000
_MAX_FILESYSTEM_VISITED_ENTRIES = 50_000
_MAX_FILESYSTEM_SCAN_BYTES = 64 * 1024 * 1024
_MAX_FILESYSTEM_RESPONSE_BYTES = 1024 * 1024
_MAX_GREP_LINE_BYTES = 16 * 1024
_MAX_FILESYSTEM_SCAN_SECONDS = 5.0
_MAX_COMMAND_ARGS = 128
_MAX_COMMAND_ARG_BYTES = 4_096
_MAX_COMMAND_BYTES = 32_768
_MAX_COMMAND_OUTPUT_BYTES = 64 * 1024
_DEFAULT_COMMAND_TIMEOUT_SECONDS = 120
_MAX_COMMAND_TIMEOUT_SECONDS = 3_600
_COMMAND_TERMINATION_GRACE_SECONDS = 3
_LONG_RUNNING_EXECUTABLES = frozenset(
    {
        "apt",
        "apt-get",
        "cleanmgr",
        "cleanmgr.exe",
        "dnf",
        "dpkg",
        "pacman",
        "snap",
        "uv",
        "winget",
        "winget.exe",
        "zypper",
    }
)
_MANAGED_EXECUTABLES = frozenset(
    {
        "add-apt-repository",
        "apt",
        "apt-cache",
        "apt-get",
        "bash",
        "cleanmgr",
        "cleanmgr.exe",
        "crontab",
        "dnf",
        "dpkg",
        "fc-cache",
        "firewall-cmd",
        "git",
        "iptables",
        "journalctl",
        "ln",
        "netsh",
        "netsh.exe",
        "netstat",
        "pacman",
        "ping",
        "ping.exe",
        "powershell",
        "powershell.exe",
        "python",
        "python.exe",
        "schtasks",
        "schtasks.exe",
        "shutdown.exe",
        "snap",
        "ss",
        "ssh-keygen",
        "systemctl",
        "trash-empty",
        "ufw",
        "uv",
        "winget",
        "winget.exe",
        "zypper",
    }
)
_CHILD_ENV_ALLOWLIST = frozenset(
    {
        "HOME",
        "HTTPS_PROXY",
        "HTTP_PROXY",
        "LANG",
        "LC_ALL",
        "NO_PROXY",
        "PATH",
        "REQUESTS_CA_BUNDLE",
        "SSL_CERT_FILE",
        "SYSTEMDRIVE",
        "SYSTEMROOT",
        "TEMP",
        "TMP",
        "TMPDIR",
        "USERPROFILE",
        "UV_NATIVE_TLS",
        "WINDIR",
    }
)


def _validated_timeout_seconds(
    argv: list[str] | tuple[str, ...] | None = None,
    requested: int | None = None,
) -> int:
    """Return a bounded deadline selected for the operation being executed."""
    if requested is not None:
        if isinstance(requested, bool) or not isinstance(requested, int):
            raise ValueError("Managed command timeout must be an integer")
        return max(1, min(requested, _MAX_COMMAND_TIMEOUT_SECONDS))
    executable = Path(argv[0]).name.casefold() if argv else ""
    is_python_install = bool(
        argv
        and executable.startswith("python")
        and list(argv[1:4]) == ["-m", "pip", "install"]
    )
    default = (
        1_800
        if executable in _LONG_RUNNING_EXECUTABLES or is_python_install
        else _DEFAULT_COMMAND_TIMEOUT_SECONDS
    )
    raw = setting("SYSTEMS_MANAGER_COMMAND_TIMEOUT_SECONDS", default)
    try:
        value = int(raw)
    except (TypeError, ValueError):
        value = default
    return max(1, min(value, _MAX_COMMAND_TIMEOUT_SECONDS))


def _validated_command_argv(command: list[str] | tuple[str, ...]) -> list[str]:
    """Validate a fixed argv vector and reject arbitrary executables."""
    if not isinstance(command, (list, tuple)) or not command:
        raise ValueError("A non-empty argument vector is required")
    if len(command) > _MAX_COMMAND_ARGS:
        raise ValueError("Managed command argument limit exceeded")
    argv: list[str] = []
    total = 0
    for argument in command:
        if not isinstance(argument, str) or "\x00" in argument:
            raise ValueError("Managed command contains an invalid argument")
        encoded = argument.encode("utf-8")
        if not encoded or len(encoded) > _MAX_COMMAND_ARG_BYTES:
            raise ValueError("Managed command argument size limit exceeded")
        total += len(encoded)
        argv.append(argument)
    if total > _MAX_COMMAND_BYTES:
        raise ValueError("Managed command size limit exceeded")

    supplied_executable = Path(argv[0])
    executable = supplied_executable.name.casefold()
    python_executable = Path(sys.executable).name.casefold()
    if supplied_executable != Path(supplied_executable.name):
        try:
            is_current_python = supplied_executable.resolve(strict=True) == Path(
                sys.executable
            ).resolve(strict=True)
        except OSError:
            is_current_python = False
        if not is_current_python:
            raise PermissionError("Caller-supplied executable paths are not permitted")
    if executable not in _MANAGED_EXECUTABLES and executable != python_executable:
        if not re.fullmatch(r"python(?:\d+(?:\.\d+)*)?(?:\.exe)?", executable):
            raise PermissionError("Executable is outside the managed allowlist")
    _validate_interpreter_policy(argv, executable)
    return argv


def _validate_interpreter_policy(argv: list[str], executable: str) -> None:
    """Constrain interpreter-capable executables to fixed internal programs."""
    if executable == "bash":
        if (
            len(argv) != 6
            or argv[1] != "-c"
            or argv[2]
            not in {
                'source "$1"; nvm install "$2"',
                'source "$1"; nvm use "$2"',
            }
            or argv[3] != "nvm"
            or resolve_managed_path(argv[4], must_exist=True).name != "nvm.sh"
        ):
            raise PermissionError("Bash program is outside the managed allowlist")
        return

    if executable.startswith("python"):
        if len(argv) < 5 or argv[1:3] != ["-m", "pip"] or argv[3] != "install":
            raise PermissionError("Python program is outside the managed allowlist")
        return

    if executable not in {"powershell", "powershell.exe"}:
        return
    if len(argv) == 6 and argv[1] in {
        "Enable-WindowsOptionalFeature",
        "Disable-WindowsOptionalFeature",
    }:
        if (
            argv[2] == "-Online"
            and argv[3] == "-FeatureName"
            and argv[5] == "-NoRestart"
        ):
            if re.fullmatch(r"[A-Za-z0-9_.@:-]{1,256}", argv[4]):
                return
    if argv[1:4] != ["-NoProfile", "-NonInteractive", "-Command"] or len(argv) != 5:
        raise PermissionError("PowerShell program is outside the managed allowlist")
    script = argv[4]
    fixed_scripts = {
        "Get-Service | Select-Object Name,Status,DisplayName | ConvertTo-Json -Depth 3",
        "Get-LocalUser | Select-Object Name,Enabled | ConvertTo-Json -Depth 3",
        "Get-LocalGroup | Select-Object Name | ConvertTo-Json -Depth 3",
        "Get-NetFirewallRule | Select-Object Name,DisplayName,Enabled,Direction,Action | ConvertTo-Json -Depth 3",
        "Get-WindowsOptionalFeature -Online | ConvertTo-Json -Depth 3",
        "Optimize-Volume -DriveLetter C",
        r"Remove-Item -Path $env:LOCALAPPDATA\Packages\Microsoft.DesktopAppInstaller_*\LocalState\DiagOutputDir\* -Recurse -Force -ErrorAction SilentlyContinue",
    }
    if script in fixed_scripts:
        return
    service = r"[A-Za-z0-9_.@:-]{1,256}"
    permitted_patterns = {
        rf"Get-Service -Name '{service}' \| Select-Object Name,Status,DisplayName,StartType \| ConvertTo-Json",
        rf"Start-Service -Name '{service}'",
        rf"Stop-Service -Name '{service}' -Force",
        rf"Restart-Service -Name '{service}' -Force",
        rf"Set-Service -Name '{service}' -StartupType (?:Automatic|Disabled)",
        r"Get-EventLog -LogName System -Newest (?:[1-9]\d{0,2}|1000) \| Format-List \| Out-String",
    }
    if not any(re.fullmatch(pattern, script) for pattern in permitted_patterns):
        raise PermissionError("PowerShell program is outside the managed allowlist")


def _bounded_stream_reader(stream, output: bytearray, limit: int) -> None:
    """Drain a child stream while retaining only a bounded prefix."""
    try:
        try:
            while True:
                chunk = stream.read(8_192)
                if not chunk:
                    break
                remaining = limit - len(output)
                if remaining > 0:
                    output.extend(chunk[:remaining])
        except (OSError, ValueError):
            return
    finally:
        try:
            stream.close()
        except OSError:
            pass


def _trusted_search_directories() -> tuple[Path, ...]:
    """Return administrator-controlled executable directories for this platform."""
    if os.name == "nt":
        windows = Path(os.environ.get("SYSTEMROOT", r"C:\Windows"))
        local_app_data = Path(os.environ.get("LOCALAPPDATA", ""))
        directories = (
            windows / "System32",
            windows,
            local_app_data / "Microsoft" / "WindowsApps",
        )
    else:
        directories = tuple(
            Path(path)
            for path in (
                "/usr/local/sbin",
                "/usr/local/bin",
                "/usr/sbin",
                "/usr/bin",
                "/sbin",
                "/bin",
                str(Path(sys.executable).resolve().parent),
            )
        )
    return tuple(dict.fromkeys(directories))


def _path_is_trusted_executable(path: Path) -> bool:
    """Check executable type, ownership, and writable ancestors on POSIX."""
    try:
        resolved = path.resolve(strict=True)
        if not resolved.is_file():
            return False
        if os.name == "nt":
            attributes = getattr(resolved.stat(), "st_file_attributes", 0)
            reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
            if attributes & reparse_flag:
                return False
            windows = Path(os.environ.get("SYSTEMROOT", r"C:\Windows")).resolve()
            program_files = Path(
                os.environ.get("PROGRAMFILES", r"C:\Program Files")
            ).resolve()
            trusted_roots = (windows, program_files / "WindowsApps")
            return any(
                resolved == root or resolved.is_relative_to(root)
                for root in trusted_roots
            )

        effective_uid = os.geteuid() if hasattr(os, "geteuid") else None
        permitted_owners = {0}
        if effective_uid is not None:
            permitted_owners.add(effective_uid)
        current = resolved
        while True:
            metadata = current.stat()
            if metadata.st_uid not in permitted_owners:
                return False
            if metadata.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
                return False
            if current.parent == current:
                break
            current = current.parent
        return os.access(resolved, os.X_OK)
    except OSError:
        return False


def _resolve_trusted_executable(executable: str) -> str:
    """Resolve an allowlisted basename without consulting the inherited PATH."""
    supplied = Path(executable)
    if supplied != Path(supplied.name):
        try:
            current_python = Path(sys.executable).resolve(strict=True)
            resolved = supplied.resolve(strict=True)
        except OSError as exc:
            raise PermissionError("Executable path is not trusted") from exc
        if resolved != current_python or not resolved.is_file():
            raise PermissionError("Executable path is not trusted")
        return str(resolved)

    names = [supplied.name]
    if os.name == "nt" and not supplied.suffix:
        names.append(f"{supplied.name}.exe")
    for directory in _trusted_search_directories():
        for name in names:
            candidate = directory / name
            if _path_is_trusted_executable(candidate):
                return str(candidate.resolve(strict=True))
    raise FileNotFoundError("Managed executable is not installed in a trusted location")


def _terminate_process_tree(
    process: subprocess.Popen,
    *,
    grace_seconds: int = _COMMAND_TERMINATION_GRACE_SECONDS,
) -> int:
    """Gracefully terminate a child tree, then force-kill survivors."""
    if process.poll() is not None:
        return int(process.returncode)

    if os.name != "nt":
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            process.terminate()
        try:
            return process.wait(timeout=grace_seconds)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                process.kill()
            return process.wait(timeout=grace_seconds)

    try:
        parent = psutil.Process(process.pid)
        descendants = parent.children(recursive=True)
        for child in descendants:
            child.terminate()
        parent.terminate()
        _, alive = psutil.wait_procs([*descendants, parent], timeout=grace_seconds)
        for survivor in alive:
            survivor.kill()
        if alive:
            psutil.wait_procs(alive, timeout=grace_seconds)
    except (psutil.Error, OSError):
        process.terminate()
    try:
        return process.wait(timeout=grace_seconds)
    except subprocess.TimeoutExpired:
        process.kill()
        return process.wait(timeout=grace_seconds)


def _minimal_child_environment(
    overrides: dict[str, str] | None = None,
) -> dict[str, str]:
    environment = {
        key: value
        for key, value in os.environ.items()
        if key.upper() in _CHILD_ENV_ALLOWLIST
    }
    environment["PATH"] = os.pathsep.join(
        str(path) for path in _trusted_search_directories()
    )
    for key, value in (overrides or {}).items():
        if key not in {"VIRTUAL_ENV"}:
            raise PermissionError("Child environment override is not permitted")
        if not isinstance(value, str) or "\x00" in value or len(value) > 4_096:
            raise ValueError("Invalid child environment override")
        environment[key] = value
    return environment


def _validated_package_name(value: str) -> str:
    candidate = value.strip()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9+._:@-]{0,255}", candidate):
        raise ValueError("Invalid package identifier")
    return candidate


def _validated_package_names(values: list[str]) -> list[str]:
    if not isinstance(values, list) or not values or len(values) > 64:
        raise ValueError("Package list must contain between 1 and 64 items")
    return [_validated_package_name(value) for value in values]


def _validated_search_query(value: str) -> str:
    candidate = value.strip()
    if (
        not candidate
        or candidate.startswith("-")
        or len(candidate) > 256
        or any(character in candidate for character in ("\x00", "\n", "\r"))
    ):
        raise ValueError("Invalid package search query")
    return candidate


def _validated_local_package(path: str, suffixes: tuple[str, ...]) -> Path:
    candidate = resolve_managed_path(path, must_exist=True)
    if (
        not candidate.is_file()
        or candidate.is_symlink()
        or candidate.stat().st_size > _MAX_LOCAL_PACKAGE_BYTES
        or not candidate.name.casefold().endswith(suffixes)
    ):
        raise ValueError("Invalid local package artifact")
    raw_digests = str(setting("SYSTEMS_MANAGER_LOCAL_PACKAGE_SHA256_MAP", "")).strip()
    if not raw_digests or len(raw_digests) > 64 * 1024:
        raise PermissionError("A deployment-controlled package digest is required")
    try:
        digest_map = json.loads(raw_digests)
    except json.JSONDecodeError as exc:
        raise ValueError("Local package digest policy is invalid") from exc
    if not isinstance(digest_map, dict) or len(digest_map) > 256:
        raise ValueError("Local package digest policy is invalid")
    artifact_name = managed_display_path(candidate)
    expected = digest_map.get(artifact_name)
    if not isinstance(expected, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", expected):
        raise PermissionError("The local package is not digest-allowlisted")
    digest = hashlib.sha256()
    with candidate.open("rb") as package_file:
        for chunk in iter(lambda: package_file.read(1024 * 1024), b""):
            digest.update(chunk)
    if digest.hexdigest().casefold() != expected.casefold():
        raise ValueError("Local package digest verification failed")
    return candidate


def _validated_repository_name(value: str | None) -> str:
    candidate = (value or "custom").strip()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", candidate):
        raise ValueError("Invalid repository name")
    return candidate


def _validated_python_requirement(value: str) -> str:
    candidate = value.strip()
    if not re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}"
        r"(?:\[[A-Za-z0-9_,.-]{1,128}\])?"
        r"(?:(?:===|==|!=|~=|<=|>=|<|>)[A-Za-z0-9.*+!_-]{1,64})?",
        candidate,
    ):
        raise ValueError("Invalid Python package requirement")
    return candidate


def _validated_repository_url(value: str) -> str:
    candidate = value.strip()
    if len(candidate) > 2_048:
        raise ValueError("Repository URL is too long")
    parsed = urlsplit(candidate)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("Repository URL must be credential-free HTTPS")
    try:
        parsed.hostname.encode("idna")
    except UnicodeError as exc:
        raise ValueError("Invalid repository hostname") from exc
    raw_allowlist = str(
        setting("SYSTEMS_MANAGER_REPOSITORY_ALLOWLIST_JSON", "")
    ).strip()
    if not raw_allowlist or len(raw_allowlist) > 64 * 1024:
        raise PermissionError(
            "A deployment-controlled repository allowlist is required"
        )
    try:
        allowed = json.loads(raw_allowlist)
    except json.JSONDecodeError as exc:
        raise ValueError("Repository allowlist is invalid") from exc
    if (
        not isinstance(allowed, list)
        or len(allowed) > 256
        or not all(isinstance(item, str) for item in allowed)
    ):
        raise ValueError("Repository allowlist is invalid")
    if candidate not in allowed:
        raise PermissionError("Repository URL is not allowlisted")
    return candidate


def _validated_account_name(value: str | None) -> str | None:
    if value in {None, ""}:
        return None
    candidate = value.strip()
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.-]{0,63}", candidate):
        raise ValueError("Invalid account name")
    return candidate


def _validated_host(value: str) -> str:
    candidate = value.strip().rstrip(".")
    if not candidate or len(candidate) > 253 or candidate.startswith("-"):
        raise ValueError("Invalid host")
    try:
        return str(ipaddress.ip_address(candidate))
    except ValueError:
        pass
    try:
        encoded = candidate.encode("idna").decode("ascii")
    except UnicodeError as exc:
        raise ValueError("Invalid host") from exc
    if any(
        not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?", label)
        for label in encoded.split(".")
    ):
        raise ValueError("Invalid host")
    return encoded


class FirewallRuleSpec(BaseModel):
    """A backend-neutral, injection-safe firewall rule."""

    model_config = ConfigDict(extra="forbid", strict=True)

    name: str = Field(
        min_length=1,
        max_length=64,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,63}$",
        description="Stable rule identifier; the reserved value 'all' is forbidden",
    )
    action: Literal["allow", "deny"] = Field(description="Rule decision")
    direction: Literal["in", "out"] = Field(
        default="in", description="Packet direction"
    )
    protocol: Literal["tcp", "udp"] = Field(description="Transport protocol")
    port: int = Field(ge=1, le=65_535, description="Destination transport port")
    source: str | None = Field(
        default=None, description="Optional canonical source IPv4/IPv6 network"
    )
    destination: str | None = Field(
        default=None, description="Optional canonical destination IPv4/IPv6 network"
    )

    @field_validator("name")
    @classmethod
    def _name_is_not_wildcard(_cls, value: str) -> str:
        if value.casefold() == "all":
            raise ValueError("The wildcard firewall rule name is forbidden")
        return value

    @field_validator("source", "destination")
    @classmethod
    def _canonical_network(_cls, value: str | None) -> str | None:
        if value is None:
            return None
        try:
            return str(ipaddress.ip_network(value, strict=False))
        except ValueError as exc:
            raise ValueError("Invalid firewall network") from exc

    @model_validator(mode="after")
    def _networks_use_same_address_family(self) -> "FirewallRuleSpec":
        networks = [
            ipaddress.ip_network(value)
            for value in (self.source, self.destination)
            if value is not None
        ]
        if len({network.version for network in networks}) > 1:
            raise ValueError("Firewall networks must use the same address family")
        return self


def _coerce_firewall_rule(
    rule: FirewallRuleSpec | dict[str, Any],
) -> FirewallRuleSpec:
    """Validate a structured rule; command strings are not accepted."""
    if isinstance(rule, FirewallRuleSpec):
        return rule
    if not isinstance(rule, dict):
        raise TypeError("Firewall rules must be structured objects")
    return FirewallRuleSpec.model_validate(rule)


def _validated_firewall_args(
    rule: FirewallRuleSpec | dict[str, Any], *, backend: str, remove: bool
) -> list[str]:
    """Generate an exact argv suffix for a supported firewall backend."""
    spec = _coerce_firewall_rule(rule)
    port = str(spec.port)
    source = spec.source or "any"
    destination = spec.destination or "any"

    if backend == "ufw":
        return [
            spec.action,
            spec.direction,
            "proto",
            spec.protocol,
            "from",
            source,
            "to",
            destination,
            "port",
            port,
            "comment",
            spec.name,
        ]

    if backend == "firewalld":
        if spec.direction != "in":
            raise ValueError("firewalld outbound rules require a separate policy API")
        networks = [
            ipaddress.ip_network(value)
            for value in (spec.source, spec.destination)
            if value is not None
        ]
        family = f' family="ipv{networks[0].version}"' if networks else ""
        source_clause = f' source address="{spec.source}"' if spec.source else ""
        destination_clause = (
            f' destination address="{spec.destination}"' if spec.destination else ""
        )
        verdict = "accept" if spec.action == "allow" else "drop"
        rich_rule = (
            f"rule{family}{source_clause}{destination_clause}"
            f' port port="{port}" protocol="{spec.protocol}" {verdict}'
        )
        operation = "--remove-rich-rule=" if remove else "--add-rich-rule="
        return [f"{operation}{rich_rule}"]

    if backend == "iptables":
        networks = [
            ipaddress.ip_network(value)
            for value in (spec.source, spec.destination)
            if value is not None
        ]
        if any(network.version != 4 for network in networks):
            raise ValueError("IPv6 firewall rules require an ip6tables-specific API")
        arguments = [
            "-D" if remove else "-A",
            "INPUT" if spec.direction == "in" else "OUTPUT",
            "-p",
            spec.protocol,
            "-m",
            spec.protocol,
            "--dport",
            port,
        ]
        if spec.source:
            arguments.extend(["-s", spec.source])
        if spec.destination:
            arguments.extend(["-d", spec.destination])
        arguments.extend(
            [
                "-m",
                "comment",
                "--comment",
                spec.name,
                "-j",
                "ACCEPT" if spec.action == "allow" else "DROP",
            ]
        )
        return arguments

    if backend == "netsh":
        local_ip = destination if spec.direction == "in" else source
        remote_ip = source if spec.direction == "in" else destination
        port_field = "localport" if spec.direction == "in" else "remoteport"
        arguments = [
            f"name={spec.name}",
            f"dir={spec.direction}",
            f"protocol={spec.protocol.upper()}",
            f"{port_field}={port}",
            f"localip={local_ip}",
            f"remoteip={remote_ip}",
        ]
        if not remove:
            arguments.insert(
                2, f"action={'allow' if spec.action == 'allow' else 'block'}"
            )
        return arguments

    raise ValueError("Unsupported firewall backend")


def _opaque_ref(namespace: str, value: str) -> str:
    digest = hashlib.sha256(f"{namespace}\x00{value}".encode()).hexdigest()
    return f"{namespace}:{digest[:16]}"


def _parse_package_metadata(output: str) -> dict[str, str]:
    allowed = {
        "architecture",
        "description",
        "license",
        "name",
        "package",
        "summary",
        "version",
    }
    metadata: dict[str, str] = {}
    for line in output.splitlines()[:1_000]:
        key, separator, value = line.partition(":")
        normalized = key.strip().casefold()
        if separator and normalized in allowed and normalized not in metadata:
            metadata[normalized] = value.strip()[:2_048]
    return metadata


def _parse_package_table(output: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for line in output.splitlines()[:2_000]:
        fields = [field.strip() for field in re.split(r"\s{2,}", line.strip())]
        if (
            len(fields) < 2
            or set(line.strip()) <= {"-", " "}
            or fields[0].casefold() in {"name", "package"}
        ):
            continue
        rows.append(
            {
                "name": fields[0][:256],
                "identifier": fields[1][:256],
                **({"version": fields[2][:128]} if len(fields) > 2 else {}),
            }
        )
        if len(rows) >= 1_000:
            break
    return rows


def managed_filesystem_root() -> Path:
    """Return the administrator-selected root for all MCP filesystem access."""
    configured = str(setting("SYSTEMS_MANAGER_FILESYSTEM_ROOT", "")).strip()
    if not configured:
        raise PermissionError(
            "SYSTEMS_MANAGER_FILESYSTEM_ROOT must explicitly select a data directory"
        )
    candidate = Path(configured).expanduser()
    if not candidate.is_absolute():
        raise ValueError("Managed filesystem root must be an absolute path")
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    for component in (candidate, *candidate.parents):
        try:
            component_metadata = component.lstat()
        except OSError:
            continue
        if component.is_symlink() or (
            os.name == "nt"
            and getattr(component_metadata, "st_file_attributes", 0) & reparse_flag
        ):
            raise PermissionError(
                "Managed filesystem root cannot traverse links or reparse points"
            )
    try:
        root = candidate.resolve(strict=True)
        metadata = root.stat()
    except OSError as exc:
        raise FileNotFoundError("Managed filesystem root does not exist") from exc
    if root == Path(root.anchor):
        raise PermissionError("Managed filesystem root cannot be a volume root")
    if not root.is_dir():
        raise ValueError("Managed filesystem root must be a directory")
    if os.name == "nt":
        attributes = getattr(metadata, "st_file_attributes", 0)
        if attributes & reparse_flag:
            raise PermissionError("Managed filesystem root cannot be a reparse point")
    else:
        effective_uid = os.geteuid() if hasattr(os, "geteuid") else metadata.st_uid
        if metadata.st_uid != effective_uid:
            raise PermissionError("Managed filesystem root has an untrusted owner")
        if metadata.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
            raise PermissionError(
                "Managed filesystem root cannot be group/world writable"
            )
    return root


def resolve_managed_path(path: str, *, must_exist: bool = False) -> Path:
    """Resolve ``path`` inside the managed root and reject escapes/symlinks.

    Relative paths are interpreted relative to the managed root, never the
    process' ambient working directory. Resolving before the containment check
    also prevents a symlink inside the root from reaching host files outside it.
    """
    root = managed_filesystem_root()
    candidate = Path(path).expanduser()
    if not candidate.is_absolute():
        candidate = root / candidate
    resolved = candidate.resolve(strict=False)
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise PermissionError("Path is outside the managed filesystem root") from exc
    if must_exist and not resolved.exists():
        raise FileNotFoundError("Managed path does not exist")
    return resolved


def managed_display_path(path: Path) -> str:
    """Return a portable, non-identifying path relative to the managed root."""
    relative = path.relative_to(managed_filesystem_root())
    return "." if not relative.parts else relative.as_posix()


def atomic_write_managed_text(
    path: Path | str,
    payload: str,
    *,
    create: bool = False,
) -> Path:
    """Write a bounded text file beneath the managed root without following links."""
    if len(payload.encode("utf-8")) > _MAX_MANAGED_FILE_BYTES:
        raise ValueError("Managed file size limit exceeded")
    target = resolve_managed_path(str(path))
    target.parent.mkdir(parents=True, exist_ok=True)
    target = resolve_managed_path(str(target))
    if target.is_symlink():
        raise PermissionError("Symbolic-link file operations are not permitted")
    if create:
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(target, flags, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        return target
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=target.parent,
        prefix=".systems-manager-",
        delete=False,
    ) as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
        temporary = Path(handle.name)
    try:
        temporary.chmod(0o600)
        if target.is_symlink():
            raise PermissionError("Symbolic-link file operations are not permitted")
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)
    return target


def setup_logging():
    """Configure metadata-only stderr logging without persistent host data."""
    logger = logging.getLogger(__name__)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(logging.Formatter("%(levelname)s %(message)s"))
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    logger.info("Systems manager logging initialized")
    return logger


class _FilesystemScanBudget:
    """Shared global limits for one filesystem request."""

    def __init__(self) -> None:
        self.visited_entries = 0
        self.scanned_bytes = 0
        self.response_bytes = 0
        self.deadline = time.monotonic() + _MAX_FILESYSTEM_SCAN_SECONDS
        self.truncated = False

    def consume_entry(self) -> bool:
        if (
            self.visited_entries >= _MAX_FILESYSTEM_VISITED_ENTRIES
            or time.monotonic() >= self.deadline
        ):
            self.truncated = True
            return False
        self.visited_entries += 1
        return True

    def consume_scan_bytes(self, amount: int) -> bool:
        if amount < 0 or self.scanned_bytes + amount > _MAX_FILESYSTEM_SCAN_BYTES:
            self.truncated = True
            return False
        self.scanned_bytes += amount
        return True

    def consume_response(self, value: str) -> bool:
        size = len(value.encode("utf-8", errors="replace")) + 1
        if self.response_bytes + size > _MAX_FILESYSTEM_RESPONSE_BYTES:
            self.truncated = True
            return False
        self.response_bytes += size
        return True


def _iter_managed_files(
    base: Path, budget: _FilesystemScanBudget, *, recursive: bool = True
) -> Iterator[Path]:
    """Yield files without following links and with a request-global entry budget."""
    if base.is_file() and not base.is_symlink():
        if budget.consume_entry():
            yield base
        return

    managed_root = managed_filesystem_root()
    pending = [base]
    while pending and not budget.truncated:
        directory = pending.pop()
        try:
            with os.scandir(directory) as entries:
                for entry in entries:
                    if not budget.consume_entry():
                        return
                    try:
                        if entry.is_symlink():
                            continue
                        candidate = Path(entry.path).resolve(strict=True)
                        candidate.relative_to(managed_root)
                        if recursive and entry.is_dir(follow_symlinks=False):
                            pending.append(candidate)
                        elif entry.is_file(follow_symlinks=False):
                            yield candidate
                    except (OSError, ValueError):
                        continue
        except OSError:
            continue


class FileSystemManager:
    def __init__(self, manager):
        self.manager = manager
        self.logger = manager.logger

    def list_files(
        self, path: str = ".", recursive: bool = False, depth: int = 1
    ) -> dict:
        try:
            depth = max(1, min(int(depth), 32))
            expanded_path = resolve_managed_path(path, must_exist=True)
            if not expanded_path.is_dir():
                return {"success": False, "error": "Managed path is not a directory"}

            items: list[dict[str, str]] = []
            budget = _FilesystemScanBudget()
            managed_root = managed_filesystem_root()
            pending = [(expanded_path, 0)]
            while pending and not budget.truncated:
                directory, current_depth = pending.pop()
                try:
                    entries = os.scandir(directory)
                except OSError:
                    continue
                with entries:
                    for entry in entries:
                        if not budget.consume_entry():
                            break
                        try:
                            if entry.is_symlink():
                                continue
                            entry_path = Path(entry.path).resolve(strict=True)
                            entry_path.relative_to(managed_root)
                            is_directory = entry.is_dir(follow_symlinks=False)
                        except (OSError, ValueError):
                            continue
                        item_type = "directory" if is_directory else "file"
                        display = managed_display_path(entry_path)
                        if not budget.consume_response(
                            f"{entry.name}\x00{item_type}\x00{display}"
                        ):
                            break
                        items.append(
                            {
                                "name": entry.name,
                                "type": item_type,
                                "path": display,
                            }
                        )
                        if len(items) >= _MAX_FILESYSTEM_RESULTS:
                            budget.truncated = True
                            break
                        if recursive and is_directory and current_depth + 1 < depth:
                            pending.append((entry_path, current_depth + 1))
                if not recursive:
                    break
            return {
                "success": True,
                "path": managed_display_path(expanded_path),
                "items": items,
                "total": len(items),
                "truncated": budget.truncated,
                "visited_entries": budget.visited_entries,
            }
        except (PermissionError, FileNotFoundError, ValueError):
            return {"success": False, "error": "Operation failed"}
        except Exception as e:
            return {"success": False, "error": type(e).__name__}

    def search_files(self, path: str, pattern: str) -> dict:
        try:
            if (
                not pattern
                or len(pattern) > 512
                or any(character in pattern for character in ("\x00", "\n", "\r"))
            ):
                raise ValueError("Invalid search pattern")
            expanded_path = resolve_managed_path(path, must_exist=True)
            budget = _FilesystemScanBudget()
            matches: list[str] = []
            for candidate in _iter_managed_files(expanded_path, budget):
                if pattern not in candidate.name:
                    continue
                display = managed_display_path(candidate)
                if not budget.consume_response(display):
                    break
                matches.append(display)
                if len(matches) >= _MAX_FILESYSTEM_RESULTS:
                    budget.truncated = True
                    break
            return {
                "success": True,
                "matches": matches,
                "total": len(matches),
                "truncated": budget.truncated,
                "visited_entries": budget.visited_entries,
            }
        except (PermissionError, FileNotFoundError, ValueError):
            return {"success": False, "error": "Operation failed"}
        except Exception as e:
            return {"success": False, "error": type(e).__name__}

    def grep_files(self, path: str, pattern: str, recursive: bool = False) -> dict:
        try:
            if (
                not pattern
                or len(pattern) > 4_096
                or any(character in pattern for character in ("\x00", "\n", "\r"))
            ):
                raise ValueError("Invalid search pattern")
            expanded_path = resolve_managed_path(path, must_exist=True)
            budget = _FilesystemScanBudget()
            candidates = _iter_managed_files(expanded_path, budget, recursive=recursive)
            matches: list[str] = []
            encoded_pattern = pattern.encode("utf-8")
            for candidate in candidates:
                try:
                    size = candidate.stat().st_size
                except OSError:
                    continue
                if size > _MAX_MANAGED_FILE_BYTES:
                    budget.truncated = True
                    continue
                if not budget.consume_scan_bytes(size):
                    break
                try:
                    display = managed_display_path(candidate.resolve(strict=True))
                    handle = candidate.open("rb")
                except (OSError, ValueError):
                    continue
                with handle:
                    line_number = 0
                    while True:
                        first_fragment = handle.readline(_MAX_GREP_LINE_BYTES + 1)
                        if not first_fragment:
                            break
                        line_number += 1
                        displayed = first_fragment[:_MAX_GREP_LINE_BYTES]
                        combined_tail = b""
                        matched = False
                        fragment = first_fragment
                        line_truncated = len(first_fragment) > _MAX_GREP_LINE_BYTES
                        while True:
                            searchable = combined_tail + fragment
                            match_offset = searchable.find(encoded_pattern)
                            if not matched and match_offset >= 0:
                                matched = True
                                snippet_start = max(0, match_offset - 256)
                                displayed = searchable[
                                    snippet_start : snippet_start + _MAX_GREP_LINE_BYTES
                                ]
                            tail_length = len(encoded_pattern) - 1
                            combined_tail = (
                                searchable[-tail_length:] if tail_length else b""
                            )
                            if (
                                fragment.endswith(b"\n")
                                or len(fragment) <= _MAX_GREP_LINE_BYTES
                            ):
                                break
                            line_truncated = True
                            fragment = handle.readline(_MAX_GREP_LINE_BYTES + 1)
                            if not fragment:
                                break
                        if line_truncated:
                            budget.truncated = True
                        if matched:
                            line = displayed.rstrip(b"\r\n").decode(
                                "utf-8", errors="replace"
                            )
                            match = f"{display}:{line_number}:{line}"
                            if not budget.consume_response(match):
                                break
                            matches.append(match)
                            if len(matches) >= _MAX_FILESYSTEM_RESULTS:
                                budget.truncated = True
                                break
                if budget.truncated and (
                    len(matches) >= _MAX_FILESYSTEM_RESULTS
                    or budget.response_bytes >= _MAX_FILESYSTEM_RESPONSE_BYTES
                    or budget.scanned_bytes >= _MAX_FILESYSTEM_SCAN_BYTES
                    or time.monotonic() >= budget.deadline
                ):
                    break
            return {
                "success": True,
                "matches": "\n".join(matches),
                "path": managed_display_path(expanded_path),
                "truncated": budget.truncated,
                "visited_entries": budget.visited_entries,
                "scanned_bytes": budget.scanned_bytes,
            }
        except (PermissionError, FileNotFoundError, ValueError):
            return {"success": False, "error": "Operation failed"}
        except Exception as e:
            return {"success": False, "error": type(e).__name__}

    def manage_file(self, action: str, path: str, content: str | None = None) -> dict:
        try:
            if action not in {"create", "update", "delete", "read"}:
                return {"success": False, "error": f"Unknown action: {action}"}
            expanded_path = resolve_managed_path(path)
            display_path = managed_display_path(expanded_path)
            if expanded_path.is_symlink():
                raise PermissionError("Symbolic-link file operations are not permitted")
            if action == "create" or action == "update":
                payload = content or ""
                if len(payload.encode("utf-8")) > _MAX_MANAGED_FILE_BYTES:
                    raise ValueError("Managed file size limit exceeded")
                expanded_path.parent.mkdir(parents=True, exist_ok=True)
                # Re-resolve after creating parents to catch a raced symlink.
                expanded_path = resolve_managed_path(str(expanded_path))
                flags = os.O_WRONLY | os.O_CREAT
                if hasattr(os, "O_NOFOLLOW"):
                    flags |= os.O_NOFOLLOW
                if action == "create":
                    flags |= os.O_EXCL
                    descriptor = os.open(expanded_path, flags, 0o600)
                    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                        handle.write(payload)
                        handle.flush()
                        os.fsync(handle.fileno())
                else:
                    with tempfile.NamedTemporaryFile(
                        mode="w",
                        encoding="utf-8",
                        dir=expanded_path.parent,
                        prefix=".systems-manager-",
                        delete=False,
                    ) as handle:
                        handle.write(payload)
                        handle.flush()
                        os.fsync(handle.fileno())
                        temporary = Path(handle.name)
                    try:
                        temporary.chmod(0o600)
                        if expanded_path.is_symlink():
                            raise PermissionError(
                                "Symbolic-link file operations are not permitted"
                            )
                        os.replace(temporary, expanded_path)
                    finally:
                        temporary.unlink(missing_ok=True)
                return {"success": True, "message": f"File {action}d: {display_path}"}
            elif action == "delete":
                if expanded_path.is_file():
                    expanded_path.unlink()
                    return {"success": True, "message": f"File deleted: {display_path}"}
                return {"success": False, "error": "Managed file not found"}
            elif action == "read":
                if expanded_path.is_file():
                    if expanded_path.stat().st_size > _MAX_MANAGED_FILE_BYTES:
                        raise ValueError("Managed file size limit exceeded")
                    with expanded_path.open(encoding="utf-8") as f:
                        return {"success": True, "content": f.read()}
                return {"success": False, "error": "Managed file not found"}
        except (PermissionError, FileNotFoundError, FileExistsError, ValueError):
            return {"success": False, "error": "Operation failed"}
        except Exception as e:
            return {"success": False, "error": type(e).__name__}


class PythonManager:
    def __init__(self, manager):
        self.manager = manager

    def install_uv(self) -> dict:
        version = str(setting("SYSTEMS_MANAGER_UV_VERSION", "")).strip()
        if not re.fullmatch(r"\d+\.\d+\.\d+", version):
            return {
                "success": False,
                "error": "SYSTEMS_MANAGER_UV_VERSION must pin an exact release",
            }
        return self.manager.run_command(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "--disable-pip-version-check",
                "--no-input",
                "--only-binary=:all:",
                "--",
                f"uv=={version}",
            ]
        )

    def create_venv(self, path: str, python_version: str | None = None) -> dict:
        managed_path = resolve_managed_path(path)
        cmd = ["uv", "venv", str(managed_path)]
        if python_version:
            candidate = python_version.strip()
            if not re.fullmatch(r"\d{1,2}(?:\.\d{1,2}){0,2}", candidate):
                raise ValueError("Invalid Python version")
            cmd.extend(["--python", candidate])
        return self.manager.run_command(cmd)

    def install_package(self, package: str, venv_path: str | None = None) -> dict:
        requirement = _validated_python_requirement(package)
        cmd = ["uv", "pip", "install", "--", requirement]
        env_overrides = None
        if venv_path:
            env_overrides = {
                "VIRTUAL_ENV": str(resolve_managed_path(venv_path, must_exist=True))
            }

        return self.manager.run_command(cmd, env_overrides=env_overrides)


class NodeManager:
    def __init__(self, manager):
        self.manager = manager

    def install_nvm(self) -> dict:
        if platform.system() == "Windows":
            return {
                "success": False,
                "error": "NVM for Windows not supported directly via this tool yet. Use nvm-windows installer.",
            }

        revision = str(setting("SYSTEMS_MANAGER_NVM_COMMIT", "")).strip().lower()
        if not re.fullmatch(r"[0-9a-f]{40}", revision):
            return {
                "success": False,
                "error": "SYSTEMS_MANAGER_NVM_COMMIT must pin an exact commit",
            }
        target = resolve_managed_path(
            setting("SYSTEMS_MANAGER_NVM_DIR", ".agent_data/nvm")
        )
        if target.is_symlink():
            return {"success": False, "error": "NVM target cannot be a symbolic link"}
        target.mkdir(parents=True, exist_ok=True)
        commands = [
            ["git", "-C", str(target), "init", "--quiet"],
            [
                "git",
                "-C",
                str(target),
                "remote",
                "remove",
                "origin",
            ],
            [
                "git",
                "-C",
                str(target),
                "remote",
                "add",
                "origin",
                "https://github.com/nvm-sh/nvm.git",
            ],
            [
                "git",
                "-C",
                str(target),
                "fetch",
                "--depth=1",
                "origin",
                revision,
            ],
            ["git", "-C", str(target), "checkout", "--detach", "FETCH_HEAD"],
        ]
        for index, command in enumerate(commands):
            result = self.manager.run_command(command)
            # Removing a missing origin is expected on first installation.
            if not result.get("success") and index != 1:
                return {"success": False, "error": "Pinned NVM install failed"}
        return {"success": True, "revision": revision}

    def install_node(self, version: str = "--lts") -> dict:
        version = self._validated_version(version)
        script = resolve_managed_path(
            os.path.join(
                setting("SYSTEMS_MANAGER_NVM_DIR", ".agent_data/nvm"),
                "nvm.sh",
            ),
            must_exist=True,
        )
        return self.manager.run_command(
            ["bash", "-c", 'source "$1"; nvm install "$2"', "nvm", str(script), version]
        )

    def use_node(self, version: str) -> dict:
        version = self._validated_version(version)
        script = resolve_managed_path(
            os.path.join(
                setting("SYSTEMS_MANAGER_NVM_DIR", ".agent_data/nvm"),
                "nvm.sh",
            ),
            must_exist=True,
        )
        return self.manager.run_command(
            ["bash", "-c", 'source "$1"; nvm use "$2"', "nvm", str(script), version]
        )

    @staticmethod
    def _validated_version(version: str) -> str:
        candidate = version.strip()
        if candidate in {"--lts", "node", "stable"} or re.fullmatch(
            r"(?:v?\d+)(?:\.\d+){0,2}|lts/[A-Za-z0-9._-]+", candidate
        ):
            return candidate
        raise ValueError("Invalid Node.js version selector")


class SystemsManagerBase(ABC):
    def __init__(self, silent: bool = False):
        self.silent = silent
        self.logger = setup_logging()
        self.fs_manager = FileSystemManager(self)
        self.python_manager = PythonManager(self)
        self.node_manager = NodeManager(self)

    def log_command(
        self,
        command: list[str] | tuple[str, ...],
        result: subprocess.CompletedProcess | None = None,
        error: Exception | None = None,
    ):
        executable = (
            Path(command[0]).name
            if isinstance(command, (list, tuple)) and command
            else "unknown"
        )
        self.logger.info("Running managed command executable=%s", executable)
        if result:
            self.logger.info("Managed command return code=%s", result.returncode)
        if error:
            self.logger.error("Managed command failed type=%s", type(error).__name__)

    def run_command(
        self,
        command: list[str] | tuple[str, ...],
        elevated: bool = False,
        *,
        capture_output: bool = False,
        env_overrides: dict[str, str] | None = None,
        timeout_seconds: int | None = None,
    ) -> dict:
        """Run an allowlisted fixed argv with bounded time and output.

        Shell execution and string commands are intentionally unsupported. On
        Windows, the hosting service must already run with the required token;
        this method never constructs an elevation command string.
        """
        try:
            argv = _validated_command_argv(command)
            operation_argv = list(argv)
            argv[0] = _resolve_trusted_executable(argv[0])
            if elevated and platform.system() == "Linux":
                is_root = hasattr(os, "geteuid") and os.geteuid() == 0
                if not is_root:
                    argv = [
                        _resolve_trusted_executable("sudo"),
                        "--non-interactive",
                        "--",
                        *argv,
                    ]
            elif elevated and platform.system() == "Windows":
                # The service/process token is the privilege boundary. Never
                # synthesize Start-Process/PowerShell elevation strings.
                try:
                    import ctypes

                    is_admin = bool(ctypes.windll.shell32.IsUserAnAdmin())
                except (AttributeError, OSError):
                    is_admin = False
                if not is_admin:
                    return {
                        "success": False,
                        "error": "Operation requires a pre-authorized service account",
                    }

            executable = (
                Path(argv[-len(command)]).name
                if elevated and argv[0] == "sudo"
                else Path(argv[0]).name
            )
            self.logger.info("Running managed executable=%s", executable)
            stdout_buffer = bytearray()
            stderr_buffer = bytearray()
            process = subprocess.Popen(
                argv,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=False,
                env=_minimal_child_environment(env_overrides),
                start_new_session=os.name != "nt",
                creationflags=(
                    getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
                    if os.name == "nt"
                    else 0
                ),
            )
            assert process.stdout is not None
            assert process.stderr is not None
            readers = [
                threading.Thread(
                    target=_bounded_stream_reader,
                    args=(process.stdout, stdout_buffer, _MAX_COMMAND_OUTPUT_BYTES),
                    daemon=True,
                ),
                threading.Thread(
                    target=_bounded_stream_reader,
                    args=(process.stderr, stderr_buffer, _MAX_COMMAND_OUTPUT_BYTES),
                    daemon=True,
                ),
            ]
            for reader in readers:
                reader.start()
            timed_out = False
            reader_cleanup_failed = False
            timeout_seconds = _validated_timeout_seconds(
                operation_argv, timeout_seconds
            )
            try:
                try:
                    returncode = process.wait(timeout=timeout_seconds)
                except subprocess.TimeoutExpired:
                    timed_out = True
                    try:
                        returncode = _terminate_process_tree(process)
                    except (OSError, psutil.Error, subprocess.TimeoutExpired):
                        process.kill()
                        returncode = process.wait(
                            timeout=_COMMAND_TERMINATION_GRACE_SECONDS
                        )
            finally:
                for reader in readers:
                    reader.join(timeout=_COMMAND_TERMINATION_GRACE_SECONDS)
                for reader, stream in zip(
                    readers, (process.stdout, process.stderr), strict=True
                ):
                    if reader.is_alive():
                        reader_cleanup_failed = True
                        stream.close()
                        reader.join(timeout=_COMMAND_TERMINATION_GRACE_SECONDS)

            result: dict[str, Any] = {
                "success": (
                    returncode == 0 and not timed_out and not reader_cleanup_failed
                ),
                "returncode": returncode,
                "timed_out": timed_out,
                "timeout_seconds": timeout_seconds,
                "reader_cleanup_failed": reader_cleanup_failed,
                "output_truncated": (
                    len(stdout_buffer) >= _MAX_COMMAND_OUTPUT_BYTES
                    or len(stderr_buffer) >= _MAX_COMMAND_OUTPUT_BYTES
                ),
            }
            if capture_output:
                result["stdout"] = stdout_buffer.decode("utf-8", errors="replace")
                result["stderr"] = stderr_buffer.decode("utf-8", errors="replace")
            if not result["success"]:
                if timed_out:
                    result["error"] = "Managed command timed out"
                elif reader_cleanup_failed:
                    result["error"] = "Managed command output cleanup failed"
                else:
                    result["error"] = "Managed command failed"
            self.logger.info("Managed command return code=%s", returncode)
            return result
        except Exception as e:
            self.log_command(command, error=e)
            return {"success": False, "error": "Managed command failed"}

    def _k8s_lifecycle_guard(self, allow_on_k8s: bool) -> dict | None:
        """Refuse a naive reboot or update on a live Kubernetes node."""
        if allow_on_k8s or str(setting("ALLOW_UPDATE_ON_K8S", "")).casefold() in {
            "1",
            "true",
            "yes",
        }:
            return None
        is_node, _reason = is_k8s_node()
        if not is_node:
            return None
        return {
            "success": False,
            "error": (
                "This host is a live Kubernetes node; use the governed rolling "
                "update workflow or an explicit deployment-policy override"
            ),
        }

    def reboot(self, allow_on_k8s: bool = False) -> dict:
        """Reboot the host after applying the Kubernetes lifecycle guard."""
        guard = self._k8s_lifecycle_guard(allow_on_k8s)
        if guard is not None:
            return guard
        if platform.system() == "Windows":
            return self.run_command(["shutdown.exe", "/r", "/t", "0"], elevated=True)
        return self.run_command(["systemctl", "reboot"], elevated=True)

    @abstractmethod
    def install_applications(self, apps: list[str]) -> dict:
        pass

    @abstractmethod
    def update(self, allow_on_k8s: bool = False) -> dict:
        pass

    @abstractmethod
    def clean(self) -> dict:
        pass

    @abstractmethod
    def optimize(self) -> dict:
        pass

    @abstractmethod
    def install_snapd(self) -> dict:
        pass

    @abstractmethod
    def add_repository(self, repo_url: str, name: str | None = None) -> dict:
        pass

    @abstractmethod
    def install_local_package(self, file_path: str) -> dict:
        pass

    @abstractmethod
    def search_package(self, query: str) -> dict:
        pass

    @abstractmethod
    def get_package_info(self, package: str) -> dict:
        pass

    @abstractmethod
    def list_installed_packages(self) -> dict:
        pass

    @abstractmethod
    def list_upgradable_packages(self) -> dict:
        pass

    @abstractmethod
    def clean_package_cache(self) -> dict:
        pass

    def install_via_snap(self, app: str) -> dict:
        app = _validated_package_name(app)
        snap_bin = shutil.which("snap")
        if snap_bin is None:
            return {
                "success": False,
                "error": (
                    "Snap prerequisite is unavailable; install and configure "
                    "snapd through an explicitly approved lifecycle operation"
                ),
                "prerequisite": "snapd",
            }
        install_result = self.run_command(["snap", "install", app], elevated=True)
        return {
            "success": install_result["success"],
            "details": install_result,
            "app": app,
        }

    def install_python_modules(self, modules: list[str]) -> dict:
        if not isinstance(modules, list) or not modules or len(modules) > 64:
            return {"success": False, "error": "Invalid Python package list"}
        results: dict[str, Any] = {
            "upgraded_pip": False,
            "installed": [],
            "failed": [],
            "success": True,
        }
        for module in modules:
            try:
                requirement = _validated_python_requirement(module)
            except (TypeError, ValueError):
                results["failed"].append("invalid-requirement")
                results["success"] = False
                continue
            install_cmd = [
                "python",
                "-m",
                "pip",
                "install",
                "--upgrade",
                "--",
                requirement,
            ]
            install_result = self.run_command(install_cmd)
            if install_result["success"]:
                results["installed"].append(requirement)
            else:
                results["failed"].append(requirement)
                results["success"] = False
                self.logger.error("Python package installation failed")
        return results

    def get_os_statistics(self) -> dict:
        return {
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "load_avg": os.getloadavg() if platform.system() != "Windows" else "N/A",
        }

    def get_hardware_statistics(self) -> dict:
        return {
            "cpu_percent": psutil.cpu_percent(interval=1),
            "cpu_count": psutil.cpu_count(),
            "memory": psutil.virtual_memory()._asdict(),
            "disk_usage": psutil.disk_usage("/")._asdict(),
            "network": psutil.net_io_counters()._asdict(),
        }

    def list_services(self) -> dict:
        try:
            if platform.system() == "Linux":
                result = self.run_command(
                    [
                        "systemctl",
                        "list-units",
                        "--type=service",
                        "--all",
                        "--no-pager",
                        "--plain",
                        "--no-legend",
                    ],
                    capture_output=True,
                )
                if not result["success"]:
                    return {"success": False, "error": "Service inventory failed"}
                services = []
                for line in (result.get("stdout") or "").strip().splitlines():
                    parts = line.split(None, 4)
                    if len(parts) >= 4:
                        services.append(
                            {
                                "name": parts[0],
                                "load": parts[1],
                                "active": parts[2],
                                "sub": parts[3],
                                "description": parts[4] if len(parts) > 4 else "",
                            }
                        )
                return {"success": True, "services": services, "total": len(services)}
            elif platform.system() == "Windows":
                result = self.run_command(
                    [
                        "powershell.exe",
                        "-NoProfile",
                        "-NonInteractive",
                        "-Command",
                        "Get-Service | Select-Object Name,Status,DisplayName | ConvertTo-Json -Depth 3",
                    ],
                    capture_output=True,
                )
                if not result["success"]:
                    return {"success": False, "error": "Service inventory failed"}
                try:
                    services = json.loads(result.get("stdout", "[]"))
                    if isinstance(services, dict):
                        services = [services]
                    return {
                        "success": True,
                        "services": services,
                        "total": len(services),
                    }
                except json.JSONDecodeError:
                    return {"success": False, "error": "Failed to parse service list"}
            return {"success": False, "error": f"Unsupported OS: {platform.system()}"}
        except Exception:
            return {"success": False, "error": "Operation failed"}

    def get_service_status(self, name: str) -> dict:
        try:
            name = self._validated_service_name(name)
            if platform.system() == "Linux":
                result = self.run_command(
                    ["systemctl", "is-active", name], capture_output=True
                )
                state = (result.get("stdout") or "unknown").strip().splitlines()[:1]
                return {
                    "success": result["success"],
                    "service": name,
                    "state": state[0] if state else "unknown",
                    "returncode": result.get("returncode"),
                }
            elif platform.system() == "Windows":
                result = self.run_command(
                    [
                        "powershell.exe",
                        "-NoProfile",
                        "-NonInteractive",
                        "-Command",
                        f"Get-Service -Name '{name}' | Select-Object Name,Status,DisplayName,StartType | ConvertTo-Json",
                    ],
                    capture_output=True,
                )
                if result["success"]:
                    try:
                        return {
                            "success": True,
                            "service": json.loads(result.get("stdout", "{}")),
                        }
                    except json.JSONDecodeError:
                        pass
                return {
                    "success": result["success"],
                    "service": name,
                    "state": "unknown",
                }
            return {"success": False, "error": f"Unsupported OS: {platform.system()}"}
        except Exception:
            return {"success": False, "error": "Operation failed"}

    def start_service(self, name: str) -> dict:
        name = self._validated_service_name(name)
        if platform.system() == "Linux":
            return self.run_command(["systemctl", "start", name], elevated=True)
        elif platform.system() == "Windows":
            return self.run_command(
                [
                    "powershell.exe",
                    "-NoProfile",
                    "-NonInteractive",
                    "-Command",
                    f"Start-Service -Name '{name}'",
                ],
                elevated=True,
            )
        return {"success": False, "error": f"Unsupported OS: {platform.system()}"}

    def stop_service(self, name: str) -> dict:
        name = self._validated_service_name(name)
        if platform.system() == "Linux":
            return self.run_command(["systemctl", "stop", name], elevated=True)
        elif platform.system() == "Windows":
            return self.run_command(
                [
                    "powershell.exe",
                    "-NoProfile",
                    "-NonInteractive",
                    "-Command",
                    f"Stop-Service -Name '{name}' -Force",
                ],
                elevated=True,
            )
        return {"success": False, "error": f"Unsupported OS: {platform.system()}"}

    def restart_service(self, name: str) -> dict:
        name = self._validated_service_name(name)
        if platform.system() == "Linux":
            return self.run_command(["systemctl", "restart", name], elevated=True)
        elif platform.system() == "Windows":
            if not os.path.exists(self.winget_bin):
                self.winget_bin = "winget.exe"
            return self.run_command(
                [
                    "powershell.exe",
                    "-NoProfile",
                    "-NonInteractive",
                    "-Command",
                    f"Restart-Service -Name '{name}' -Force",
                ],
                elevated=True,
            )
        return {"success": False, "error": f"Unsupported OS: {platform.system()}"}

    def enable_service(self, name: str) -> dict:
        name = self._validated_service_name(name)
        if platform.system() == "Linux":
            return self.run_command(["systemctl", "enable", name], elevated=True)
        elif platform.system() == "Windows":
            return self.run_command(
                [
                    "powershell.exe",
                    "-NoProfile",
                    "-NonInteractive",
                    "-Command",
                    f"Set-Service -Name '{name}' -StartupType Automatic",
                ],
                elevated=True,
            )
        return {"success": False, "error": f"Unsupported OS: {platform.system()}"}

    def disable_service(self, name: str) -> dict:
        name = self._validated_service_name(name)
        if platform.system() == "Linux":
            return self.run_command(["systemctl", "disable", name], elevated=True)
        elif platform.system() == "Windows":
            return self.run_command(
                [
                    "powershell.exe",
                    "-NoProfile",
                    "-NonInteractive",
                    "-Command",
                    f"Set-Service -Name '{name}' -StartupType Disabled",
                ],
                elevated=True,
            )
        return {"success": False, "error": f"Unsupported OS: {platform.system()}"}

    @staticmethod
    def _validated_service_name(name: str) -> str:
        candidate = name.strip()
        if not re.fullmatch(r"[A-Za-z0-9_.@:-]{1,256}", candidate):
            raise ValueError("Invalid service name")
        return candidate

    def list_processes(self) -> dict:
        try:
            processes = []
            for proc in psutil.process_iter(
                ["pid", "name", "cpu_percent", "memory_percent", "status"]
            ):
                try:
                    info = proc.info
                    processes.append(
                        {
                            "pid": info["pid"],
                            "process_ref": _opaque_ref(
                                "process", f"{info['pid']}\x00{info['name']}"
                            ),
                            "cpu_percent": info["cpu_percent"],
                            "memory_percent": (
                                round(info["memory_percent"], 2)
                                if info["memory_percent"]
                                else 0
                            ),
                            "status": info["status"],
                        }
                    )
                    if len(processes) >= _MAX_FILESYSTEM_RESULTS:
                        break
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            return {"success": True, "processes": processes, "total": len(processes)}
        except Exception:
            return {"success": False, "error": "Operation failed"}

    def get_process_info(self, pid: int) -> dict:
        try:
            if not isinstance(pid, int) or pid <= 0:
                raise ValueError("Invalid process identifier")
            proc = psutil.Process(pid)
            with proc.oneshot():
                info = {
                    "pid": proc.pid,
                    "process_ref": _opaque_ref(
                        "process", f"{proc.pid}\x00{proc.name()}"
                    ),
                    "status": proc.status(),
                    "cpu_percent": proc.cpu_percent(interval=0.1),
                    "memory_percent": round(proc.memory_percent(), 2),
                    "memory_info": proc.memory_info()._asdict(),
                    "create_time": datetime.fromtimestamp(
                        proc.create_time()
                    ).isoformat(),
                    "num_threads": proc.num_threads(),
                }
            return {"success": True, "process": info}
        except psutil.NoSuchProcess:
            return {"success": False, "error": "Process was not found"}
        except psutil.AccessDenied:
            return {"success": False, "error": "Process access was denied"}
        except Exception:
            return {"success": False, "error": "Operation failed"}

    def kill_process(self, pid: int, signal: int = 15) -> dict:
        try:
            if (
                not isinstance(pid, int)
                or pid in {0, 1, os.getpid(), os.getppid()}
                or pid < 0
                or signal not in {9, 15}
            ):
                raise ValueError("Protected or invalid process target")
            proc = psutil.Process(pid)
            proc.kill() if signal == 9 else proc.terminate()
            return {
                "success": True,
                "message": "Requested process signal was delivered",
            }
        except psutil.NoSuchProcess:
            return {"success": False, "error": "Process was not found"}
        except psutil.AccessDenied:
            return {"success": False, "error": "Process access was denied"}
        except Exception:
            return {"success": False, "error": "Operation failed"}

    def list_network_interfaces(self) -> dict:
        try:
            interfaces: list[dict[str, Any]] = []
            addrs = psutil.net_if_addrs()
            stats = psutil.net_if_stats()
            for iface, addr_list in addrs.items():
                iface_info = {
                    "interface_ref": _opaque_ref("interface", iface),
                    "address_families": [],
                    "is_up": False,
                    "speed": 0,
                }
                if iface in stats:
                    iface_info.update(
                        {
                            "is_up": stats[iface].isup,
                            "speed": stats[iface].speed,
                            "mtu": stats[iface].mtu,
                        }
                    )
                for addr in addr_list:
                    family = str(addr.family)
                    if family not in iface_info["address_families"]:
                        iface_info["address_families"].append(family)
                interfaces.append(iface_info)
            return {"success": True, "interfaces": interfaces}
        except Exception:
            return {"success": False, "error": "Operation failed"}

    def list_open_ports(self) -> dict:
        try:
            connections = []
            for conn in psutil.net_connections(kind="inet"):
                if conn.status == "LISTEN":
                    connections.append(
                        {
                            "local_port": conn.laddr.port if conn.laddr else None,
                            "listener_ref": _opaque_ref(
                                "listener",
                                f"{conn.laddr.ip if conn.laddr else ''}:"
                                f"{conn.laddr.port if conn.laddr else ''}:"
                                f"{conn.pid or ''}",
                            ),
                            "status": conn.status,
                        }
                    )
                    if len(connections) >= _MAX_FILESYSTEM_RESULTS:
                        break
            return {"success": True, "ports": connections, "total": len(connections)}
        except psutil.AccessDenied:
            cmd = (
                ["ss", "-tlnp"] if platform.system() == "Linux" else ["netstat", "-an"]
            )
            result = self.run_command(cmd)
            return {
                "success": result["success"],
                "details_redacted": True,
            }
        except Exception:
            return {"success": False, "error": "Operation failed"}

    def ping_host(self, host: str, count: int = 4) -> dict:
        host = _validated_host(host)
        count = max(1, min(int(count), 10))
        flag = "-n" if platform.system() == "Windows" else "-c"
        result = self.run_command(["ping", flag, str(count), host])
        return {
            "success": result["success"],
            "host_ref": _opaque_ref("host", host),
            "returncode": result.get("returncode"),
        }

    def dns_lookup(self, hostname: str) -> dict:
        try:
            hostname = _validated_host(hostname)
            results = socket.getaddrinfo(hostname, None)
            addresses = list(set(addr[4][0] for addr in results))
            return {
                "success": True,
                "hostname_ref": _opaque_ref("host", hostname),
                "address_refs": [_opaque_ref("address", value) for value in addresses],
                "address_count": len(addresses),
            }
        except socket.gaierror:
            return {"success": False, "error": "DNS lookup failed"}
        except Exception:
            return {"success": False, "error": "Operation failed"}

    def list_disks(self) -> dict:
        try:
            partitions = []
            for part in psutil.disk_partitions(all=False):
                entry = {
                    "disk_ref": _opaque_ref(
                        "disk", f"{part.device}\x00{part.mountpoint}"
                    ),
                    "fstype": part.fstype,
                }
                try:
                    usage = psutil.disk_usage(part.mountpoint)
                    entry.update(
                        {
                            "total": usage.total,
                            "used": usage.used,
                            "free": usage.free,
                            "percent": usage.percent,
                        }
                    )
                except (PermissionError, OSError):
                    pass
                partitions.append(entry)
            return {"success": True, "disks": partitions, "total": len(partitions)}
        except Exception:
            return {"success": False, "error": "Operation failed"}

    def get_disk_usage(self, path: str = ".") -> dict:
        try:
            managed_path = resolve_managed_path(path, must_exist=True)
            usage = psutil.disk_usage(managed_path)
            return {
                "success": True,
                "path": managed_display_path(managed_path),
                "total": usage.total,
                "used": usage.used,
                "free": usage.free,
                "percent": usage.percent,
            }
        except Exception:
            return {"success": False, "error": "Operation failed"}

    def list_users(self) -> dict:
        try:
            if platform.system() == "Linux":
                users = []
                with open("/etc/passwd") as f:
                    for line in f:
                        parts = line.strip().split(":")
                        if len(parts) >= 7:
                            users.append(
                                {
                                    "user_ref": _opaque_ref("user", parts[0]),
                                    "uid": int(parts[2]),
                                    "gid": int(parts[3]),
                                }
                            )
                return {"success": True, "users": users, "total": len(users)}
            elif platform.system() == "Windows":
                result = self.run_command(
                    [
                        "powershell.exe",
                        "-NoProfile",
                        "-NonInteractive",
                        "-Command",
                        "Get-LocalUser | Select-Object Name,Enabled | ConvertTo-Json -Depth 3",
                    ],
                    capture_output=True,
                )
                if result["success"]:
                    try:
                        users = json.loads(result.get("stdout", "[]"))
                        if isinstance(users, dict):
                            users = [users]
                        redacted_users = [
                            {
                                "user_ref": _opaque_ref(
                                    "user", str(user.get("Name", "unknown"))
                                ),
                                "enabled": bool(user.get("Enabled", False)),
                            }
                            for user in users[:_MAX_FILESYSTEM_RESULTS]
                        ]
                        return {
                            "success": True,
                            "users": redacted_users,
                            "total": len(redacted_users),
                        }
                    except json.JSONDecodeError:
                        return {"success": False, "error": "Failed to parse user list"}
                return {"success": False, "error": "User inventory failed"}
            return {"success": False, "error": f"Unsupported OS: {platform.system()}"}
        except Exception:
            return {"success": False, "error": "Operation failed"}

    def list_groups(self) -> dict:
        try:
            if platform.system() == "Linux":
                groups = []
                with open("/etc/group") as f:
                    for line in f:
                        parts = line.strip().split(":")
                        if len(parts) >= 4:
                            groups.append(
                                {
                                    "group_ref": _opaque_ref("group", parts[0]),
                                    "gid": int(parts[2]),
                                    "member_count": (
                                        len(parts[3].split(",")) if parts[3] else 0
                                    ),
                                }
                            )
                return {"success": True, "groups": groups, "total": len(groups)}
            elif platform.system() == "Windows":
                result = self.run_command(
                    [
                        "powershell.exe",
                        "-NoProfile",
                        "-NonInteractive",
                        "-Command",
                        "Get-LocalGroup | Select-Object Name | ConvertTo-Json -Depth 3",
                    ],
                    capture_output=True,
                )
                if result["success"]:
                    try:
                        groups = json.loads(result.get("stdout", "[]"))
                        if isinstance(groups, dict):
                            groups = [groups]
                        redacted_groups = [
                            {
                                "group_ref": _opaque_ref(
                                    "group", str(group.get("Name", "unknown"))
                                )
                            }
                            for group in groups[:_MAX_FILESYSTEM_RESULTS]
                        ]
                        return {
                            "success": True,
                            "groups": redacted_groups,
                            "total": len(redacted_groups),
                        }
                    except json.JSONDecodeError:
                        return {"success": False, "error": "Failed to parse group list"}
                return {"success": False, "error": "Group inventory failed"}
            return {"success": False, "error": f"Unsupported OS: {platform.system()}"}
        except Exception:
            return {"success": False, "error": "Operation failed"}

    def get_system_logs(
        self, unit: str | None = None, lines: int = 100, priority: str | None = None
    ) -> dict:
        try:
            lines = max(1, min(int(lines), 1_000))
            if unit:
                unit = self._validated_service_name(unit)
            if priority and priority not in {
                "emerg",
                "alert",
                "crit",
                "err",
                "warning",
                "notice",
                "info",
                "debug",
            }:
                raise ValueError("Invalid log priority")
            if platform.system() == "Linux":
                cmd = ["journalctl", "--no-pager", "-n", str(lines)]
                if unit:
                    cmd.extend(["-u", unit])
                if priority:
                    cmd.extend(["-p", priority])
                result = self.run_command(cmd, capture_output=True)
                logs = result.get("stdout", "") if result["success"] else ""
                return {"success": result["success"], "logs": logs}
            elif platform.system() == "Windows":
                result = self.run_command(
                    [
                        "powershell.exe",
                        "-NoProfile",
                        "-NonInteractive",
                        "-Command",
                        f"Get-EventLog -LogName System -Newest {lines} | Format-List | Out-String",
                    ],
                    capture_output=True,
                )
                logs = result.get("stdout", "") if result["success"] else ""
                return {"success": result["success"], "logs": logs}
            return {"success": False, "error": f"Unsupported OS: {platform.system()}"}
        except Exception:
            return {"success": False, "error": "Operation failed"}

    def tail_log_file(self, path: str, lines: int = 50) -> dict:
        try:
            managed_path = resolve_managed_path(path, must_exist=True)
            if not managed_path.is_file() or managed_path.is_symlink():
                return {"success": False, "error": "Configured file was not found"}
            if managed_path.stat().st_size > _MAX_MANAGED_FILE_BYTES:
                return {"success": False, "error": "Managed file size limit exceeded"}
            lines = max(1, min(int(lines), 1_000))
            with managed_path.open(errors="replace") as handle:
                tail = deque(handle, maxlen=lines)
            return {
                "success": True,
                "path": managed_display_path(managed_path),
                "lines": len(tail),
                "content": "".join(tail),
            }
        except Exception:
            return {"success": False, "error": "Operation failed"}

    def system_health_check(self) -> dict:
        try:
            boot_time = datetime.fromtimestamp(psutil.boot_time())
            uptime = datetime.now() - boot_time
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            swap = psutil.swap_memory()
            disk_warnings = []
            for part in psutil.disk_partitions(all=False):
                try:
                    usage = psutil.disk_usage(part.mountpoint)
                    if usage.percent > 90:
                        disk_warnings.append(
                            {
                                "disk_ref": _opaque_ref(
                                    "disk", f"{part.device}\x00{part.mountpoint}"
                                ),
                                "percent": usage.percent,
                                "free_gb": round(usage.free / (1024**3), 2),
                            }
                        )
                except (PermissionError, OSError):
                    continue
            top_procs = []
            for proc in sorted(
                psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]),
                key=lambda p: p.info.get("memory_percent", 0) or 0,
                reverse=True,
            )[:10]:
                try:
                    info = proc.info
                    top_procs.append(
                        {
                            "process_ref": _opaque_ref(
                                "process", f"{info['pid']}\x00{info['name']}"
                            ),
                            "cpu_percent": info.get("cpu_percent") or 0,
                            "memory_percent": round(info.get("memory_percent") or 0, 2),
                        }
                    )
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            warnings = []
            if cpu_percent > 90:
                warnings.append(f"HIGH CPU: {cpu_percent}%")
            if memory.percent > 90:
                warnings.append(f"HIGH MEMORY: {memory.percent}%")
            if swap.percent > 80:
                warnings.append(f"HIGH SWAP: {swap.percent}%")
            for dw in disk_warnings:
                warnings.append(f"DISK CAPACITY HIGH: {dw['percent']}%")
            drive_faults: list[dict[str, Any]] = []
            try:
                from systems_manager.storage_health import drive_health_summary

                drive_summary = drive_health_summary(self)
                warnings.extend(drive_summary.get("warnings", []))
                drive_faults = drive_summary.get("faults", [])
            except Exception as exc:
                # Storage telemetry is optional and must not make the base
                # health endpoint unavailable on unsupported hosts.
                self.logger.debug(
                    "Storage health telemetry unavailable: %s",
                    type(exc).__name__,
                )
            load_avg = os.getloadavg() if platform.system() != "Windows" else None
            return {
                "success": True,
                "status": "warning" if warnings else "healthy",
                "warnings": warnings,
                "uptime_seconds": int(uptime.total_seconds()),
                "uptime_human": str(uptime).split(".")[0],
                "cpu_percent": cpu_percent,
                "memory_percent": memory.percent,
                "memory_available_gb": round(memory.available / (1024**3), 2),
                "swap_percent": swap.percent,
                "disk_warnings": disk_warnings,
                "drive_faults": drive_faults,
                "load_average": load_avg,
                "top_memory_processes": top_procs,
            }
        except Exception:
            return {"success": False, "error": "Operation failed"}

    def get_uptime(self) -> dict:
        try:
            boot_time = datetime.fromtimestamp(psutil.boot_time())
            uptime = datetime.now() - boot_time
            return {
                "success": True,
                "boot_time": boot_time.isoformat(),
                "uptime_seconds": int(uptime.total_seconds()),
                "uptime_human": str(uptime).split(".")[0],
            }
        except Exception:
            return {"success": False, "error": "Operation failed"}

    def list_cron_jobs(self, user: str | None = None) -> dict:
        try:
            user = _validated_account_name(user)
            if platform.system() == "Linux":
                cmd = ["crontab", "-l", "-u", user] if user else ["crontab", "-l"]
                result = self.run_command(cmd, capture_output=True)
                jobs = []
                if result["success"]:
                    for line in (result.get("stdout") or "").strip().splitlines():
                        if line.strip() and not line.strip().startswith("#"):
                            content = line.strip()
                            fields = content.split(None, 5)
                            jobs.append(
                                {
                                    "job_ref": _opaque_ref("cron", content),
                                    "schedule": (
                                        " ".join(fields[:5])
                                        if len(fields) >= 6
                                        else "special"
                                    ),
                                }
                            )
                            if len(jobs) >= _MAX_FILESYSTEM_RESULTS:
                                break
                return {"success": True, "jobs": jobs, "total": len(jobs)}
            elif platform.system() == "Windows":
                result = self.run_command(
                    ["schtasks", "/query", "/fo", "CSV", "/v"],
                    capture_output=True,
                )
                return {
                    "success": result["success"],
                    "total": max(0, len((result.get("stdout") or "").splitlines()) - 1),
                    "details_redacted": True,
                }
            return {"success": False, "error": f"Unsupported OS: {platform.system()}"}
        except Exception:
            return {"success": False, "error": "Operation failed"}

    def remove_cron_job(self, pattern: str, user: str | None = None) -> dict:
        try:
            if platform.system() != "Linux":
                return {
                    "success": False,
                    "error": "Cron jobs are only supported on Linux",
                }
            user = _validated_account_name(user)
            if not re.fullmatch(r"cron:[0-9a-f]{16}", pattern):
                raise ValueError("An exact cron job reference is required")
            list_cmd = ["crontab", "-l", "-u", user] if user else ["crontab", "-l"]
            existing = self.run_command(list_cmd, capture_output=True)
            if not existing["success"]:
                return {"success": False, "error": "Failed to read current crontab"}
            lines = (existing.get("stdout") or "").splitlines()
            removed = [
                line_content
                for line_content in lines
                if _opaque_ref("cron", line_content.strip()) == pattern
            ]
            kept = [
                line_content
                for line_content in lines
                if _opaque_ref("cron", line_content.strip()) != pattern
            ]
            if not removed:
                return {
                    "success": False,
                    "error": "Cron job reference was not found",
                }
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".cron", delete=False
            ) as tmp:
                tmp.write("\n".join(kept) + "\n")
                tmp_path = tmp.name
            os.chmod(tmp_path, 0o600)
            try:
                install_cmd = (
                    ["crontab", "-u", user, tmp_path] if user else ["crontab", tmp_path]
                )
                result = self.run_command(install_cmd, elevated=bool(user))
                return {
                    "success": result["success"],
                    "message": (
                        f"Removed {len(removed)} cron job(s)"
                        if result["success"]
                        else "Failed"
                    ),
                }
            finally:
                os.remove(tmp_path)
        except Exception:
            return {"success": False, "error": "Operation failed"}

    def get_firewall_status(self) -> dict:
        try:
            if platform.system() == "Linux":
                if shutil.which("ufw"):
                    r = self.run_command(
                        ["ufw", "status", "verbose"],
                        elevated=True,
                        capture_output=True,
                    )
                    state = (
                        "active"
                        if "status: active" in (r.get("stdout") or "").casefold()
                        else "inactive-or-unknown"
                    )
                    return {
                        "success": r["success"],
                        "tool": "ufw",
                        "state": state,
                    }
                if shutil.which("firewall-cmd"):
                    r = self.run_command(
                        ["firewall-cmd", "--state"],
                        elevated=True,
                        capture_output=True,
                    )
                    return {
                        "success": r["success"],
                        "tool": "firewalld",
                        "state": (
                            (r.get("stdout") or "unknown").strip().splitlines()[:1]
                            or ["unknown"]
                        )[0],
                    }
                r = self.run_command(
                    ["iptables", "-L", "-n", "--line-numbers"], elevated=True
                )
                return {
                    "success": r["success"],
                    "tool": "iptables",
                    "details_redacted": True,
                }
            elif platform.system() == "Windows":
                r = self.run_command(["netsh", "advfirewall", "show", "allprofiles"])
                return {
                    "success": r["success"],
                    "tool": "netsh",
                    "details_redacted": True,
                }
            return {"success": False, "error": f"Unsupported OS: {platform.system()}"}
        except Exception:
            return {"success": False, "error": "Operation failed"}

    def list_firewall_rules(self) -> dict:
        try:
            if platform.system() == "Linux":
                if shutil.which("ufw"):
                    r = self.run_command(
                        ["ufw", "status", "numbered"],
                        elevated=True,
                        capture_output=True,
                    )
                    return {
                        "success": r["success"],
                        "tool": "ufw",
                        "total": sum(
                            1
                            for line in (r.get("stdout") or "").splitlines()
                            if re.match(r"\s*\[\s*\d+\]", line)
                        ),
                        "details_redacted": True,
                    }
                if shutil.which("firewall-cmd"):
                    r = self.run_command(
                        ["firewall-cmd", "--list-all"],
                        elevated=True,
                        capture_output=True,
                    )
                    return {
                        "success": r["success"],
                        "tool": "firewalld",
                        "total": sum(
                            len(line.split()[1:])
                            for line in (r.get("stdout") or "").splitlines()
                            if ":" in line
                        ),
                        "details_redacted": True,
                    }
                r = self.run_command(
                    ["iptables", "-L", "-n", "-v", "--line-numbers"],
                    elevated=True,
                    capture_output=True,
                )
                return {
                    "success": r["success"],
                    "tool": "iptables",
                    "total": sum(
                        1
                        for line in (r.get("stdout") or "").splitlines()
                        if re.match(r"\s*\d+\s", line)
                    ),
                    "details_redacted": True,
                }
            elif platform.system() == "Windows":
                r = self.run_command(
                    [
                        "powershell.exe",
                        "-NoProfile",
                        "-NonInteractive",
                        "-Command",
                        "Get-NetFirewallRule | Select-Object Name,DisplayName,Enabled,Direction,Action "
                        "| ConvertTo-Json -Depth 3",
                    ],
                    capture_output=True,
                )
                if r["success"]:
                    try:
                        rules = json.loads(r.get("stdout", "[]"))
                        if isinstance(rules, dict):
                            rules = [rules]
                        return {
                            "success": True,
                            "tool": "netsh",
                            "total": len(rules),
                            "details_redacted": True,
                        }
                    except json.JSONDecodeError:
                        pass
                return {
                    "success": r["success"],
                    "tool": "netsh",
                    "details_redacted": True,
                }
            return {"success": False, "error": f"Unsupported OS: {platform.system()}"}
        except Exception:
            return {"success": False, "error": "Operation failed"}

    def add_firewall_rule(self, rule: FirewallRuleSpec | dict[str, Any]) -> dict:
        """Add one strongly typed firewall rule using exact backend arguments."""
        try:
            if platform.system() == "Linux":
                if shutil.which("ufw"):
                    arguments = _validated_firewall_args(
                        rule, backend="ufw", remove=False
                    )
                    r = self.run_command(["ufw", *arguments], elevated=True)
                    return {"success": r["success"], "tool": "ufw", "details": r}
                if shutil.which("firewall-cmd"):
                    arguments = _validated_firewall_args(
                        rule, backend="firewalld", remove=False
                    )
                    r = self.run_command(["firewall-cmd", *arguments], elevated=True)
                    return {"success": r["success"], "tool": "firewalld", "details": r}
                arguments = _validated_firewall_args(
                    rule, backend="iptables", remove=False
                )
                r = self.run_command(["iptables", *arguments], elevated=True)
                return {"success": r["success"], "tool": "iptables", "details": r}
            elif platform.system() == "Windows":
                arguments = _validated_firewall_args(
                    rule, backend="netsh", remove=False
                )
                r = self.run_command(
                    ["netsh", "advfirewall", "firewall", "add", "rule", *arguments],
                    elevated=True,
                )
                return {"success": r["success"], "tool": "netsh", "details": r}
            return {"success": False, "error": f"Unsupported OS: {platform.system()}"}
        except Exception:
            return {"success": False, "error": "Operation failed"}

    def remove_firewall_rule(self, rule: FirewallRuleSpec | dict[str, Any]) -> dict:
        """Remove one strongly typed firewall rule using exact backend arguments."""
        try:
            if platform.system() == "Linux":
                if shutil.which("ufw"):
                    arguments = _validated_firewall_args(
                        rule, backend="ufw", remove=True
                    )
                    r = self.run_command(["ufw", "delete", *arguments], elevated=True)
                    return {"success": r["success"], "tool": "ufw", "details": r}
                if shutil.which("firewall-cmd"):
                    arguments = _validated_firewall_args(
                        rule, backend="firewalld", remove=True
                    )
                    r = self.run_command(["firewall-cmd", *arguments], elevated=True)
                    return {"success": r["success"], "tool": "firewalld", "details": r}
                arguments = _validated_firewall_args(
                    rule, backend="iptables", remove=True
                )
                r = self.run_command(["iptables", *arguments], elevated=True)
                return {"success": r["success"], "tool": "iptables", "details": r}
            elif platform.system() == "Windows":
                arguments = _validated_firewall_args(rule, backend="netsh", remove=True)
                r = self.run_command(
                    ["netsh", "advfirewall", "firewall", "delete", "rule"] + arguments,
                    elevated=True,
                )
                return {"success": r["success"], "tool": "netsh", "details": r}
            return {"success": False, "error": f"Unsupported OS: {platform.system()}"}
        except Exception:
            return {"success": False, "error": "Operation failed"}

    def list_ssh_keys(self) -> dict:
        try:
            ssh_dir = os.path.expanduser("~/.ssh")
            if not os.path.exists(ssh_dir):
                return {
                    "success": True,
                    "keys": [],
                    "message": "No .ssh directory found",
                }
            keys = []
            for filename in os.listdir(ssh_dir):
                filepath = os.path.join(ssh_dir, filename)
                if os.path.isfile(filepath):
                    stat = os.stat(filepath)
                    keys.append(
                        {
                            "key_ref": hashlib.sha256(
                                filename.encode("utf-8")
                            ).hexdigest()[:16],
                            "is_public": filename.endswith(".pub"),
                            "size": stat.st_size,
                            "permissions": oct(stat.st_mode)[-3:],
                        }
                    )
            return {"success": True, "keys": keys, "total": len(keys)}
        except Exception:
            return {"success": False, "error": "Operation failed"}

    def generate_ssh_key(
        self,
        key_type: str = "ed25519",
        comment: str = "",
        passphrase: str | None = None,
    ) -> dict:
        try:
            if passphrase:
                return {
                    "success": False,
                    "error": "Secret-bearing key generation requires an external broker",
                }
            key_type = key_type.strip().casefold()
            if key_type not in {"ed25519", "rsa"}:
                raise ValueError("Unsupported SSH key type")
            if len(comment) > 256 or any(
                character in comment for character in ("\x00", "\n", "\r")
            ):
                raise ValueError("Invalid SSH key comment")
            ssh_dir = Path.home() / ".ssh"
            if ssh_dir.is_symlink():
                raise PermissionError("Symbolic-link SSH directories are not permitted")
            ssh_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
            key_path = ssh_dir / f"id_{key_type}"
            if key_path.exists() or key_path.is_symlink():
                return {"success": False, "error": "Key already exists"}
            result = self.run_command(
                [
                    "ssh-keygen",
                    "-t",
                    key_type,
                    "-f",
                    str(key_path),
                    "-N",
                    "",
                    "-C",
                    comment,
                ]
            )
            return {
                "success": result["success"],
                "key_ref": _opaque_ref("ssh-key", key_path.name),
            }
        except Exception:
            return {"success": False, "error": "Operation failed"}

    def add_authorized_key(self, public_key: str) -> dict:
        try:
            candidate = public_key.strip()
            if len(candidate) > 16_384 or any(
                character in candidate for character in ("\x00", "\n", "\r")
            ):
                raise ValueError("Invalid public key")
            fields = candidate.split(None, 2)
            if len(fields) < 2 or fields[0] not in {
                "ecdsa-sha2-nistp256",
                "ecdsa-sha2-nistp384",
                "ecdsa-sha2-nistp521",
                "sk-ecdsa-sha2-nistp256@openssh.com",
                "sk-ssh-ed25519@openssh.com",
                "ssh-ed25519",
                "ssh-rsa",
            }:
                raise ValueError("Unsupported public key type")
            try:
                decoded = base64.b64decode(fields[1], validate=True)
            except (ValueError, TypeError) as exc:
                raise ValueError("Invalid public key encoding") from exc
            if not 32 <= len(decoded) <= 16_384:
                raise ValueError("Invalid public key size")

            ssh_dir = Path.home() / ".ssh"
            if ssh_dir.is_symlink():
                raise PermissionError("Symbolic-link SSH directories are not permitted")
            ssh_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
            auth_keys = ssh_dir / "authorized_keys"
            if auth_keys.is_symlink():
                raise PermissionError("Symbolic-link key files are not permitted")
            existing = ""
            if auth_keys.exists():
                if auth_keys.stat().st_size > _MAX_MANAGED_FILE_BYTES:
                    raise ValueError("Authorized key file size limit exceeded")
                existing = auth_keys.read_text(encoding="utf-8")
                if candidate in existing.splitlines():
                    return {
                        "success": True,
                        "message": "Key already exists in authorized_keys",
                    }
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=ssh_dir,
                prefix=".authorized-keys-",
                delete=False,
            ) as handle:
                handle.write(existing.rstrip("\n") + ("\n" if existing else ""))
                handle.write(candidate + "\n")
                handle.flush()
                os.fsync(handle.fileno())
                temporary = Path(handle.name)
            try:
                temporary.chmod(0o600)
                if auth_keys.is_symlink():
                    raise PermissionError("Symbolic-link key files are not permitted")
                os.replace(temporary, auth_keys)
            finally:
                temporary.unlink(missing_ok=True)
            return {"success": True, "message": "Public key added to authorized_keys"}
        except Exception:
            return {"success": False, "error": "Operation failed"}

    def list_env_vars(self) -> dict:
        return {
            "success": True,
            "variables": sorted(os.environ),
            "total": len(os.environ),
            "values_redacted": True,
        }

    def get_env_var(self, name: str) -> dict:
        candidate = name.strip()
        allowlist = {
            item.strip()
            for item in str(
                setting("SYSTEMS_MANAGER_ENV_METADATA_ALLOWLIST", "")
            ).split(",")
            if item.strip()
        }
        sensitive = re.search(
            r"(?:KEY|TOKEN|SECRET|PASS|CREDENTIAL|COOKIE|AUTH|USER|HOME|PATH|PWD|HOST|CERT)",
            candidate,
            flags=re.IGNORECASE,
        )
        if candidate not in allowlist or sensitive:
            return {
                "success": False,
                "error": "Environment metadata is not allowlisted",
            }
        value = setting(candidate)
        if value is None:
            return {
                "success": False,
                "error": "Environment variable is not configured",
            }
        return {
            "success": True,
            "name": candidate,
            "configured": True,
        }

    def clean_temp_files(self) -> dict:
        try:
            temp_dir = resolve_managed_path(
                setting("SYSTEMS_MANAGER_TEMP_ROOT", ".agent_data/tmp")
            )
            if temp_dir.is_symlink():
                raise PermissionError("Symbolic-link temp roots are not permitted")
            temp_dir.mkdir(parents=True, exist_ok=True)
            cleaned, errors = 0, 0
            for item_path in list(temp_dir.iterdir())[:_MAX_FILESYSTEM_RESULTS]:
                try:
                    if item_path.is_symlink() or item_path.is_file():
                        item_path.unlink()
                    elif item_path.is_dir():
                        shutil.rmtree(item_path)
                    cleaned += 1
                except (PermissionError, OSError):
                    errors += 1
            return {
                "success": True,
                "cleaned": cleaned,
                "errors": errors,
            }
        except Exception:
            return {"success": False, "error": "Operation failed"}

    def get_disk_space_report(self, path: str = ".", top_n: int = 10) -> dict:
        try:
            base = resolve_managed_path(path, must_exist=True)
            if not base.is_dir():
                return {"success": False, "error": "Base path is not a directory"}
            entries: list[dict[str, Any]] = []
            budget = _FilesystemScanBudget()
            managed_root = managed_filesystem_root()
            with os.scandir(base) as children:
                for item in children:
                    if not budget.consume_entry():
                        break
                    try:
                        if item.is_symlink() or not item.is_dir(follow_symlinks=False):
                            continue
                        child = Path(item.path).resolve(strict=True)
                        child.relative_to(managed_root)
                    except (OSError, ValueError):
                        continue
                    size = 0
                    child_was_truncated = False
                    for candidate in _iter_managed_files(child, budget):
                        try:
                            size += candidate.stat().st_size
                        except OSError:
                            continue
                    if budget.truncated:
                        child_was_truncated = True
                    entries.append(
                        {
                            "size_bytes": size,
                            "path": managed_display_path(child),
                            "truncated": child_was_truncated,
                        }
                    )
                    if budget.truncated:
                        break
            entries.sort(key=lambda item: item["size_bytes"], reverse=True)
            return {
                "success": True,
                "entries": entries[: max(1, min(top_n, 100))],
                "base_path": managed_display_path(base),
                "truncated": budget.truncated,
                "visited_entries": budget.visited_entries,
            }
        except Exception:
            return {"success": False, "error": "Operation failed"}


class AptManager(SystemsManagerBase):
    def __init__(self, silent: bool = False):
        super().__init__(silent)
        self.not_found_msg = "Unable to locate package"

    def install_applications(self, apps: list[str]) -> dict:
        apps = _validated_package_names(apps)
        results = {
            "natively_installed": [],
            "snap_installed": [],
            "failed": [],
            "success": True,
        }
        update_result = self.run_command(["apt", "update"], elevated=True)
        if not update_result["success"]:
            results["success"] = False
            results["update_error"] = update_result.get("error")
            self.logger.error("apt update failed")
        for app in apps:
            install_result = self.run_command(
                ["apt", "install", "-y", "--", app],
                elevated=True,
                capture_output=True,
            )
            if install_result["success"]:
                results["natively_installed"].append(app)
            else:
                if self.not_found_msg in install_result.get("stderr", ""):
                    self.logger.info("Native install failed; trying snap")
                    snap_result = self.install_via_snap(app)
                    if snap_result["success"]:
                        results["snap_installed"].append(app)
                    else:
                        results["failed"].append(app)
                        results["success"] = False
                        self.logger.error("Snap installation failed")
                else:
                    results["failed"].append(app)
                    results["success"] = False
                    self.logger.error("Native installation failed")
        return results

    def update(self, allow_on_k8s: bool = False) -> dict:
        guard = self._k8s_lifecycle_guard(allow_on_k8s)
        if guard is not None:
            return guard
        try:
            update_result = self.run_command(["apt", "update"], elevated=True)
            if not update_result["success"]:
                return {
                    "success": False,
                    "error": "apt update failed",
                    "details": update_result,
                }
            upgrade_result = self.run_command(["apt", "upgrade", "-y"], elevated=True)
            if not upgrade_result["success"]:
                return {
                    "success": False,
                    "error": "apt upgrade failed",
                    "details": upgrade_result,
                }
            return {"success": True, "message": "System and packages updated"}
        except Exception as e:
            self.logger.error(
                "Unexpected error in update: error_type=%s", type(e).__name__
            )
            return {"success": False, "error": "Operation failed"}

    def clean(self) -> dict:
        empty_result = self.run_command(["trash-empty"])
        if empty_result["success"]:
            return {"success": True, "message": "Trash emptied"}
        else:
            return {
                "success": False,
                "error": "Failed to empty trash",
                "details": empty_result,
            }

    def optimize(self) -> dict:
        autoremove_result = self.run_command(["apt", "autoremove", "-y"], elevated=True)
        autoclean_result = self.run_command(["apt", "autoclean"], elevated=True)
        overall_success = autoremove_result["success"] and autoclean_result["success"]
        return {
            "success": overall_success,
            "message": (
                "System optimized" if overall_success else "Partial optimization"
            ),
            "details": {"autoremove": autoremove_result, "autoclean": autoclean_result},
        }

    def install_snapd(self) -> dict:
        result = self.run_command(["apt", "install", "-y", "snapd"], elevated=True)
        return {
            "success": result["success"],
            "details": result,
            "message": (
                "snapd installed" if result["success"] else "Failed to install snapd"
            ),
        }

    def add_repository(self, repo_url: str, name: str | None = None) -> dict:
        del name
        repo_url = _validated_repository_url(repo_url)
        add_result = self.run_command(
            ["add-apt-repository", "-y", repo_url], elevated=True
        )
        if add_result["success"]:
            update_result = self.run_command(["apt", "update"], elevated=True)
            return {
                "success": update_result["success"],
                "details": [add_result, update_result],
            }
        return add_result

    def install_local_package(self, file_path: str) -> dict:
        package_path = _validated_local_package(file_path, (".deb",))
        install_result = self.run_command(
            ["dpkg", "-i", str(package_path)], elevated=True
        )
        if install_result["success"]:
            fix_result = self.run_command(["apt", "install", "-f", "-y"], elevated=True)
            return {
                "success": fix_result["success"],
                "details": [install_result, fix_result],
            }
        return install_result

    def search_package(self, query: str):
        query = _validated_search_query(query)
        result = self.run_command(["apt-cache", "search", query], capture_output=True)
        packages = []
        if result["success"]:
            for line in (result.get("stdout") or "").strip().splitlines():
                parts = line.split(" - ", 1)
                if len(parts) == 2:
                    packages.append(
                        {"name": parts[0].strip(), "description": parts[1].strip()}
                    )
                    if len(packages) >= 1_000:
                        break
        return {
            "success": result["success"],
            "packages": packages,
            "total": len(packages),
        }

    def get_package_info(self, package: str):
        package = _validated_package_name(package)
        result = self.run_command(["apt-cache", "show", package], capture_output=True)
        return {
            "success": result["success"],
            "info": _parse_package_metadata(result.get("stdout", "")),
        }

    def list_installed_packages(self):
        result = self.run_command(["dpkg", "--get-selections"], capture_output=True)
        packages = []
        if result["success"]:
            for line in (result.get("stdout") or "").strip().splitlines():
                parts = line.split()
                if len(parts) >= 2 and parts[1] == "install":
                    packages.append(parts[0])
                    if len(packages) >= _MAX_FILESYSTEM_RESULTS:
                        break
        return {
            "success": result["success"],
            "packages": packages,
            "total": len(packages),
        }

    def list_upgradable_packages(self):
        result = self.run_command(["apt", "list", "--upgradable"], capture_output=True)
        packages = []
        if result["success"]:
            for line in (result.get("stdout") or "").strip().splitlines():
                if "/" in line and "Listing" not in line:
                    packages.append(line.split("/")[0])
                    if len(packages) >= _MAX_FILESYSTEM_RESULTS:
                        break
        return {
            "success": result["success"],
            "packages": packages,
            "total": len(packages),
        }

    def clean_package_cache(self):
        result = self.run_command(["apt-get", "clean"], elevated=True)
        return {
            "success": result["success"],
            "message": "APT cache cleaned" if result["success"] else "Failed",
        }


class DnfManager(SystemsManagerBase):
    def __init__(self, silent: bool = False):
        super().__init__(silent)
        self.not_found_msg = "Unable to find a match"

    def install_applications(self, apps: list[str]) -> dict:
        apps = _validated_package_names(apps)
        results = {
            "natively_installed": [],
            "snap_installed": [],
            "failed": [],
            "success": True,
        }
        for app in apps:
            install_result = self.run_command(
                ["dnf", "install", "-y", "--", app],
                elevated=True,
                capture_output=True,
            )
            if install_result["success"]:
                results["natively_installed"].append(app)
            else:
                if self.not_found_msg in install_result.get("stderr", ""):
                    self.logger.info("Native install failed; trying snap")
                    snap_result = self.install_via_snap(app)
                    if snap_result["success"]:
                        results["snap_installed"].append(app)
                    else:
                        results["failed"].append(app)
                        results["success"] = False
                else:
                    results["failed"].append(app)
                    results["success"] = False
        return results

    def update(self, allow_on_k8s: bool = False) -> dict:
        guard = self._k8s_lifecycle_guard(allow_on_k8s)
        if guard is not None:
            return guard
        result = self.run_command(["dnf", "update", "-y"], elevated=True)
        return {
            "success": result["success"],
            "message": "System updated" if result["success"] else "Update failed",
            "details": result,
        }

    def clean(self) -> dict:
        result = self.run_command(["dnf", "clean", "all"], elevated=True)
        return {
            "success": result["success"],
            "message": "Cache cleaned" if result["success"] else "Clean failed",
            "details": result,
        }

    def optimize(self) -> dict:
        result = self.run_command(["dnf", "autoremove", "-y"], elevated=True)
        return {
            "success": result["success"],
            "message": "Orphans removed" if result["success"] else "Optimize failed",
            "details": result,
        }

    def install_snapd(self) -> dict:
        result = self.run_command(["dnf", "install", "-y", "snapd"], elevated=True)
        return {
            "success": result["success"],
            "details": result,
            "message": (
                "snapd installed" if result["success"] else "Failed to install snapd"
            ),
        }

    def add_repository(self, repo_url: str, name: str | None = None) -> dict:
        del name
        repo_url = _validated_repository_url(repo_url)
        command = ["dnf", "config-manager", "--add-repo", repo_url]
        add_result = self.run_command(command, elevated=True)
        if add_result["success"]:
            update_result = self.run_command(["dnf", "makecache"], elevated=True)
            return {
                "success": update_result["success"],
                "details": [add_result, update_result],
            }
        return add_result

    def install_local_package(self, file_path: str) -> dict:
        package_path = _validated_local_package(file_path, (".rpm",))
        return self.run_command(
            ["dnf", "install", "-y", "--", str(package_path)], elevated=True
        )

    def search_package(self, query: str):
        query = _validated_search_query(query)
        result = self.run_command(["dnf", "search", query], capture_output=True)
        packages = []
        if result["success"]:
            for line in (result.get("stdout") or "").strip().splitlines():
                parts = line.split(" : ", 1)
                if len(parts) == 2 and not line.startswith("="):
                    packages.append(
                        {
                            "name": parts[0].strip().split(".")[0],
                            "description": parts[1].strip(),
                        }
                    )
                    if len(packages) >= 1_000:
                        break
        return {
            "success": result["success"],
            "packages": packages,
            "total": len(packages),
        }

    def get_package_info(self, package: str):
        package = _validated_package_name(package)
        result = self.run_command(["dnf", "info", package], capture_output=True)
        return {
            "success": result["success"],
            "info": _parse_package_metadata(result.get("stdout", "")),
        }

    def list_installed_packages(self):
        result = self.run_command(["dnf", "list", "installed"], capture_output=True)
        packages = []
        if result["success"]:
            for line in (result.get("stdout") or "").strip().splitlines():
                if not line.startswith("Installed") and not line.startswith("Last"):
                    parts = line.split()
                    if parts:
                        packages.append(parts[0].split(".")[0])
                        if len(packages) >= _MAX_FILESYSTEM_RESULTS:
                            break
        return {
            "success": result["success"],
            "packages": packages,
            "total": len(packages),
        }

    def list_upgradable_packages(self):
        result = self.run_command(["dnf", "check-update"], capture_output=True)
        packages = []
        if result.get("stdout"):
            for line in result["stdout"].strip().splitlines():
                parts = line.split()
                if len(parts) >= 3 and "." in parts[0]:
                    packages.append(parts[0].split(".")[0])
                    if len(packages) >= _MAX_FILESYSTEM_RESULTS:
                        break
        return {"success": True, "packages": packages, "total": len(packages)}

    def clean_package_cache(self):
        result = self.run_command(["dnf", "clean", "all"], elevated=True)
        return {
            "success": result["success"],
            "message": "DNF cache cleaned" if result["success"] else "Failed",
        }


class ZypperManager(SystemsManagerBase):
    def __init__(self, silent: bool = False):
        super().__init__(silent)
        self.not_found_msg = "No provider of"

    def install_applications(self, apps: list[str]) -> dict:
        apps = _validated_package_names(apps)
        results = {
            "natively_installed": [],
            "snap_installed": [],
            "failed": [],
            "success": True,
        }
        for app in apps:
            install_result = self.run_command(
                ["zypper", "install", "-y", "--", app],
                elevated=True,
                capture_output=True,
            )
            if install_result["success"]:
                results["natively_installed"].append(app)
            else:
                if self.not_found_msg in install_result.get("stderr", ""):
                    self.logger.info("Native install failed; trying snap")
                    snap_result = self.install_via_snap(app)
                    if snap_result["success"]:
                        results["snap_installed"].append(app)
                    else:
                        results["failed"].append(app)
                        results["success"] = False
                else:
                    results["failed"].append(app)
                    results["success"] = False
        return results

    def update(self, allow_on_k8s: bool = False) -> dict:
        guard = self._k8s_lifecycle_guard(allow_on_k8s)
        if guard is not None:
            return guard
        result = self.run_command(["zypper", "update", "-y"], elevated=True)
        return {
            "success": result["success"],
            "message": "System updated" if result["success"] else "Update failed",
            "details": result,
        }

    def clean(self) -> dict:
        result = self.run_command(["zypper", "clean", "--all"], elevated=True)
        return {
            "success": result["success"],
            "message": "Cache cleaned" if result["success"] else "Clean failed",
            "details": result,
        }

    def optimize(self) -> dict:
        result = self.run_command(["zypper", "rm", "-u"], elevated=True)
        return {
            "success": result["success"],
            "message": "Unneeded removed" if result["success"] else "Optimize failed",
            "details": result,
        }

    def install_snapd(self) -> dict:
        result = self.run_command(["zypper", "install", "-y", "snapd"], elevated=True)
        return {
            "success": result["success"],
            "details": result,
            "message": (
                "snapd installed" if result["success"] else "Failed to install snapd"
            ),
        }

    def add_repository(self, repo_url: str, name: str | None = None) -> dict:
        repo_url = _validated_repository_url(repo_url)
        name = _validated_repository_name(name)
        add_result = self.run_command(
            ["zypper", "addrepo", repo_url, name], elevated=True
        )
        if add_result["success"]:
            refresh_result = self.run_command(["zypper", "refresh"], elevated=True)
            return {
                "success": refresh_result["success"],
                "details": [add_result, refresh_result],
            }
        return add_result

    def install_local_package(self, file_path: str) -> dict:
        package_path = _validated_local_package(file_path, (".rpm",))
        return self.run_command(
            ["zypper", "install", "-y", "--", str(package_path)], elevated=True
        )

    def search_package(self, query: str):
        query = _validated_search_query(query)
        result = self.run_command(["zypper", "search", query], capture_output=True)
        packages = []
        if result["success"]:
            for line in (result.get("stdout") or "").strip().splitlines():
                parts = line.split("|")
                if len(parts) >= 3 and parts[0].strip() not in ("S", "-", ""):
                    packages.append(
                        {
                            "name": parts[1].strip(),
                            "description": parts[2].strip() if len(parts) > 2 else "",
                        }
                    )
                    if len(packages) >= 1_000:
                        break
        return {
            "success": result["success"],
            "packages": packages,
            "total": len(packages),
        }

    def get_package_info(self, package: str):
        package = _validated_package_name(package)
        result = self.run_command(["zypper", "info", package], capture_output=True)
        return {
            "success": result["success"],
            "info": _parse_package_metadata(result.get("stdout", "")),
        }

    def list_installed_packages(self):
        result = self.run_command(
            ["zypper", "search", "--installed-only"], capture_output=True
        )
        packages = []
        if result["success"]:
            for line in (result.get("stdout") or "").strip().splitlines():
                parts = line.split("|")
                if len(parts) >= 2 and parts[0].strip() == "i":
                    packages.append(parts[1].strip())
                    if len(packages) >= _MAX_FILESYSTEM_RESULTS:
                        break
        return {
            "success": result["success"],
            "packages": packages,
            "total": len(packages),
        }

    def list_upgradable_packages(self):
        result = self.run_command(["zypper", "list-updates"], capture_output=True)
        packages = []
        if result["success"]:
            for line in (result.get("stdout") or "").strip().splitlines():
                parts = line.split("|")
                if len(parts) >= 3 and parts[0].strip() not in ("S", "-", "", "v"):
                    packages.append(
                        parts[2].strip() if len(parts) > 2 else parts[1].strip()
                    )
                    if len(packages) >= _MAX_FILESYSTEM_RESULTS:
                        break
        return {
            "success": result["success"],
            "packages": packages,
            "total": len(packages),
        }

    def clean_package_cache(self):
        result = self.run_command(["zypper", "clean", "--all"], elevated=True)
        return {
            "success": result["success"],
            "message": "Zypper cache cleaned" if result["success"] else "Failed",
        }


class PacmanManager(SystemsManagerBase):
    def __init__(self, silent: bool = False):
        super().__init__(silent)
        self.not_found_msg = "target not found"

    def install_applications(self, apps: list[str]) -> dict:
        apps = _validated_package_names(apps)
        results = {
            "natively_installed": [],
            "snap_installed": [],
            "failed": [],
            "success": True,
        }
        for app in apps:
            install_result = self.run_command(
                ["pacman", "-S", "--noconfirm", "--", app],
                elevated=True,
                capture_output=True,
            )
            if install_result["success"]:
                results["natively_installed"].append(app)
            else:
                if self.not_found_msg in install_result.get("stderr", ""):
                    self.logger.info("Native install failed; trying snap")
                    snap_result = self.install_via_snap(app)
                    if snap_result["success"]:
                        results["snap_installed"].append(app)
                    else:
                        results["failed"].append(app)
                        results["success"] = False
                else:
                    results["failed"].append(app)
                    results["success"] = False
        return results

    def update(self, allow_on_k8s: bool = False) -> dict:
        guard = self._k8s_lifecycle_guard(allow_on_k8s)
        if guard is not None:
            return guard
        result = self.run_command(["pacman", "-Syu", "--noconfirm"], elevated=True)
        return {
            "success": result["success"],
            "message": "System updated" if result["success"] else "Update failed",
            "details": result,
        }

    def clean(self) -> dict:
        result = self.run_command(["pacman", "-Sc", "--noconfirm"], elevated=True)
        return {
            "success": result["success"],
            "message": "Cache cleaned" if result["success"] else "Clean failed",
            "details": result,
        }

    def optimize(self) -> dict:
        query = self.run_command(["pacman", "-Qdtq"], capture_output=True)
        orphans = [
            _validated_package_name(line)
            for line in (query.get("stdout") or "").splitlines()
            if line.strip()
        ][: _MAX_COMMAND_ARGS - 3]
        if not query["success"] or not orphans:
            return {
                "success": query["success"],
                "message": "No removable orphan packages found",
            }
        result = self.run_command(
            ["pacman", "-Rns", "--noconfirm", *orphans], elevated=True
        )
        return {
            "success": result["success"],
            "message": "Orphans removed" if result["success"] else "Optimize failed",
            "details": result,
        }

    def install_snapd(self) -> dict:
        result = self.run_command(
            ["pacman", "-S", "--noconfirm", "snapd"], elevated=True
        )
        return {
            "success": result["success"],
            "details": result,
            "message": (
                "snapd installed" if result["success"] else "Failed to install snapd"
            ),
        }

    def add_repository(self, repo_url: str, name: str | None = None) -> dict:
        del repo_url, name
        return {
            "success": False,
            "error": "Pacman repository-file mutation requires external governance",
        }

    def install_local_package(self, file_path: str) -> dict:
        package_path = _validated_local_package(
            file_path, (".pkg.tar.zst", ".pkg.tar.xz")
        )
        return self.run_command(
            ["pacman", "-U", "--noconfirm", "--", str(package_path)],
            elevated=True,
        )

    def search_package(self, query: str):
        query = _validated_search_query(query)
        result = self.run_command(["pacman", "-Ss", query], capture_output=True)
        packages = []
        if result["success"]:
            lines = (result.get("stdout") or "").strip().splitlines()
            for i in range(0, len(lines), 2):
                name_line = lines[i].strip()
                desc = lines[i + 1].strip() if i + 1 < len(lines) else ""
                parts = name_line.split("/", 1)
                if len(parts) == 2:
                    pkg_name = parts[1].split()[0]
                    packages.append({"name": pkg_name, "description": desc})
                    if len(packages) >= 1_000:
                        break
        return {
            "success": result["success"],
            "packages": packages,
            "total": len(packages),
        }

    def get_package_info(self, package: str):
        package = _validated_package_name(package)
        result = self.run_command(["pacman", "-Si", package], capture_output=True)
        if not result["success"]:
            result = self.run_command(["pacman", "-Qi", package], capture_output=True)
        return {
            "success": result["success"],
            "info": _parse_package_metadata(result.get("stdout", "")),
        }

    def list_installed_packages(self):
        result = self.run_command(["pacman", "-Qq"], capture_output=True)
        packages = []
        if result["success"]:
            packages = [
                p.strip()
                for p in (result.get("stdout") or "").strip().splitlines()
                if p.strip()
            ][:_MAX_FILESYSTEM_RESULTS]
        return {
            "success": result["success"],
            "packages": packages,
            "total": len(packages),
        }

    def list_upgradable_packages(self):
        result = self.run_command(["pacman", "-Qu"], capture_output=True)
        packages = []
        if result["success"]:
            for line in (result.get("stdout") or "").strip().splitlines():
                parts = line.split()
                if parts:
                    packages.append(parts[0])
                    if len(packages) >= _MAX_FILESYSTEM_RESULTS:
                        break
        return {
            "success": result["success"],
            "packages": packages,
            "total": len(packages),
        }

    def clean_package_cache(self):
        result = self.run_command(["pacman", "-Sc", "--noconfirm"], elevated=True)
        return {
            "success": result["success"],
            "message": "Pacman cache cleaned" if result["success"] else "Failed",
        }


class WindowsManager(SystemsManagerBase):
    def __init__(self, silent: bool = False):
        super().__init__(silent)
        self.winget_bin = "winget.exe"

    def install_applications(self, apps: list[str]) -> dict:
        apps = _validated_package_names(apps)
        results = {"installed": [], "failed": [], "success": True}
        for app in apps:
            install_cmd = [
                "winget",
                "install",
                "--id",
                app,
                "--silent",
                "--accept-package-agreements",
                "--accept-source-agreements",
            ]
            install_result = self.run_command(install_cmd)
            if install_result["success"]:
                results["installed"].append(app)
            else:
                results["failed"].append(app)
                results["success"] = False
                self.logger.error("Winget installation failed")
        return results

    def update(self, allow_on_k8s: bool = False) -> dict:
        guard = self._k8s_lifecycle_guard(allow_on_k8s)
        if guard is not None:
            return guard
        winget_result = self.run_command(
            [
                "winget",
                "upgrade",
                "--all",
                "--silent",
                "--accept-package-agreements",
                "--accept-source-agreements",
            ]
        )
        return {
            "success": winget_result["success"],
            "message": "Managed applications updated",
            "os_update": "requires external Windows Update governance",
            "details": {"winget": winget_result},
        }

    def clean(self) -> dict:
        result = self.run_command(["cleanmgr", "/lowdisk"])
        return {
            "success": result["success"],
            "message": "Cleanup initiated" if result["success"] else "Cleanup failed",
            "details": result,
        }

    def optimize(self) -> dict:
        clean_result = self.run_command(["cleanmgr", "/lowdisk"])
        defrag_result = self.run_command(
            [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                "Optimize-Volume -DriveLetter C",
            ],
            elevated=True,
        )
        overall_success = clean_result["success"] and defrag_result["success"]
        return {
            "success": overall_success,
            "message": (
                "System optimized" if overall_success else "Partial optimization"
            ),
            "details": {"cleanup": clean_result, "defrag": defrag_result},
        }

    def list_windows_features(self) -> list[dict]:
        cmd = [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            "Get-WindowsOptionalFeature -Online | ConvertTo-Json -Depth 3",
        ]
        result = self.run_command(cmd, capture_output=True)
        if result["success"]:
            try:
                features = json.loads(result["stdout"])
                if isinstance(features, list):
                    return features
                else:
                    return [features]
            except json.JSONDecodeError:
                self.logger.error("Failed to parse features JSON")
                return []
        else:
            self.logger.error("Failed to list features")
            return []

    def enable_windows_features(self, features: list[str]) -> dict:
        if not isinstance(features, list) or not 1 <= len(features) <= 64:
            raise ValueError("Invalid Windows feature list")
        results = {"enabled": [], "failed": [], "success": True}
        for feature in features:
            feature = self._validated_service_name(feature)
            cmd = [
                "powershell.exe",
                "Enable-WindowsOptionalFeature",
                "-Online",
                "-FeatureName",
                feature,
                "-NoRestart",
            ]
            enable_result = self.run_command(cmd, elevated=True)
            if enable_result["success"]:
                results["enabled"].append(feature)
            else:
                results["failed"].append(feature)
                results["success"] = False
                self.logger.error("Windows feature enable failed")
        return results

    def disable_windows_features(self, features: list[str]) -> dict:
        if not isinstance(features, list) or not 1 <= len(features) <= 64:
            raise ValueError("Invalid Windows feature list")
        results = {"disabled": [], "failed": [], "success": True}
        for feature in features:
            feature = self._validated_service_name(feature)
            cmd = [
                "powershell.exe",
                "Disable-WindowsOptionalFeature",
                "-Online",
                "-FeatureName",
                feature,
                "-NoRestart",
            ]
            disable_result = self.run_command(cmd, elevated=True)
            if disable_result["success"]:
                results["disabled"].append(feature)
            else:
                results["failed"].append(feature)
                results["success"] = False
                self.logger.error("Windows feature disable failed")
        return results

    def install_snapd(self) -> dict:
        return {"success": False, "error": "Snap not supported on Windows"}

    def add_repository(self, repo_url: str, name: str | None = None) -> dict:
        return {
            "success": False,
            "error": "Repository addition not supported on Windows",
        }

    def install_local_package(self, file_path: str) -> dict:
        return {
            "success": False,
            "error": "Local package installation not supported on Windows",
        }

    def search_package(self, query: str):
        query = _validated_search_query(query)
        result = self.run_command(
            [self.winget_bin, "search", query, "--accept-source-agreements"],
            capture_output=True,
        )
        packages = _parse_package_table(result.get("stdout", ""))
        return {
            "success": result["success"],
            "packages": packages,
            "total": len(packages),
        }

    def get_package_info(self, package: str):
        package = _validated_package_name(package)
        result = self.run_command(
            [self.winget_bin, "show", package, "--accept-source-agreements"],
            capture_output=True,
        )
        return {
            "success": result["success"],
            "info": _parse_package_metadata(result.get("stdout", "")),
        }

    def list_installed_packages(self):
        result = self.run_command(
            [self.winget_bin, "list", "--accept-source-agreements"],
            capture_output=True,
        )
        packages = _parse_package_table(result.get("stdout", ""))
        return {
            "success": result["success"],
            "packages": packages,
            "total": len(packages),
        }

    def list_upgradable_packages(self):
        result = self.run_command(
            [self.winget_bin, "upgrade", "--accept-source-agreements"],
            capture_output=True,
        )
        packages = _parse_package_table(result.get("stdout", ""))
        return {
            "success": result["success"],
            "packages": packages,
            "total": len(packages),
        }

    def clean_package_cache(self):
        result = self.run_command(
            [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                r"Remove-Item -Path $env:LOCALAPPDATA\Packages\Microsoft.DesktopAppInstaller_*\LocalState\DiagOutputDir\* -Recurse -Force -ErrorAction SilentlyContinue",
            ],
        )
        return {
            "success": result["success"],
            "message": "Windows package cache cleanup completed",
        }


def detect_and_create_manager(silent: bool | None = False) -> SystemsManagerBase:
    """
    Detect the current operating system and return the appropriate SystemsManager instance.
    """
    silent_bool = bool(silent)
    sys_name = platform.system()
    if sys_name == "Windows":
        return WindowsManager(silent_bool)
    elif sys_name == "Linux":
        dist_id = distro.id()
        if dist_id in ["ubuntu", "debian"]:
            return AptManager(silent_bool)
        elif dist_id in ["rhel", "ol", "centos"]:
            return DnfManager(silent_bool)
        elif dist_id == "sles":
            return ZypperManager(silent_bool)
        elif dist_id == "arch":
            return PacmanManager(silent_bool)
        else:
            raise NotImplementedError(f"Unsupported Linux distro: {dist_id}")
    else:
        raise NotImplementedError(f"Unsupported OS: {sys_name}")


def systems_manager():
    print(f"systems_manager v{__version__}")
    parser = argparse.ArgumentParser(
        add_help=False, description="System Manager Utility"
    )
    parser.add_argument(
        "-c", "--clean", action="store_true", help="Clean system resources"
    )
    parser.add_argument(
        "-s", "--silent", action="store_true", help="Run in silent mode"
    )
    parser.add_argument(
        "-u", "--update", action="store_true", help="Update system packages"
    )
    parser.add_argument(
        "-i",
        "--install",
        type=str,
        help="Comma-separated list of applications to install",
    )
    parser.add_argument(
        "-p",
        "--python",
        type=str,
        help="Comma-separated list of Python modules to install",
    )
    parser.add_argument("-o", "--optimize", action="store_true", help="Optimize system")
    parser.add_argument("--os-stats", action="store_true", help="Display OS statistics")
    parser.add_argument(
        "--hw-stats", action="store_true", help="Display hardware statistics"
    )
    parser.add_argument(
        "-e",
        "--enable-features",
        type=str,
        help="Comma-separated list of features to enable (Windows only)",
    )
    parser.add_argument(
        "-d",
        "--disable-features",
        type=str,
        help="Comma-separated list of features to disable (Windows only)",
    )
    parser.add_argument(
        "-l",
        "--list-features",
        action="store_true",
        help="List available features (Windows only)",
    )
    parser.add_argument(
        "--add-repo", type=str, help="Add upstream repository: url[:name] (Linux only)"
    )
    parser.add_argument(
        "--install-local",
        type=str,
        help="Install local package files, comma-separated (Linux only)",
    )

    parser.add_argument("--help", action="store_true", help="Show usage")

    args = parser.parse_args()

    if hasattr(args, "help") and args.help:
        parser.print_help()
        sys.exit(0)

    apps = args.install.split(",") if args.install else []
    python_modules = args.python.split(",") if args.python else []
    enable_features_list = (
        args.enable_features.split(",") if args.enable_features else []
    )
    disable_features_list = (
        args.disable_features.split(",") if args.disable_features else []
    )
    install = bool(args.install)
    update = args.update
    clean = args.clean
    optimize = args.optimize
    install_python = bool(args.python)
    os_stats = args.os_stats
    hw_stats = args.hw_stats
    silent = args.silent
    list_features = args.list_features
    enable_features = bool(args.enable_features)
    disable_features = bool(args.disable_features)
    add_repo = args.add_repo
    install_local = args.install_local

    manager = detect_and_create_manager(silent)

    if update:
        manager.update()
    if install:
        manager.install_applications(apps)
    if install_python:
        manager.install_python_modules(python_modules)
    if clean:
        manager.clean()
    if optimize:
        manager.optimize()
    if add_repo:
        parts = add_repo.split(":")
        url = parts[0]
        name = parts[1] if len(parts) > 1 else None
        manager.add_repository(url, name)
    if install_local:
        files = [f.strip() for f in install_local.split(",")]
        for f in files:
            manager.install_local_package(f)
    if os_stats:
        print(json.dumps(manager.get_os_statistics(), indent=2))
    if hw_stats:
        print(json.dumps(manager.get_hardware_statistics(), indent=2))
    if list_features:
        if isinstance(manager, WindowsManager):
            features = manager.list_windows_features()
            print(json.dumps(features, indent=2))
        else:
            print("Feature listing is only available on Windows.")
    if enable_features:
        if isinstance(manager, WindowsManager):
            manager.enable_windows_features(enable_features_list)
        else:
            print("Feature enabling is only available on Windows.")
    if disable_features:
        if isinstance(manager, WindowsManager):
            manager.disable_windows_features(disable_features_list)
        else:
            print("Feature disabling is only available on Windows.")

    print("Done!")


def main() -> None:
    """Run the systems-manager command-line interface."""
    systems_manager()


if __name__ == "__main__":
    main()
