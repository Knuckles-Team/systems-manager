"""Focused tests for the governed agent entry point."""

from __future__ import annotations

from argparse import Namespace
from pathlib import Path
from unittest.mock import Mock

import pytest

import systems_manager.agent_server as agent_module


def _args(config: Path, workspace: Path, **overrides) -> Namespace:
    values = {
        "debug": False,
        "mcp_url": None,
        "mcp_config": str(config),
        "host": "localhost",
        "port": 9009,
        "provider": "openai",
        "model_id": "test-model",
        "base_url": None,
        "api_key": None,
        "custom_skills_directory": None,
        "workspace": str(workspace),
        "web": False,
        "terminal": False,
        "web_logs": False,
        "insecure": False,
        "otel": False,
        "otel_endpoint": None,
        "otel_headers": None,
        "otel_public_key": None,
        "otel_secret_key": None,
        "otel_protocol": "http/protobuf",
    }
    values.update(overrides)
    return Namespace(**values)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("https://mcp.example.test/mcp", "https://mcp.example.test/mcp"),
        ("http://localhost:8010/mcp", "http://localhost:8010/mcp"),
        (None, None),
    ],
)
def test_validated_runtime_url_accepts_safe_endpoints(value, expected):
    assert agent_module._validated_runtime_url(value, label="test URL") == expected


@pytest.mark.parametrize(
    "value",
    [
        "http://mcp.example.test/mcp",
        "https://user:secret@mcp.example.test/mcp",
        "file:///tmp/socket",
        "https://mcp.example.test/mcp?token=secret",
    ],
)
def test_validated_runtime_url_rejects_unsafe_endpoints(value):
    with pytest.raises(ValueError):
        agent_module._validated_runtime_url(value, label="test URL")


def test_explicit_runtime_path_has_no_cwd_fallback(tmp_path):
    assert (
        agent_module._explicit_runtime_path(None, label="optional runtime path") is None
    )
    with pytest.raises(FileNotFoundError):
        agent_module._explicit_runtime_path(
            str(tmp_path / "missing.json"), label="runtime file"
        )


def test_remote_listener_fails_closed_without_real_auth(monkeypatch):
    for name in (
        "SYSTEMS_MANAGER_ALLOW_REMOTE_AGENT_SERVER",
        "ENABLE_API_AUTH",
        "AGENT_API_KEY",
        "AUTH_JWT_JWKS_URI",
        "AUTH_JWT_ISSUER",
        "AUTH_JWT_AUDIENCE",
        "SERVER_TLS_TERMINATED",
        "SERVER_TRUSTED_PROXY_CIDRS",
        "SERVER_TLS_CERTFILE",
        "SERVER_TLS_KEYFILE",
    ):
        monkeypatch.delenv(name, raising=False)

    with pytest.raises(PermissionError, match="TLS"):
        agent_module._validate_remote_agent_boundary("0.0.0.0", debug=False)


def test_remote_listener_accepts_configured_jwt_boundary(monkeypatch):
    monkeypatch.setenv("SYSTEMS_MANAGER_ALLOW_REMOTE_AGENT_SERVER", "true")
    monkeypatch.setenv("AUTH_JWT_JWKS_URI", "https://identity.example.invalid/jwks")
    monkeypatch.setenv("AUTH_JWT_ISSUER", "https://identity.example.invalid")
    monkeypatch.setenv("AUTH_JWT_AUDIENCE", "agent-services")
    monkeypatch.setenv("SERVER_TLS_TERMINATED", "true")
    monkeypatch.setenv("SERVER_TRUSTED_PROXY_CIDRS", "192.0.2.0/24")

    agent_module._validate_remote_agent_boundary("0.0.0.0", debug=False)


def test_remote_listener_rejects_debug_even_when_authenticated(monkeypatch):
    monkeypatch.setenv("SYSTEMS_MANAGER_ALLOW_REMOTE_AGENT_SERVER", "true")
    monkeypatch.setenv("AUTH_JWT_JWKS_URI", "https://identity.example.invalid/jwks")
    monkeypatch.setenv("AUTH_JWT_ISSUER", "https://identity.example.invalid")
    monkeypatch.setenv("AUTH_JWT_AUDIENCE", "agent-services")
    monkeypatch.setenv("SERVER_TLS_TERMINATED", "true")
    monkeypatch.setenv("SERVER_TRUSTED_PROXY_CIDRS", "192.0.2.0/24")

    with pytest.raises(PermissionError, match="Debug"):
        agent_module._validate_remote_agent_boundary("0.0.0.0", debug=True)


def test_agent_server_uses_supported_agent_utilities_api(tmp_path, monkeypatch):
    config = tmp_path / "mcp_config.json"
    config.write_text('{"mcpServers": {}}', encoding="utf-8")
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    parser = Mock()
    parser.parse_args.return_value = _args(config, workspace)
    create_server = Mock()
    initialize = Mock()
    monkeypatch.setattr(agent_module, "create_agent_parser", Mock(return_value=parser))
    monkeypatch.setattr(agent_module, "create_agent_server", create_server)
    monkeypatch.setattr(agent_module, "initialize_workspace", initialize)
    monkeypatch.setattr(
        agent_module,
        "load_identity",
        Mock(return_value={"name": "Systems Manager", "content": "System prompt"}),
    )

    agent_module.agent_server()

    initialize.assert_called_once_with()
    create_server.assert_called_once()
    kwargs = create_server.call_args.kwargs
    assert kwargs["mcp_config"] == str(config)
    assert kwargs["workspace"] == str(workspace)
    assert kwargs["name"] == "Systems Manager"
    assert kwargs["system_prompt"] == "System prompt"
    assert "ssl_verify" not in kwargs
    assert kwargs["custom_headers"] is None


def test_reference_mcp_configuration_is_current_and_value_free():
    config = Path(agent_module.__file__).parents[1] / "mcp_config.json"
    rendered = config.read_text(encoding="utf-8")
    assert '"systems-manager"' in rendered
    assert '"MCP_TOOL_MODE": "intent"' in rendered
    assert '"SYSTEMS_MANAGER_BMC_CREDENTIALS": "env://' in rendered
