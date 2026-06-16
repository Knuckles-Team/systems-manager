#!/usr/bin/python
"""Agent OS MCP Tool Groups for systems-manager.

Exposes kernel-level Agent OS operations (AU-030, AU-031, AU-032,
AU-036, AU-038) as privileged MCP tools.  All tools are thin wrappers
around ``agent-utilities`` classes, following the existing
``register_*_tools(mcp: FastMCP)`` pattern.

All routing flows through the Knowledge Graph by default —
these tools are registered into the KG at startup and discoverable
via ``sync_mcp_agents()``.

Requires ``agent-utilities >= 0.3.0``.  If not installed, all
registration functions log a warning and become no-ops.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from agent_utilities.mcp_utilities import resolve_action
from pydantic import Field

logger = logging.getLogger(__name__)

# Canonical action sets per action-routed tool, reused by ``resolve_action``
# to provide list_actions discovery, plural->singular aliases, and
# did-you-mean errors on unknown actions.
IDENTITY_ACTIONS = ("issue", "verify", "revoke", "list")
POLICY_ACTIONS = ("list", "get", "update", "reload")
SPECIALIST_ACTIONS = ("install", "uninstall", "list", "search")
SCHEDULER_ACTIONS = ("get_stats", "list_processes", "preempt", "reset_quota")
WATCHDOG_ACTIONS = ("check_change", "list_watchers", "drain_triggers")
MAINTENANCE_ACTIONS = ("list_tasks", "run_now", "schedule", "get_log")

# Graceful import — all registration functions become no-ops if
# agent-utilities is not installed (backward compatible).
try:
    from agent_utilities.automation.file_watcher import FileWatcher
    from agent_utilities.automation.maintenance_cron import (
        MaintenanceCron,
        MaintenanceTask,
    )
    from agent_utilities.core.cognitive_scheduler import (
        CognitiveScheduler,
    )
    from agent_utilities.core.registry_cli import AgentRegistry
    from agent_utilities.security.permissions_kernel import (
        AgentRole,
        PermissionsKernel,
    )

    _HAS_AGENT_UTILITIES = True
except ImportError:
    _HAS_AGENT_UTILITIES = False
    logger.warning(
        "[Agent OS] agent-utilities >= 0.3.0 not found. "
        "Agent OS tools will not be registered."
    )


def _guard(func):  # type: ignore[no-untyped-def]
    """Decorator that makes registration a no-op without agent-utilities."""

    def wrapper(mcp):  # type: ignore[no-untyped-def]
        if not _HAS_AGENT_UTILITIES:
            logger.debug(
                "[Agent OS] Skipping %s — agent-utilities missing", func.__name__
            )
            return
        return func(mcp)

    return wrapper


# ── Shared singletons (lazily initialized) ────────────────────────────

_scheduler: CognitiveScheduler | None = None
_permissions: PermissionsKernel | None = None
_registry: AgentRegistry | None = None
_watcher: FileWatcher | None = None
_maintenance: MaintenanceCron | None = None


def _get_scheduler() -> CognitiveScheduler:
    global _scheduler
    if _scheduler is None:
        max_concurrent = int(os.getenv("MAX_CONCURRENT_AGENTS", "5"))
        _scheduler = CognitiveScheduler(max_concurrent=max_concurrent)
    return _scheduler


def _get_permissions() -> PermissionsKernel:
    global _permissions
    if _permissions is None:
        signing_key = os.getenv("PERMISSIONS_SIGNING_KEY")
        policies_path = os.getenv("AGENT_POLICIES_PATH")
        _permissions = PermissionsKernel(
            signing_key=signing_key,
            policies_path=policies_path,
        )
    return _permissions


def _get_registry() -> AgentRegistry:
    global _registry
    if _registry is None:
        registry_path = os.getenv("SPECIALIST_REGISTRY_PATH")
        mcp_config_path = os.getenv("MCP_CONFIG_PATH")
        _registry = AgentRegistry(
            registry_path=registry_path,
            mcp_config_path=mcp_config_path,
        )
    return _registry


def _get_watcher() -> FileWatcher:
    global _watcher
    if _watcher is None:
        project_root = os.getenv("PROJECT_ROOT", os.getcwd())
        _watcher = FileWatcher(project_root=project_root)
    return _watcher


def _get_maintenance() -> MaintenanceCron:
    global _maintenance
    if _maintenance is None:
        token_budget = int(os.getenv("MAINTENANCE_TOKEN_BUDGET", "0"))
        priority = os.getenv("MAINTENANCE_PRIORITY", "LOW")
        _maintenance = MaintenanceCron(
            token_budget=token_budget,
            priority=priority,
        )
    return _maintenance


# ══════════════════════════════════════════════════════════════════════
# Tool Group 1: Identity Management (AU-031)
# ══════════════════════════════════════════════════════════════════════


async def sm_agent_identity_operations(
    action: str = Field(
        description="Action to perform. Must be one of: "
        + ", ".join(f"'{a}'" for a in IDENTITY_ACTIONS),
    ),
    agent_name: str | None = Field(
        description="Name of the agent to issue identity for", default=None
    ),
    role: str = Field(
        description="Agent role (for 'issue'): admin, operator, specialist, sandbox, guest",
        default="specialist",
    ),
    agent_id: str | None = Field(
        description="Agent ID to verify or revoke", default=None
    ),
) -> dict:
    """Manages agent identity lifecycle: issue, verify, revoke, or list identities."""
    resolved = resolve_action(action, IDENTITY_ACTIONS, service="systems-manager")
    if isinstance(resolved, dict):
        return resolved
    action = resolved
    kernel = _get_permissions()
    if action == "issue":
        if not agent_name:
            return {
                "success": False,
                "error": "agent_name is required for 'issue' action",
            }
        try:
            agent_role = AgentRole(role.lower())
        except ValueError:
            return {"success": False, "error": f"Invalid role: {role}"}
        identity = kernel.issue_identity(agent_name, agent_role)
        return {
            "success": True,
            "agent_id": identity.agent_id,
            "role": identity.role.value,
            "issued_at": identity.issued_at,
            "expires_at": identity.expires_at,
            "signature": identity.signature[:16] + "...",
        }
    elif action == "verify":
        if not agent_id:
            return {
                "success": False,
                "error": "agent_id is required for 'verify' action",
            }
        identity = kernel.get_identity(agent_id)
        if not identity:
            return {"valid": False, "error": "Identity not found"}
        is_valid = kernel.verify_identity(identity)
        return {
            "valid": is_valid,
            "agent_id": identity.agent_id,
            "role": identity.role.value,
            "expires_at": identity.expires_at,
        }
    elif action == "revoke":
        if not agent_id:
            return {
                "success": False,
                "error": "agent_id is required for 'revoke' action",
            }
        if agent_id in kernel._identities:
            del kernel._identities[agent_id]
            return {"success": True, "revoked": agent_id}
        return {"success": False, "error": "Identity not found"}
    elif action == "list":
        identities = []
        for a_id, identity in kernel._identities.items():
            identities.append(
                {
                    "agent_id": a_id,
                    "role": identity.role.value,
                    "valid": kernel.verify_identity(identity),
                }
            )
        return {"identities": identities, "count": len(identities)}
    else:
        return {"success": False, "error": f"Unsupported action: {action}"}


@_guard
def register_identity_tools(mcp: Any) -> None:
    """Register agent identity lifecycle tools (AU-031)."""
    mcp.tool(
        annotations={
            "title": "Agent Identity Operations",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": False,
        },
        tags={"agent_os", "identity"},
    )(sm_agent_identity_operations)


# ══════════════════════════════════════════════════════════════════════
# Tool Group 2: Policy Management (AU-031)
# ══════════════════════════════════════════════════════════════════════


async def sm_agent_policy_operations(
    action: str = Field(
        description="Action to perform. Must be one of: "
        + ", ".join(f"'{a}'" for a in POLICY_ACTIONS),
    ),
    role: str | None = Field(
        description="Role name for 'get' or 'update' action", default=None
    ),
    allowed_tools: list[str] | None = Field(
        description="List of allowed tool patterns for 'update'", default=None
    ),
    denied_tools: list[str] | None = Field(
        description="List of denied tool patterns for 'update'", default=None
    ),
) -> dict:
    """Manages agent policies: list role policies, get, update or reload policies."""
    resolved = resolve_action(action, POLICY_ACTIONS, service="systems-manager")
    if isinstance(resolved, dict):
        return resolved
    action = resolved
    kernel = _get_permissions()
    if action == "list":
        policies = []
        for r, policy in kernel._policies.items():
            policies.append(
                {
                    "role": r,
                    "allowed_tools": policy.allowed_tools,
                    "denied_tools": policy.denied_tools,
                    "require_approval": policy.require_approval,
                    "max_tokens_per_session": policy.max_tokens_per_session,
                }
            )
        return {"policies": policies, "count": len(policies)}
    elif action == "get":
        if not role:
            return {"success": False, "error": "role is required for 'get' action"}
        policy = kernel._policies.get(role)
        if not policy:
            return {"success": False, "error": f"No policy for role: {role}"}
        return {
            "role": role,
            "allowed_tools": policy.allowed_tools,
            "denied_tools": policy.denied_tools,
            "require_approval": policy.require_approval,
            "max_tokens_per_session": policy.max_tokens_per_session,
        }
    elif action == "update":
        if not role:
            return {"success": False, "error": "role is required for 'update' action"}
        policy = kernel._policies.get(role)
        if not policy:
            return {"success": False, "error": f"No policy for role: {role}"}
        if allowed_tools is not None:
            policy.allowed_tools = allowed_tools
        if denied_tools is not None:
            policy.denied_tools = denied_tools
        return {"success": True, "role": role, "message": "Policy updated"}
    elif action == "reload":
        if kernel._policies_path:
            kernel.load_policies(kernel._policies_path)
            return {"success": True, "message": "Policies reloaded from disk"}
        return {"success": False, "error": "No policies file configured"}
    else:
        return {"success": False, "error": f"Unsupported action: {action}"}


@_guard
def register_policy_tools(mcp: Any) -> None:
    """Register agent policy management tools (AU-031)."""
    mcp.tool(
        annotations={
            "title": "Agent Policy Operations",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": False,
        },
        tags={"agent_os", "policy"},
    )(sm_agent_policy_operations)


# ══════════════════════════════════════════════════════════════════════
# Tool Group 3: Specialist Registry (AU-032)
# ══════════════════════════════════════════════════════════════════════


async def sm_agent_specialist_operations(
    action: str = Field(
        description="Action to perform. Must be one of: "
        + ", ".join(f"'{a}'" for a in SPECIALIST_ACTIONS),
    ),
    package_name: str | None = Field(
        description="Name of the specialist package to install or uninstall",
        default=None,
    ),
    status: str = Field(
        description="Filter (for 'list'): 'installed', 'available', or 'all'",
        default="all",
    ),
    query: str | None = Field(description="Search term (for 'search')", default=None),
) -> dict:
    """Manages specialist packages: install, uninstall, list, or search."""
    resolved = resolve_action(action, SPECIALIST_ACTIONS, service="systems-manager")
    if isinstance(resolved, dict):
        return resolved
    action = resolved
    registry = _get_registry()
    if action == "install":
        if not package_name:
            return {
                "success": False,
                "error": "package_name is required for 'install' action",
            }
        result = await registry.install(package_name)
        return {"success": "✓" in result, "message": result}
    elif action == "uninstall":
        if not package_name:
            return {
                "success": False,
                "error": "package_name is required for 'uninstall' action",
            }
        result = await registry.uninstall(package_name)
        return {"success": "✓" in result, "message": result}
    elif action == "list":
        if status == "installed":
            packages = registry.list_installed()
        elif status == "available":
            packages = registry.list_available()
        else:
            packages = registry.list_installed() + registry.list_available()
        return {
            "packages": [
                {"name": p.name, "version": p.version, "description": p.description}
                for p in packages
            ],
            "count": len(packages),
        }
    elif action == "search":
        if not query:
            return {"success": False, "error": "query is required for 'search' action"}
        results = registry.search(query)
        return {
            "results": [
                {"name": p.name, "version": p.version, "tags": p.tags} for p in results
            ],
            "count": len(results),
        }
    else:
        return {"success": False, "error": f"Unsupported action: {action}"}


@_guard
def register_specialist_registry_tools(mcp: Any) -> None:
    """Register specialist package registry tools (AU-032)."""
    mcp.tool(
        annotations={
            "title": "Agent Specialist Registry Operations",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": False,
        },
        tags={"agent_os", "registry"},
    )(sm_agent_specialist_operations)


# ══════════════════════════════════════════════════════════════════════
# Tool Group 4: Agent Health (AU-030)
# ══════════════════════════════════════════════════════════════════════


async def sm_agent_scheduler_operations(
    action: str = Field(
        description="Action to perform. Must be one of: "
        + ", ".join(f"'{a}'" for a in SCHEDULER_ACTIONS),
    ),
    process_id: str | None = Field(
        description="Process ID to preempt or reset quota", default=None
    ),
    reason: str = Field(description="Reason for preemption", default="manual"),
) -> dict:
    """Manages the cognitive scheduler: get stats, list processes, preempt, or reset quota."""
    resolved = resolve_action(action, SCHEDULER_ACTIONS, service="systems-manager")
    if isinstance(resolved, dict):
        return resolved
    action = resolved
    scheduler = _get_scheduler()
    if action == "get_stats":
        return scheduler.get_stats()
    elif action == "list_processes":
        table = scheduler.get_process_table()
        return {"processes": table, "count": len(table)}
    elif action == "preempt":
        if not process_id:
            return {
                "success": False,
                "error": "process_id is required for 'preempt' action",
            }
        checkpoint = scheduler.preempt(process_id, reason=reason)
        if checkpoint:
            return {"success": True, "checkpoint": checkpoint}
        return {
            "success": False,
            "error": f"Process '{process_id}' not found or not running",
        }
    elif action == "reset_quota":
        if not process_id:
            return {
                "success": False,
                "error": "process_id is required for 'reset_quota' action",
            }
        proc = scheduler._processes.get(process_id)
        if not proc:
            return {"success": False, "error": "Process not found"}
        proc.tokens_used = 0
        return {"success": True, "process_id": process_id, "tokens_used": 0}
    else:
        return {"success": False, "error": f"Unsupported action: {action}"}


@_guard
def register_agent_health_tools(mcp: Any) -> None:
    """Register cognitive scheduler health tools (AU-030)."""
    mcp.tool(
        annotations={
            "title": "Agent Scheduler Operations",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": False,
        },
        tags={"agent_os", "scheduler"},
    )(sm_agent_scheduler_operations)


# ══════════════════════════════════════════════════════════════════════
# Tool Group 5: File Watcher (AU-036)
# ══════════════════════════════════════════════════════════════════════


async def sm_agent_watchdog_operations(
    action: str = Field(
        description="Action to perform. Must be one of: "
        + ", ".join(f"'{a}'" for a in WATCHDOG_ACTIONS),
    ),
    filepath: str | None = Field(
        description="File path to check for 'check_change'", default=None
    ),
) -> dict:
    """Manages file watchdog triggers: check file change, list active watchers, or drain triggers."""
    resolved = resolve_action(action, WATCHDOG_ACTIONS, service="systems-manager")
    if isinstance(resolved, dict):
        return resolved
    action = resolved
    watcher = _get_watcher()
    if action == "check_change":
        if not filepath:
            return {
                "success": False,
                "error": "filepath is required for 'check_change' action",
            }
        trigger = watcher.check_file_change(filepath)
        if trigger:
            return {"triggered": True, **trigger}
        return {"triggered": False, "filepath": filepath}
    elif action == "list_watchers":
        rules = []
        for rule in watcher.triggers:
            rules.append(
                {
                    "pattern": rule.pattern,
                    "priority": rule.priority,
                    "cooldown": rule.cooldown,
                    "query_preview": (
                        rule.query[:80] + "..." if len(rule.query) > 80 else rule.query
                    ),
                }
            )
        return {
            "rules": rules,
            "count": len(rules),
            "project_root": watcher.project_root,
        }
    elif action == "drain_triggers":
        pending = watcher.drain_pending()
        return {"triggers": pending, "count": len(pending)}
    else:
        return {"success": False, "error": f"Unsupported action: {action}"}


@_guard
def register_watchdog_tools(mcp: Any) -> None:
    """Register file watcher trigger tools (AU-036)."""
    mcp.tool(
        annotations={
            "title": "Agent Watchdog Operations",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": False,
        },
        tags={"agent_os", "watchdog"},
    )(sm_agent_watchdog_operations)


# ══════════════════════════════════════════════════════════════════════
# Tool Group 6: Maintenance (AU-038)
# ══════════════════════════════════════════════════════════════════════


async def sm_agent_maintenance_operations(
    action: str = Field(
        description="Action to perform. Must be one of: "
        + ", ".join(f"'{a}'" for a in MAINTENANCE_ACTIONS),
    ),
    task_id: str | None = Field(
        description="Unique task identifier to run or schedule", default=None
    ),
    name: str | None = Field(
        description="Human-readable task name (for 'schedule')", default=None
    ),
    query: str | None = Field(
        description="Graph query to execute (for 'schedule')", default=None
    ),
    frequency: str = Field(
        description="Frequency (for 'schedule'): hourly, daily, weekly, on_demand",
        default="daily",
    ),
    priority: str = Field(
        description="Priority (for 'schedule'): LOW, MEDIUM, HIGH",
        default="LOW",
    ),
) -> dict:
    """Manages autonomous maintenance: list due tasks, run a task immediately, schedule a new task, or get logs."""
    resolved = resolve_action(action, MAINTENANCE_ACTIONS, service="systems-manager")
    if isinstance(resolved, dict):
        return resolved
    action = resolved
    cron = _get_maintenance()
    if action == "list_tasks":
        summary = cron.summary()
        tasks = []
        for task in cron.tasks:
            tasks.append(
                {
                    "id": task.id,
                    "name": task.name,
                    "frequency": task.frequency.value,
                    "priority": task.priority,
                    "enabled": task.enabled,
                    "last_status": task.last_status,
                }
            )
        return {**summary, "tasks": tasks}
    elif action == "run_now":
        if not task_id:
            return {
                "success": False,
                "error": "task_id is required for 'run_now' action",
            }
        task = next((t for t in cron.tasks if t.id == task_id), None)
        if not task:
            return {"success": False, "error": f"Task '{task_id}' not found"}
        if not cron.is_budget_available():
            return {"success": False, "error": "Maintenance token budget exhausted"}
        return {
            "success": True,
            "task_id": task.id,
            "query": task.query,
            "priority": task.priority,
            "message": f"Maintenance task '{task.name}' ready for graph execution",
        }
    elif action == "schedule":
        if not task_id or not name or not query:
            return {
                "success": False,
                "error": "task_id, name, and query are required for 'schedule' action",
            }
        task = MaintenanceTask(
            id=task_id,
            name=name,
            query=query,
            frequency=frequency,
            priority=priority,
        )
        cron.add_task(task)
        return {"success": True, "task_id": task_id, "message": f"Scheduled '{name}'"}
    elif action == "get_log":
        return cron.summary()
    else:
        return {"success": False, "error": f"Unsupported action: {action}"}


@_guard
def register_maintenance_tools(mcp: Any) -> None:
    """Register autonomous maintenance tools (AU-038)."""
    mcp.tool(
        annotations={
            "title": "Agent Maintenance Operations",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": False,
        },
        tags={"agent_os", "maintenance"},
    )(sm_agent_maintenance_operations)
