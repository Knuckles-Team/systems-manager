#!/usr/bin/env python3
"""Least-privilege elevation helper for pre-authorized local deployments."""

import argparse
import json
import os
import re
import signal
import subprocess
from typing import NoReturn

_MAX_OUTPUT_BYTES = 64 * 1024
_MAX_TIMEOUT_SECONDS = 1800
_NAME_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9+_.@-]{0,127}")


def _result_and_exit(payload: dict, code: int = 0) -> NoReturn:
    print(json.dumps(payload, separators=(",", ":")))
    raise SystemExit(code)


def _configured_allowlist(variable: str) -> frozenset[str]:
    raw = os.environ.get(variable, "").strip()
    if not raw or len(raw) > 64 * 1024:
        return frozenset()
    try:
        values = json.loads(raw)
    except json.JSONDecodeError:
        return frozenset()
    if (
        not isinstance(values, list)
        or len(values) > 256
        or not all(
            isinstance(value, str) and _NAME_PATTERN.fullmatch(value)
            for value in values
        )
    ):
        return frozenset()
    return frozenset(values)


def _run(command: list[str], *, timeout: int = _MAX_TIMEOUT_SECONDS) -> dict:
    try:
        process = subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False,
            env={
                "LANG": "C.UTF-8",
                "LC_ALL": "C.UTF-8",
                "PATH": "/usr/bin:/usr/sbin:/bin:/sbin",
                "SYSTEMD_PAGER": "cat",
            },
            start_new_session=True,
        )
        stdout, stderr = process.communicate(timeout=timeout)
        if len(stdout) + len(stderr) > _MAX_OUTPUT_BYTES:
            return {"success": False, "error": "Helper output limit exceeded"}
        return {
            "success": process.returncode == 0,
            "returncode": process.returncode,
            **(
                {}
                if process.returncode == 0
                else {"error": "Elevated operation failed"}
            ),
        }
    except subprocess.TimeoutExpired:
        if os.name != "nt":
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        else:
            process.kill()
        process.communicate()
        return {"success": False, "error": "Elevated operation timed out"}
    except (OSError, ValueError):
        return {"success": False, "error": "Elevated operation failed"}


def _service_command(action: str, name: str) -> list[str]:
    if name not in _configured_allowlist(
        "SYSTEMS_MANAGER_HELPER_ALLOWED_SERVICES_JSON"
    ):
        raise PermissionError("Service is not deployment-allowlisted")
    return ["/usr/bin/systemctl", action, name]


def _package_command(action: str, name: str | None) -> list[str]:
    if action in {"install", "remove"}:
        if not name or name not in _configured_allowlist(
            "SYSTEMS_MANAGER_HELPER_ALLOWED_PACKAGES_JSON"
        ):
            raise PermissionError("Package is not deployment-allowlisted")
        return ["/usr/bin/apt-get", action, "-y", "--", name]
    commands = {
        "update": ["/usr/bin/apt-get", "update"],
        "upgrade": ["/usr/bin/apt-get", "upgrade", "-y"],
        "autoremove": ["/usr/bin/apt-get", "autoremove", "-y"],
        "autoclean": ["/usr/bin/apt-get", "autoclean"],
    }
    return commands[action]


def main() -> None:
    if not hasattr(os, "geteuid") or os.geteuid() != 0:
        _result_and_exit(
            {"success": False, "error": "Pre-authorized elevation is required"}, 1
        )

    parser = argparse.ArgumentParser(description="Systems Manager elevation helper")
    subparsers = parser.add_subparsers(dest="command", required=True)
    service = subparsers.add_parser("service")
    service.add_argument(
        "action", choices=["start", "stop", "restart", "status", "enable", "disable"]
    )
    service.add_argument("name")
    package = subparsers.add_parser("package")
    package.add_argument(
        "action",
        choices=["install", "remove", "update", "upgrade", "autoremove", "autoclean"],
    )
    package.add_argument("name", nargs="?")

    args = parser.parse_args()
    try:
        command = (
            _service_command(args.action, args.name)
            if args.command == "service"
            else _package_command(args.action, args.name)
        )
    except (KeyError, PermissionError, ValueError):
        _result_and_exit({"success": False, "error": "Operation is not permitted"}, 1)

    result = _run(command)
    _result_and_exit(result, 0 if result["success"] else 1)


if __name__ == "__main__":
    main()
