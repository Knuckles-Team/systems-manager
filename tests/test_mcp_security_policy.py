"""Focused tests for the systems-manager MCP privilege boundary."""

import ast
import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from fastmcp import FastMCP

from systems_manager import mcp_server as server


class _Message:
    def __init__(self, name=None, arguments=None):
        self.name = name
        self.arguments = arguments


class _Context:
    def __init__(self, name=None, arguments=None, *, message=True):
        self.message = _Message(name, arguments) if message else None


async def _allowed(_context):
    return {"success": True}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "context",
    [
        _Context(message=False),
        _Context(None, {}),
        _Context("unknown_tool", {}),
        _Context("sm_advanced_operations", []),
        _Context(
            "sm_file_operations",
            {"action": "manage_file", "file_action": "chmod"},
        ),
        _Context("sm_system_operations", {"action": "unsupported"}),
    ],
)
async def test_malformed_unknown_and_unclassified_calls_fail_closed(
    monkeypatch, context
):
    monkeypatch.setenv("SYSTEMS_MANAGER_ALLOW_HOST_MUTATIONS", "true")
    monkeypatch.setenv("SYSTEMS_MANAGER_ALLOW_FILESYSTEM_MUTATIONS", "true")
    with pytest.raises(PermissionError):
        await server.SystemsSecurityMiddleware().on_call_tool(context, _allowed)


@pytest.mark.asyncio
async def test_filesystem_mutation_requires_its_distinct_gate(monkeypatch):
    monkeypatch.setenv("SYSTEMS_MANAGER_ALLOW_HOST_MUTATIONS", "true")
    monkeypatch.delenv("SYSTEMS_MANAGER_ALLOW_FILESYSTEM_MUTATIONS", raising=False)
    context = _Context(
        "sm_file_operations", {"action": "manage_file", "file_action": "create"}
    )
    with pytest.raises(PermissionError, match="filesystem mutation"):
        await server.SystemsSecurityMiddleware().on_call_tool(context, _allowed)


@pytest.mark.asyncio
async def test_filesystem_read_requires_sensitive_read_gate(monkeypatch):
    monkeypatch.delenv("SYSTEMS_MANAGER_ALLOW_SENSITIVE_READS", raising=False)
    context = _Context(
        "sm_file_operations", {"action": "manage_file", "file_action": "read"}
    )
    with pytest.raises(PermissionError, match="Sensitive host reads"):
        await server.SystemsSecurityMiddleware().on_call_tool(context, _allowed)


@pytest.mark.asyncio
async def test_host_mutations_are_serialized_process_wide(monkeypatch):
    monkeypatch.setenv("SYSTEMS_MANAGER_ALLOW_HOST_MUTATIONS", "true")
    active = 0
    maximum = 0

    async def mutation(context):
        nonlocal active, maximum
        active += 1
        maximum = max(maximum, active)
        await asyncio.sleep(0)
        active -= 1
        return context.message.arguments["action"]

    middleware = server.SystemsSecurityMiddleware()
    results = await asyncio.gather(
        middleware.on_call_tool(
            _Context("sm_advanced_operations", {"action": "install_uv"}), mutation
        ),
        middleware.on_call_tool(
            _Context("sm_system_operations", {"action": "update"}), mutation
        ),
    )
    assert results == ["install_uv", "update"]
    assert maximum == 1


@pytest.mark.asyncio
async def test_approval_is_canonical_bounded_and_fails_closed():
    class _ApprovalContext:
        prompt = ""

        async def elicit(self, prompt, *, response_type):
            assert response_type is bool
            self.prompt = prompt
            return SimpleNamespace(action="accept", data=True)

    context = _ApprovalContext()
    assert await server._mutation_approved(context, "update\npackages", "target\rhost")
    assert context.prompt.startswith("SYSTEMS MANAGER MUTATION APPROVAL\nAction: ")
    assert "update packages" in context.prompt
    assert "target host" in context.prompt
    assert len(context.prompt) < 800
    assert await server._mutation_approved(None, "update") is False


@pytest.mark.asyncio
async def test_blocking_work_is_bounded(monkeypatch):
    active = 0
    maximum = 0

    async def fake_run_blocking(function, *args, **kwargs):
        nonlocal active, maximum
        active += 1
        maximum = max(maximum, active)
        await asyncio.sleep(0)
        active -= 1
        return function(*args, **kwargs)

    monkeypatch.setattr(server, "_agent_run_blocking", fake_run_blocking)
    results = await asyncio.gather(
        *(server.run_blocking(lambda value: value, value) for value in range(6))
    )
    assert results == list(range(6))
    assert maximum <= server._MAX_BLOCKING_OPERATIONS


def test_blocking_limiter_does_not_leak_across_event_loops(monkeypatch):
    async def fake_run_blocking(function, *args, **kwargs):
        await asyncio.sleep(0)
        return function(*args, **kwargs)

    async def exercise():
        return await asyncio.gather(
            *(server.run_blocking(lambda value: value, value) for value in range(6))
        )

    monkeypatch.setattr(server, "_agent_run_blocking", fake_run_blocking)
    assert asyncio.run(exercise()) == list(range(6))
    assert asyncio.run(exercise()) == list(range(6))


def test_startup_invariant_rejects_unclassified_tool():
    mcp = FastMCP("policy-test")

    @mcp.tool()
    def unclassified_tool() -> str:
        return "unsafe"

    with pytest.raises(RuntimeError, match="Unclassified MCP tools"):
        server._assert_registered_tools_are_classified(mcp)


def test_registered_policy_is_complete():
    tree = ast.parse(Path(server.__file__).read_text(encoding="utf-8"))
    decorated_tools = {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and any(
            isinstance(decorator, ast.Call)
            and isinstance(decorator.func, ast.Attribute)
            and decorator.func.attr == "tool"
            for decorator in node.decorator_list
        )
    }
    assert decorated_tools <= server._ALL_CLASSIFIED_TOOLS
    assert {
        "sm_system_operations",
        "sm_file_operations",
        "sm_firewall_operations",
        "systems_ingest_host",
    } <= decorated_tools


@pytest.mark.asyncio
async def test_capability_report_discloses_status_not_paths(monkeypatch, tmp_path):
    async def inline_run_blocking(function, *args, **kwargs):
        return function(*args, **kwargs)

    monkeypatch.setenv("SYSTEMS_MANAGER_FILESYSTEM_ROOT", str(tmp_path))
    monkeypatch.setenv("SYSTEMS_MANAGER_ALLOW_SENSITIVE_READS", "true")
    monkeypatch.setattr(server, "run_blocking", inline_run_blocking)
    mcp = FastMCP("capability-test")
    server.register_misc_tools(mcp)
    tool = next(
        component
        for component in mcp._local_provider._components.values()
        if component.name == "get_management_capabilities"
    )
    with patch.object(server, "detect_and_create_manager", return_value=Mock()):
        result = await tool.fn()
    assert result["success"] is True
    assert result["managed_root"]["configured"] is True
    assert result["managed_root"]["path_disclosed"] is False
    assert str(tmp_path) not in repr(result)
    assert "policy" in result and "transport_boundary" in result


def test_network_transport_requires_authentication_even_on_loopback():
    mcp = Mock(auth=None)
    args = SimpleNamespace(
        transport="streamable-http",
        auth_type="none",
        host="localhost",
        port=8000,
    )
    with (
        patch.object(server, "get_mcp_instance", return_value=(args, mcp, [])),
        patch.object(server, "apply_served_security_profile") as apply_profile,
    ):
        with pytest.raises(SystemExit) as exc:
            server.mcp_server()
    assert exc.value.code == 2
    mcp.run.assert_not_called()
    apply_profile.assert_not_called()


def test_authenticated_network_transport_can_start():
    mcp = Mock(auth=object())
    args = SimpleNamespace(
        transport="streamable-http",
        auth_type="static",
        host="localhost",
        port=8000,
    )
    with (
        patch.object(server, "get_mcp_instance", return_value=(args, mcp, [])),
        patch.object(server, "apply_served_security_profile") as apply_profile,
        patch.object(
            server, "mcp_network_run_kwargs", return_value={"ssl_verify": True}
        ) as network_kwargs,
    ):
        server.mcp_server()
    apply_profile.assert_called_once_with(
        "streamable-http", transport_auth_configured=True
    )
    network_kwargs.assert_called_once_with(args)
    mcp.run.assert_called_once_with(
        transport="streamable-http",
        host="localhost",
        port=8000,
        ssl_verify=True,
    )
