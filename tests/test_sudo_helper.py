import json
from unittest.mock import patch

import pytest

from systems_manager import sudo_helper


def _printed_payload(mock_print):
    return json.loads(mock_print.call_args.args[0])


def test_sudo_helper_requires_pre_authorized_root():
    with (
        patch.object(sudo_helper.os, "geteuid", return_value=1000),
        patch("builtins.print") as mock_print,
        pytest.raises(SystemExit) as exc,
    ):
        sudo_helper.main()
    assert exc.value.code == 1
    assert _printed_payload(mock_print) == {
        "success": False,
        "error": "Pre-authorized elevation is required",
    }


def test_sudo_helper_service_allowlist_is_explicit(monkeypatch):
    monkeypatch.setenv(
        "SYSTEMS_MANAGER_HELPER_ALLOWED_SERVICES_JSON", '["example-service"]'
    )
    assert sudo_helper._service_command("restart", "example-service") == [
        "/usr/bin/systemctl",
        "restart",
        "example-service",
    ]
    with pytest.raises(PermissionError):
        sudo_helper._service_command("restart", "undeclared-service")


def test_sudo_helper_package_allowlist_is_explicit(monkeypatch):
    monkeypatch.setenv(
        "SYSTEMS_MANAGER_HELPER_ALLOWED_PACKAGES_JSON", '["example-package"]'
    )
    assert sudo_helper._package_command("install", "example-package") == [
        "/usr/bin/apt-get",
        "install",
        "-y",
        "--",
        "example-package",
    ]
    with pytest.raises(PermissionError):
        sudo_helper._package_command("remove", "undeclared-package")
    assert sudo_helper._package_command("update", None) == [
        "/usr/bin/apt-get",
        "update",
    ]


def test_sudo_helper_rejects_malformed_allowlists(monkeypatch):
    for value in ("not-json", "{}", '["bad;name"]', "[1]"):
        monkeypatch.setenv("SYSTEMS_MANAGER_HELPER_ALLOWED_SERVICES_JSON", value)
        with pytest.raises(PermissionError):
            sudo_helper._service_command("start", "bad;name")


def test_sudo_helper_main_returns_only_sanitized_result(monkeypatch):
    monkeypatch.setenv(
        "SYSTEMS_MANAGER_HELPER_ALLOWED_SERVICES_JSON", '["example-service"]'
    )
    with (
        patch.object(sudo_helper.os, "geteuid", return_value=0),
        patch(
            "sys.argv",
            ["systems-manager-helper", "service", "start", "example-service"],
        ),
        patch.object(
            sudo_helper,
            "_run",
            return_value={"success": False, "error": "Elevated operation failed"},
        ) as mock_run,
        patch("builtins.print") as mock_print,
        pytest.raises(SystemExit) as exc,
    ):
        sudo_helper.main()
    assert exc.value.code == 1
    mock_run.assert_called_once_with(["/usr/bin/systemctl", "start", "example-service"])
    assert _printed_payload(mock_print) == {
        "success": False,
        "error": "Elevated operation failed",
    }
