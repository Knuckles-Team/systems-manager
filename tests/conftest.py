#!/usr/bin/python
import pytest
from unittest.mock import Mock


@pytest.fixture
def mock_logger():
    """Mock logger fixture."""
    return Mock()


@pytest.fixture
def mock_windows_platform(monkeypatch):
    """Mock Windows platform fixture."""
    import platform

    monkeypatch.setattr(platform, "system", lambda: "Windows")
    yield


@pytest.fixture
def mock_linux_platform(monkeypatch):
    """Mock Linux platform fixture."""
    import platform
    import os
    import distro

    monkeypatch.setattr(platform, "system", lambda: "Linux")
    monkeypatch.setattr(os, "name", "posix")
    # Using a monkeypatch version that works with distro.id as a function or attribute
    try:
        monkeypatch.setattr(distro, "id", lambda: "ubuntu")
    except Exception:
        pass
    yield


@pytest.fixture
def mock_rhel_platform(monkeypatch):
    """Mock RHEL platform fixture."""
    import platform
    import os
    import distro

    monkeypatch.setattr(platform, "system", lambda: "Linux")
    monkeypatch.setattr(os, "name", "posix")
    try:
        monkeypatch.setattr(distro, "id", lambda: "rhel")
    except Exception:
        pass
    yield


@pytest.fixture
def mock_arch_platform(monkeypatch):
    """Mock Arch platform fixture."""
    import platform
    import os
    import distro

    monkeypatch.setattr(platform, "system", lambda: "Linux")
    monkeypatch.setattr(os, "name", "posix")
    try:
        monkeypatch.setattr(distro, "id", lambda: "arch")
    except Exception:
        pass
    yield


@pytest.fixture
def temp_home(tmp_path, monkeypatch):
    """Mock HOME directory fixture."""
    home = tmp_path / "home"
    home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setenv("HOMEPATH", str(home))
    monkeypatch.setenv("HOMEDRIVE", "C:")
    return home


@pytest.fixture
def mcp_context_mock():
    """Mock MCP context fixture."""
    mock_ctx = Mock()
    # Add async methods if needed, but for now just a Mock
    return mock_ctx


@pytest.fixture
def mock_requests_get(monkeypatch):
    """Mock requests.get fixture."""
    import requests

    mock_resp = Mock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"assets": []}
    mock_resp.content = b"fake content"
    mock_resp.raise_for_status = Mock()

    monkeypatch.setattr(requests, "get", lambda *args, **kwargs: mock_resp)
    return mock_resp
