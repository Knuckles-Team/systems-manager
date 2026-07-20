"""Current Agent OS tool contracts exposed by systems-manager."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from systems_manager import agent_os_tools
from systems_manager.mcp_server import get_mcp_instance

args, mcp_server, middlewares = get_mcp_instance()


@pytest.fixture(autouse=True)
def _authorized_test_boundary(monkeypatch, tmp_path):
    monkeypatch.setenv("SYSTEMS_MANAGER_ALLOW_HOST_MUTATIONS", "true")
    monkeypatch.setenv("SYSTEMS_MANAGER_ALLOW_SENSITIVE_READS", "true")
    monkeypatch.setenv("SPECIALIST_REGISTRY_PATH", str(tmp_path / "registry"))
    monkeypatch.setenv("MCP_CONFIG_PATH", str(tmp_path / "mcp.json"))
    monkeypatch.setenv("PROJECT_ROOT", str(tmp_path))
    monkeypatch.setenv(
        "PERMISSIONS_SIGNING_KEY", "test-key-material-that-is-at-least-32-bytes"
    )

    async def approve(*_args, **_kwargs):
        return True

    monkeypatch.setattr(agent_os_tools, "ctx_confirm_destructive", approve)


def _result(response):
    return json.loads(response.content[0].text)


@pytest.mark.asyncio
async def test_identity_issue_pseudonymizes_subject_and_verify_is_current():
    with patch("systems_manager.agent_os_tools._get_permissions") as get_permissions:
        kernel = MagicMock()
        get_permissions.return_value = kernel
        kernel.derive_agent_id.return_value = "agent:opaque"
        identity = MagicMock()
        identity.agent_id = "agent:opaque"
        identity.role.value = "specialist"
        identity.issued_at = 1.0
        identity.expires_at = 0.0
        kernel.issue_identity.return_value = identity

        issued = _result(
            await mcp_server.call_tool(
                "sm_agent_identity_operations",
                arguments={
                    "action": "issue",
                    "agent_subject": "runtime-subject",
                    "role": "specialist",
                },
            )
        )
        assert issued == {
            "success": True,
            "agent_id": "agent:opaque",
            "role": "specialist",
            "issued_at": 1.0,
            "expires_at": 0.0,
        }
        kernel.derive_agent_id.assert_called_once_with("runtime-subject")
        kernel.issue_identity.assert_called_once_with(
            "agent:opaque", agent_os_tools.AgentRole.SPECIALIST
        )

        kernel.get_identity.return_value = identity
        kernel.verify_identity.return_value = True
        verified = _result(
            await mcp_server.call_tool(
                "sm_agent_identity_operations",
                arguments={"action": "verify", "agent_id": "agent:opaque"},
            )
        )
        assert verified["valid"] is True
        assert "signature" not in verified


@pytest.mark.asyncio
async def test_specialist_registry_uses_stable_minimal_results():
    with patch("systems_manager.agent_os_tools._get_registry") as get_registry:
        registry = MagicMock()
        get_registry.return_value = registry
        registry.install = AsyncMock(return_value="✓ installed")
        installed = _result(
            await mcp_server.call_tool(
                "sm_agent_specialist_operations",
                arguments={"action": "install", "package_name": "provider-skill"},
            )
        )
        assert installed == {"success": True, "package": "provider-skill"}

        package = MagicMock()
        package.name = "provider-skill"
        package.version = "1.0.0"
        package.tags = ["operations"]
        registry.list_installed.return_value = [package]
        listed = _result(
            await mcp_server.call_tool(
                "sm_agent_specialist_operations",
                arguments={"action": "list", "status": "installed"},
            )
        )
        assert listed["packages"] == [
            {"name": "provider-skill", "version": "1.0.0", "tags": ["operations"]}
        ]
        assert "description" not in listed["packages"][0]


@pytest.mark.asyncio
async def test_scheduler_projection_excludes_task_and_checkpoint_content():
    with patch("systems_manager.agent_os_tools._get_scheduler") as get_scheduler:
        scheduler = MagicMock()
        get_scheduler.return_value = scheduler
        process = MagicMock(
            id="proc:opaque",
            priority=1,
            state="running",
            token_quota=100,
            tokens_used=5,
        )
        process.task_description = "private task content"
        scheduler.get_process_table.return_value = [process]

        listed = _result(
            await mcp_server.call_tool(
                "sm_agent_scheduler_operations",
                arguments={"action": "list_processes"},
            )
        )
        assert listed["processes"] == [
            {
                "id": "proc:opaque",
                "priority": 1,
                "state": "running",
                "token_quota": 100,
                "tokens_used": 5,
            }
        ]
        assert "private task content" not in repr(listed)

        scheduler.preempt = AsyncMock(return_value="ckpt:private")
        preempted = _result(
            await mcp_server.call_tool(
                "sm_agent_scheduler_operations",
                arguments={"action": "preempt", "process_id": "proc:opaque"},
            )
        )
        assert preempted == {"success": True, "checkpoint_created": True}


@pytest.mark.asyncio
async def test_watchdog_outputs_exclude_paths_queries_and_pending_content():
    with patch("systems_manager.agent_os_tools._get_watcher") as get_watcher:
        watcher = MagicMock()
        get_watcher.return_value = watcher
        watcher.check_file_change.return_value = {
            "filepath": "private/path",
            "query": "private query",
            "pattern": "*.py",
            "priority": "LOW",
        }
        checked = _result(
            await mcp_server.call_tool(
                "sm_agent_watchdog_operations",
                arguments={"action": "check_change", "filepath": "runtime/path.py"},
            )
        )
        assert checked == {"triggered": True, "pattern": "*.py", "priority": "LOW"}

        rule = MagicMock(pattern="*.py", priority="LOW", cooldown=30)
        watcher.triggers = [rule]
        watcher.project_root = "private/root"
        listed = _result(
            await mcp_server.call_tool(
                "sm_agent_watchdog_operations",
                arguments={"action": "list_watchers"},
            )
        )
        assert listed == {
            "rules": [{"pattern": "*.py", "priority": "LOW", "cooldown": 30}],
            "count": 1,
        }

        watcher.drain_pending.return_value = [{"query": "private query"}]
        drained = _result(
            await mcp_server.call_tool(
                "sm_agent_watchdog_operations",
                arguments={"action": "drain_triggers"},
            )
        )
        assert drained == {"drained": True, "count": 1}


def test_removed_agent_os_surfaces_are_not_registered():
    names = {
        component.name
        for component in mcp_server._local_provider._components.values()
        if getattr(component, "name", None)
    }
    assert "sm_agent_policy_operations" not in names
    assert "sm_agent_maintenance_operations" not in names


def test_current_singleton_authorities_require_explicit_paths(monkeypatch, tmp_path):
    with (
        patch("systems_manager.agent_os_tools.CognitiveScheduler") as scheduler,
        patch("systems_manager.agent_os_tools.PermissionsKernel") as permissions,
        patch("systems_manager.agent_os_tools.AgentRegistry") as registry,
        patch("systems_manager.agent_os_tools.FileWatcher") as watcher,
    ):
        agent_os_tools._scheduler = None
        agent_os_tools._permissions = None
        agent_os_tools._registry = None
        agent_os_tools._watcher = None

        assert agent_os_tools._get_scheduler() is scheduler.return_value
        assert agent_os_tools._get_permissions() is permissions.return_value
        assert agent_os_tools._get_registry() is registry.return_value
        assert agent_os_tools._get_watcher() is watcher.return_value

        registry.assert_called_once_with(
            registry_path=str(tmp_path / "registry"),
            mcp_config_path=str(tmp_path / "mcp.json"),
        )

    agent_os_tools._registry = None
    monkeypatch.delenv("SPECIALIST_REGISTRY_PATH")
    with pytest.raises(ValueError, match="SPECIALIST_REGISTRY_PATH"):
        agent_os_tools._get_registry()
