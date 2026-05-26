import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from systems_manager import agent_os_tools
from systems_manager.agent_os_tools import (
    sm_agent_identity_operations,
    sm_agent_maintenance_operations,
    sm_agent_policy_operations,
    sm_agent_scheduler_operations,
    sm_agent_specialist_operations,
    sm_agent_watchdog_operations,
)
from systems_manager.mcp_server import get_mcp_instance

args, mcp_server, middlewares = get_mcp_instance()


def parse_mcp_result(res):
    text = getattr(res.content[0], "text", "")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


@pytest.mark.asyncio
async def test_identity_operations():
    with patch("systems_manager.agent_os_tools._get_permissions") as mock_get_perms:
        perms = MagicMock()
        mock_get_perms.return_value = perms

        identity_mock = MagicMock()
        identity_mock.agent_id = "agent-1"
        identity_mock.role.value = "specialist"
        identity_mock.issued_at = 1234
        identity_mock.expires_at = 5678
        identity_mock.signature = "abc" * 10
        perms.issue_identity.return_value = identity_mock

        # Action: issue
        res = await mcp_server.call_tool(
            "sm_agent_identity_operations",
            arguments={
                "action": "issue",
                "agent_name": "agent-test",
                "role": "specialist",
            },
        )
        data = parse_mcp_result(res)
        assert data["success"] is True
        assert data["agent_id"] == "agent-1"

        # Action: issue invalid role
        res_invalid = await mcp_server.call_tool(
            "sm_agent_identity_operations",
            arguments={
                "action": "issue",
                "agent_name": "agent-test",
                "role": "invalid",
            },
        )
        data_invalid = parse_mcp_result(res_invalid)
        assert data_invalid["success"] is False

        # Action: issue missing agent_name
        res_missing = await mcp_server.call_tool(
            "sm_agent_identity_operations",
            arguments={"action": "issue", "role": "specialist"},
        )
        data_missing = parse_mcp_result(res_missing)
        assert data_missing["success"] is False

        # Action: verify
        perms.get_identity.return_value = identity_mock
        perms.verify_identity.return_value = True
        res_verify = await mcp_server.call_tool(
            "sm_agent_identity_operations",
            arguments={"action": "verify", "agent_id": "agent-1"},
        )
        data_verify = parse_mcp_result(res_verify)
        assert data_verify["valid"] is True

        # Action: verify missing agent_id
        res_verify_missing = await mcp_server.call_tool(
            "sm_agent_identity_operations",
            arguments={"action": "verify"},
        )
        data_verify_missing = parse_mcp_result(res_verify_missing)
        assert data_verify_missing["success"] is False

        # Action: verify not found
        perms.get_identity.return_value = None
        res_verify_nf = await mcp_server.call_tool(
            "sm_agent_identity_operations",
            arguments={"action": "verify", "agent_id": "agent-1"},
        )
        data_verify_nf = parse_mcp_result(res_verify_nf)
        assert data_verify_nf["valid"] is False

        # Action: revoke
        perms._identities = {"agent-1": identity_mock}
        res_revoke = await mcp_server.call_tool(
            "sm_agent_identity_operations",
            arguments={"action": "revoke", "agent_id": "agent-1"},
        )
        data_revoke = parse_mcp_result(res_revoke)
        assert data_revoke["success"] is True

        # Action: revoke missing agent_id
        res_revoke_missing = await mcp_server.call_tool(
            "sm_agent_identity_operations",
            arguments={"action": "revoke"},
        )
        data_revoke_missing = parse_mcp_result(res_revoke_missing)
        assert data_revoke_missing["success"] is False

        # Action: revoke not found
        perms._identities = {}
        res_revoke_nf = await mcp_server.call_tool(
            "sm_agent_identity_operations",
            arguments={"action": "revoke", "agent_id": "agent-1"},
        )
        data_revoke_nf = parse_mcp_result(res_revoke_nf)
        assert data_revoke_nf["success"] is False

        # Action: list
        perms._identities = {"agent-1": identity_mock}
        perms.verify_identity.return_value = True
        res_list = await mcp_server.call_tool(
            "sm_agent_identity_operations",
            arguments={"action": "list"},
        )
        data_list = parse_mcp_result(res_list)
        assert data_list["count"] == 1
        assert data_list["identities"][0]["agent_id"] == "agent-1"

        # Action: unsupported (Direct Python call to hit the else branch)
        res_unsupported = await sm_agent_identity_operations(action="invalid_action")  # type: ignore
        assert res_unsupported["success"] is False


@pytest.mark.asyncio
async def test_policy_operations():
    with patch("systems_manager.agent_os_tools._get_permissions") as mock_get_perms:
        perms = MagicMock()
        mock_get_perms.return_value = perms

        policy_mock = MagicMock()
        policy_mock.allowed_tools = ["*"]
        policy_mock.denied_tools = []
        policy_mock.require_approval = False
        policy_mock.max_tokens_per_session = 100
        perms._policies = {"specialist": policy_mock}

        # Action: list
        res_list = await mcp_server.call_tool(
            "sm_agent_policy_operations",
            arguments={"action": "list"},
        )
        data_list = parse_mcp_result(res_list)
        assert data_list["count"] == 1
        assert data_list["policies"][0]["role"] == "specialist"

        # Action: get
        res_get = await mcp_server.call_tool(
            "sm_agent_policy_operations",
            arguments={"action": "get", "role": "specialist"},
        )
        data_get = parse_mcp_result(res_get)
        assert data_get["role"] == "specialist"

        # Action: get missing role
        res_get_missing = await mcp_server.call_tool(
            "sm_agent_policy_operations",
            arguments={"action": "get"},
        )
        data_get_missing = parse_mcp_result(res_get_missing)
        assert data_get_missing["success"] is False

        # Action: get not found
        res_get_nf = await mcp_server.call_tool(
            "sm_agent_policy_operations",
            arguments={"action": "get", "role": "invalid"},
        )
        data_get_nf = parse_mcp_result(res_get_nf)
        assert data_get_nf["success"] is False

        # Action: update
        res_update = await mcp_server.call_tool(
            "sm_agent_policy_operations",
            arguments={
                "action": "update",
                "role": "specialist",
                "allowed_tools": ["tool1"],
                "denied_tools": ["tool2"],
            },
        )
        data_update = parse_mcp_result(res_update)
        assert data_update["success"] is True
        assert policy_mock.allowed_tools == ["tool1"]
        assert policy_mock.denied_tools == ["tool2"]

        # Action: update missing role
        res_update_missing = await mcp_server.call_tool(
            "sm_agent_policy_operations",
            arguments={"action": "update"},
        )
        data_update_missing = parse_mcp_result(res_update_missing)
        assert data_update_missing["success"] is False

        # Action: update not found
        perms._policies = {}
        res_update_nf = await mcp_server.call_tool(
            "sm_agent_policy_operations",
            arguments={"action": "update", "role": "invalid"},
        )
        data_update_nf = parse_mcp_result(res_update_nf)
        assert data_update_nf["success"] is False

        # Action: reload
        perms._policies_path = "path/to/policies.json"
        res_reload = await mcp_server.call_tool(
            "sm_agent_policy_operations",
            arguments={"action": "reload"},
        )
        data_reload = parse_mcp_result(res_reload)
        assert data_reload["success"] is True

        # Action: reload no path
        perms._policies_path = None
        res_reload_nf = await mcp_server.call_tool(
            "sm_agent_policy_operations",
            arguments={"action": "reload"},
        )
        data_reload_nf = parse_mcp_result(res_reload_nf)
        assert data_reload_nf["success"] is False

        # Action: unsupported (Direct Python call to hit the else branch)
        res_unsupported = await sm_agent_policy_operations(action="invalid_action")  # type: ignore
        assert res_unsupported["success"] is False


@pytest.mark.asyncio
async def test_specialist_operations():
    with patch("systems_manager.agent_os_tools._get_registry") as mock_get_reg:
        registry = MagicMock()
        mock_get_reg.return_value = registry

        # Action: install
        registry.install = AsyncMock(return_value="✓ specialist installed")
        res_inst = await mcp_server.call_tool(
            "sm_agent_specialist_operations",
            arguments={"action": "install", "package_name": "specialist"},
        )
        data_inst = parse_mcp_result(res_inst)
        assert data_inst["success"] is True

        # Action: install missing package_name
        res_inst_missing = await mcp_server.call_tool(
            "sm_agent_specialist_operations",
            arguments={"action": "install"},
        )
        data_inst_missing = parse_mcp_result(res_inst_missing)
        assert data_inst_missing["success"] is False

        # Action: uninstall
        registry.uninstall = AsyncMock(return_value="✓ specialist uninstalled")
        res_uninst = await mcp_server.call_tool(
            "sm_agent_specialist_operations",
            arguments={"action": "uninstall", "package_name": "specialist"},
        )
        data_uninst = parse_mcp_result(res_uninst)
        assert data_uninst["success"] is True

        # Action: uninstall missing package_name
        res_uninst_missing = await mcp_server.call_tool(
            "sm_agent_specialist_operations",
            arguments={"action": "uninstall"},
        )
        data_uninst_missing = parse_mcp_result(res_uninst_missing)
        assert data_uninst_missing["success"] is False

        # Action: list
        package_mock = MagicMock()
        package_mock.name = "pkg1"
        package_mock.version = "1.0"
        package_mock.description = "pkg desc"
        registry.list_installed.return_value = [package_mock]
        registry.list_available.return_value = []

        res_list = await mcp_server.call_tool(
            "sm_agent_specialist_operations",
            arguments={"action": "list", "status": "installed"},
        )
        data_list = parse_mcp_result(res_list)
        assert data_list["count"] == 1

        res_list_avail = await mcp_server.call_tool(
            "sm_agent_specialist_operations",
            arguments={"action": "list", "status": "available"},
        )
        data_list_avail = parse_mcp_result(res_list_avail)
        assert data_list_avail["count"] == 0

        res_list_all = await mcp_server.call_tool(
            "sm_agent_specialist_operations",
            arguments={"action": "list", "status": "all"},
        )
        data_list_all = parse_mcp_result(res_list_all)
        assert data_list_all["count"] == 1

        # Action: search
        registry.search.return_value = [package_mock]
        res_search = await mcp_server.call_tool(
            "sm_agent_specialist_operations",
            arguments={"action": "search", "query": "pkg"},
        )
        data_search = parse_mcp_result(res_search)
        assert data_search["count"] == 1

        # Action: search missing query
        res_search_missing = await mcp_server.call_tool(
            "sm_agent_specialist_operations",
            arguments={"action": "search"},
        )
        data_search_missing = parse_mcp_result(res_search_missing)
        assert data_search_missing["success"] is False

        # Action: unsupported (Direct Python call to hit the else branch)
        res_unsupported = await sm_agent_specialist_operations(action="invalid_action")  # type: ignore
        assert res_unsupported["success"] is False


@pytest.mark.asyncio
async def test_scheduler_operations():
    with patch("systems_manager.agent_os_tools._get_scheduler") as mock_get_sched:
        scheduler = MagicMock()
        mock_get_sched.return_value = scheduler

        # Action: get_stats
        scheduler.get_stats.return_value = {"active": 1}
        res_stats = await mcp_server.call_tool(
            "sm_agent_scheduler_operations",
            arguments={"action": "get_stats"},
        )
        data_stats = parse_mcp_result(res_stats)
        assert data_stats["active"] == 1

        # Action: list_processes
        scheduler.get_process_table.return_value = [{"id": "p1"}]
        res_list = await mcp_server.call_tool(
            "sm_agent_scheduler_operations",
            arguments={"action": "list_processes"},
        )
        data_list = parse_mcp_result(res_list)
        assert data_list["count"] == 1

        # Action: preempt
        scheduler.preempt.return_value = {"checkpoint": True}
        res_pre = await mcp_server.call_tool(
            "sm_agent_scheduler_operations",
            arguments={"action": "preempt", "process_id": "p1"},
        )
        data_pre = parse_mcp_result(res_pre)
        assert data_pre["success"] is True

        # Action: preempt missing process_id
        res_pre_missing = await mcp_server.call_tool(
            "sm_agent_scheduler_operations",
            arguments={"action": "preempt"},
        )
        data_pre_missing = parse_mcp_result(res_pre_missing)
        assert data_pre_missing["success"] is False

        # Action: preempt not running
        scheduler.preempt.return_value = None
        res_pre_nf = await mcp_server.call_tool(
            "sm_agent_scheduler_operations",
            arguments={"action": "preempt", "process_id": "p2"},
        )
        data_pre_nf = parse_mcp_result(res_pre_nf)
        assert data_pre_nf["success"] is False

        # Action: reset_quota
        proc_mock = MagicMock()
        scheduler._processes = {"p1": proc_mock}
        res_reset = await mcp_server.call_tool(
            "sm_agent_scheduler_operations",
            arguments={"action": "reset_quota", "process_id": "p1"},
        )
        data_reset = parse_mcp_result(res_reset)
        assert data_reset["success"] is True
        assert proc_mock.tokens_used == 0

        # Action: reset_quota missing process_id
        res_reset_missing = await mcp_server.call_tool(
            "sm_agent_scheduler_operations",
            arguments={"action": "reset_quota"},
        )
        data_reset_missing = parse_mcp_result(res_reset_missing)
        assert data_reset_missing["success"] is False

        # Action: reset_quota not found
        scheduler._processes = {}
        res_reset_nf = await mcp_server.call_tool(
            "sm_agent_scheduler_operations",
            arguments={"action": "reset_quota", "process_id": "p2"},
        )
        data_reset_nf = parse_mcp_result(res_reset_nf)
        assert data_reset_nf["success"] is False

        # Action: unsupported (Direct Python call to hit the else branch)
        res_unsupported = await sm_agent_scheduler_operations(action="invalid_action")  # type: ignore
        assert res_unsupported["success"] is False


@pytest.mark.asyncio
async def test_watchdog_operations():
    with patch("systems_manager.agent_os_tools._get_watcher") as mock_get_watch:
        watcher = MagicMock()
        mock_get_watch.return_value = watcher

        # Action: check_change
        watcher.check_file_change.return_value = {"pattern": "*.py"}
        res_check = await mcp_server.call_tool(
            "sm_agent_watchdog_operations",
            arguments={"action": "check_change", "filepath": "main.py"},
        )
        data_check = parse_mcp_result(res_check)
        assert data_check["triggered"] is True

        # Action: check_change missing filepath
        res_check_missing = await mcp_server.call_tool(
            "sm_agent_watchdog_operations",
            arguments={"action": "check_change"},
        )
        data_check_missing = parse_mcp_result(res_check_missing)
        assert data_check_missing["success"] is False

        # Action: check_change not triggered
        watcher.check_file_change.return_value = None
        res_check_nt = await mcp_server.call_tool(
            "sm_agent_watchdog_operations",
            arguments={"action": "check_change", "filepath": "main.py"},
        )
        data_check_nt = parse_mcp_result(res_check_nt)
        assert data_check_nt["triggered"] is False

        # Action: list_watchers
        trigger_mock = MagicMock()
        trigger_mock.pattern = "*.py"
        trigger_mock.priority = "HIGH"
        trigger_mock.cooldown = 10
        trigger_mock.query = "graph query"
        watcher.triggers = [trigger_mock]
        watcher.project_root = "/root"

        res_list = await mcp_server.call_tool(
            "sm_agent_watchdog_operations",
            arguments={"action": "list_watchers"},
        )
        data_list = parse_mcp_result(res_list)
        assert data_list["count"] == 1
        assert data_list["rules"][0]["pattern"] == "*.py"

        # Action: drain_triggers
        watcher.drain_pending.return_value = ["trigger1"]
        res_drain = await mcp_server.call_tool(
            "sm_agent_watchdog_operations",
            arguments={"action": "drain_triggers"},
        )
        data_drain = parse_mcp_result(res_drain)
        assert data_drain["count"] == 1

        # Action: unsupported (Direct Python call to hit the else branch)
        res_unsupported = await sm_agent_watchdog_operations(action="invalid_action")  # type: ignore
        assert res_unsupported["success"] is False


@pytest.mark.asyncio
async def test_maintenance_operations():
    with patch("systems_manager.agent_os_tools._get_maintenance") as mock_get_maint:
        cron = MagicMock()
        mock_get_maint.return_value = cron

        # Action: list_tasks
        cron.summary.return_value = {"budget": 10}
        task_mock = MagicMock()
        task_mock.id = "t1"
        task_mock.name = "task1"
        task_mock.frequency.value = "daily"
        task_mock.priority = "LOW"
        task_mock.enabled = True
        task_mock.last_status = "SUCCESS"
        cron.tasks = [task_mock]

        res_list = await mcp_server.call_tool(
            "sm_agent_maintenance_operations",
            arguments={"action": "list_tasks"},
        )
        data_list = parse_mcp_result(res_list)
        assert data_list["tasks"][0]["id"] == "t1"

        # Action: run_now
        cron.is_budget_available.return_value = True
        task_mock.query = "match (n) return n"
        res_run = await mcp_server.call_tool(
            "sm_agent_maintenance_operations",
            arguments={"action": "run_now", "task_id": "t1"},
        )
        data_run = parse_mcp_result(res_run)
        assert data_run["success"] is True

        # Action: run_now missing task_id
        res_run_missing = await mcp_server.call_tool(
            "sm_agent_maintenance_operations",
            arguments={"action": "run_now"},
        )
        data_run_missing = parse_mcp_result(res_run_missing)
        assert data_run_missing["success"] is False

        # Action: run_now not found
        res_run_nf = await mcp_server.call_tool(
            "sm_agent_maintenance_operations",
            arguments={"action": "run_now", "task_id": "t2"},
        )
        data_run_nf = parse_mcp_result(res_run_nf)
        assert data_run_nf["success"] is False

        # Action: run_now budget exhausted
        cron.is_budget_available.return_value = False
        res_run_be = await mcp_server.call_tool(
            "sm_agent_maintenance_operations",
            arguments={"action": "run_now", "task_id": "t1"},
        )
        data_run_be = parse_mcp_result(res_run_be)
        assert data_run_be["success"] is False

        # Action: schedule
        res_sched = await mcp_server.call_tool(
            "sm_agent_maintenance_operations",
            arguments={
                "action": "schedule",
                "task_id": "t2",
                "name": "task2",
                "query": "query2",
                "frequency": "weekly",
                "priority": "HIGH",
            },
        )
        data_sched = parse_mcp_result(res_sched)
        assert data_sched["success"] is True

        # Action: schedule missing parameters
        res_sched_missing = await mcp_server.call_tool(
            "sm_agent_maintenance_operations",
            arguments={"action": "schedule"},
        )
        data_sched_missing = parse_mcp_result(res_sched_missing)
        assert data_sched_missing["success"] is False

        # Action: get_log
        cron.summary.return_value = {"log_entry": 1}
        res_log = await mcp_server.call_tool(
            "sm_agent_maintenance_operations",
            arguments={"action": "get_log"},
        )
        data_log = parse_mcp_result(res_log)
        assert data_log["log_entry"] == 1

        # Action: unsupported (Direct Python call to hit the else branch)
        res_unsupported = await sm_agent_maintenance_operations(action="invalid_action")  # type: ignore
        assert res_unsupported["success"] is False


def test_guard_no_agent_utilities():
    with patch("systems_manager.agent_os_tools._HAS_AGENT_UTILITIES", False):
        mcp_mock = MagicMock()
        # Should not raise and return None
        res = agent_os_tools.register_identity_tools(mcp_mock)
        assert res is None
        assert not mcp_mock.tool.called


def test_singleton_getters():
    with (
        patch("systems_manager.agent_os_tools.CognitiveScheduler") as mock_sched,
        patch("systems_manager.agent_os_tools.PermissionsKernel") as mock_perms,
        patch("systems_manager.agent_os_tools.AgentRegistry") as mock_reg,
        patch("systems_manager.agent_os_tools.FileWatcher") as mock_watch,
        patch("systems_manager.agent_os_tools.MaintenanceCron") as mock_maint,
    ):
        # Reset the globals to None to trigger lazy loading
        agent_os_tools._scheduler = None
        agent_os_tools._permissions = None
        agent_os_tools._registry = None
        agent_os_tools._watcher = None
        agent_os_tools._maintenance = None

        s = agent_os_tools._get_scheduler()
        assert s is mock_sched.return_value

        p = agent_os_tools._get_permissions()
        assert p is mock_perms.return_value

        r = agent_os_tools._get_registry()
        assert r is mock_reg.return_value

        w = agent_os_tools._get_watcher()
        assert w is mock_watch.return_value

        m = agent_os_tools._get_maintenance()
        assert m is mock_maint.return_value
