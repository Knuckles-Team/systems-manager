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

logger = logging.getLogger(__name__)

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


@_guard
def register_identity_tools(mcp: Any) -> None:
    """Register agent identity lifecycle tools (AU-031)."""
    from pydantic import Field

    @mcp.tool(
        annotations={
            "title": "Issue Agent Identity",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": False,
        },
        tags={"agent_os", "identity"},
    )
    async def issue_agent_identity(
        agent_name: str = Field(description="Name of the agent to issue identity for"),
        role: str = Field(
            description="Agent role: admin, operator, specialist, sandbox, guest",
            default="specialist",
        ),
    ) -> dict:
        """Issues a signed identity token for an agent with the specified role."""
        kernel = _get_permissions()
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

    @mcp.tool(
        annotations={
            "title": "Verify Agent Identity",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
        tags={"agent_os", "identity"},
    )
    async def verify_agent_identity(
        agent_id: str = Field(description="Agent ID to verify"),
    ) -> dict:
        """Verifies that an agent's identity token is valid and not expired."""
        kernel = _get_permissions()
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

    @mcp.tool(
        annotations={
            "title": "Revoke Agent Identity",
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": True,
            "openWorldHint": False,
        },
        tags={"agent_os", "identity"},
    )
    async def revoke_agent_identity(
        agent_id: str = Field(description="Agent ID to revoke"),
    ) -> dict:
        """Revokes an agent's identity, removing it from the active registry."""
        kernel = _get_permissions()
        if agent_id in kernel._identities:
            del kernel._identities[agent_id]
            return {"success": True, "revoked": agent_id}
        return {"success": False, "error": "Identity not found"}

    @mcp.tool(
        annotations={
            "title": "List Agent Identities",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
        tags={"agent_os", "identity"},
    )
    async def list_agent_identities() -> dict:
        """Lists all currently registered agent identities and their roles."""
        kernel = _get_permissions()
        identities = []
        for agent_id, identity in kernel._identities.items():
            identities.append(
                {
                    "agent_id": agent_id,
                    "role": identity.role.value,
                    "valid": kernel.verify_identity(identity),
                }
            )
        return {"identities": identities, "count": len(identities)}


# ══════════════════════════════════════════════════════════════════════
# Tool Group 2: Policy Management (AU-031)
# ══════════════════════════════════════════════════════════════════════


@_guard
def register_policy_tools(mcp: Any) -> None:
    """Register agent policy management tools (AU-031)."""
    from pydantic import Field

    @mcp.tool(
        annotations={
            "title": "List Agent Policies",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
        tags={"agent_os", "policy"},
    )
    async def list_agent_policies() -> dict:
        """Lists all configured agent role policies and their permissions."""
        kernel = _get_permissions()
        policies = []
        for role, policy in kernel._policies.items():
            policies.append(
                {
                    "role": role,
                    "allowed_tools": policy.allowed_tools,
                    "denied_tools": policy.denied_tools,
                    "require_approval": policy.require_approval,
                    "max_tokens_per_session": policy.max_tokens_per_session,
                }
            )
        return {"policies": policies, "count": len(policies)}

    @mcp.tool(
        annotations={
            "title": "Get Agent Policy",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
        tags={"agent_os", "policy"},
    )
    async def get_agent_policy(
        role: str = Field(description="Role name to get policy for"),
    ) -> dict:
        """Gets the detailed policy configuration for a specific agent role."""
        kernel = _get_permissions()
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

    @mcp.tool(
        annotations={
            "title": "Update Agent Policy",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
        tags={"agent_os", "policy"},
    )
    async def update_agent_policy(
        role: str = Field(description="Role to update"),
        allowed_tools: list[str] = Field(
            description="List of allowed tool patterns", default_factory=list
        ),
        denied_tools: list[str] = Field(
            description="List of denied tool patterns", default_factory=list
        ),
    ) -> dict:
        """Updates the allowed/denied tool patterns for an agent role policy."""
        kernel = _get_permissions()
        policy = kernel._policies.get(role)
        if not policy:
            return {"success": False, "error": f"No policy for role: {role}"}
        if allowed_tools:
            policy.allowed_tools = allowed_tools
        if denied_tools:
            policy.denied_tools = denied_tools
        return {"success": True, "role": role, "message": "Policy updated"}

    @mcp.tool(
        annotations={
            "title": "Reload Agent Policies",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
        tags={"agent_os", "policy"},
    )
    async def reload_policies() -> dict:
        """Reloads agent policies from the policies file on disk."""
        kernel = _get_permissions()
        if kernel._policies_path:
            kernel.load_policies(kernel._policies_path)
            return {"success": True, "message": "Policies reloaded from disk"}
        return {"success": False, "error": "No policies file configured"}


# ══════════════════════════════════════════════════════════════════════
# Tool Group 3: Specialist Registry (AU-032)
# ══════════════════════════════════════════════════════════════════════


@_guard
def register_specialist_registry_tools(mcp: Any) -> None:
    """Register specialist package registry tools (AU-032)."""
    from pydantic import Field

    @mcp.tool(
        annotations={
            "title": "Install Specialist",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": False,
        },
        tags={"agent_os", "registry"},
    )
    async def install_specialist(
        package_name: str = Field(
            description="Name of the specialist package to install"
        ),
    ) -> dict:
        """Installs a specialist package: merges MCP config, hydrates KG, deploys container if needed."""
        registry = _get_registry()
        result = await registry.install(package_name)
        return {"success": "✓" in result, "message": result}

    @mcp.tool(
        annotations={
            "title": "Uninstall Specialist",
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": True,
            "openWorldHint": False,
        },
        tags={"agent_os", "registry"},
    )
    async def uninstall_specialist(
        package_name: str = Field(
            description="Name of the specialist package to uninstall"
        ),
    ) -> dict:
        """Uninstalls a specialist package: removes MCP config, KG nodes, and container if running."""
        registry = _get_registry()
        result = await registry.uninstall(package_name)
        return {"success": "✓" in result, "message": result}

    @mcp.tool(
        annotations={
            "title": "List Specialists",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
        tags={"agent_os", "registry"},
    )
    async def list_specialists(
        status: str = Field(
            description="Filter: 'installed', 'available', or 'all'",
            default="all",
        ),
    ) -> dict:
        """Lists specialist packages filtered by installation status."""
        registry = _get_registry()
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

    @mcp.tool(
        annotations={
            "title": "Search Specialists",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
        tags={"agent_os", "registry"},
    )
    async def search_specialists(
        query: str = Field(description="Search term (matches name, description, tags)"),
    ) -> dict:
        """Searches the specialist registry by name, description, or tags."""
        registry = _get_registry()
        results = registry.search(query)
        return {
            "results": [
                {"name": p.name, "version": p.version, "tags": p.tags} for p in results
            ],
            "count": len(results),
        }


# ══════════════════════════════════════════════════════════════════════
# Tool Group 4: Agent Health (AU-030)
# ══════════════════════════════════════════════════════════════════════


@_guard
def register_agent_health_tools(mcp: Any) -> None:
    """Register cognitive scheduler health tools (AU-030)."""
    from pydantic import Field

    @mcp.tool(
        annotations={
            "title": "Get Scheduler Stats",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
        tags={"agent_os", "scheduler"},
    )
    async def get_scheduler_stats() -> dict:
        """Returns the current cognitive scheduler statistics including active processes and quotas."""
        scheduler = _get_scheduler()
        return scheduler.get_stats()

    @mcp.tool(
        annotations={
            "title": "List Agent Processes",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
        tags={"agent_os", "scheduler"},
    )
    async def list_agent_processes() -> dict:
        """Lists all agent processes in the scheduler (running, waiting, preempted, completed)."""
        scheduler = _get_scheduler()
        table = scheduler.get_process_table()
        return {"processes": table, "count": len(table)}

    @mcp.tool(
        annotations={
            "title": "Preempt Agent Process",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": False,
        },
        tags={"agent_os", "scheduler"},
    )
    async def preempt_process(
        process_id: str = Field(description="ID of the agent process to preempt"),
        reason: str = Field(description="Reason for preemption", default="manual"),
    ) -> dict:
        """Preempts a running agent process, checkpointing its context for later resumption."""
        scheduler = _get_scheduler()
        checkpoint = scheduler.preempt(process_id, reason=reason)
        if checkpoint:
            return {"success": True, "checkpoint": checkpoint}
        return {
            "success": False,
            "error": f"Process '{process_id}' not found or not running",
        }

    @mcp.tool(
        annotations={
            "title": "Reset Agent Quota",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
        tags={"agent_os", "scheduler"},
    )
    async def reset_agent_quota(
        process_id: str = Field(description="ID of the process to reset quota for"),
    ) -> dict:
        """Resets the token usage counter for an agent process."""
        scheduler = _get_scheduler()
        proc = scheduler._processes.get(process_id)
        if not proc:
            return {"success": False, "error": "Process not found"}
        proc.tokens_used = 0
        return {"success": True, "process_id": process_id, "tokens_used": 0}


# ══════════════════════════════════════════════════════════════════════
# Tool Group 5: File Watcher (AU-036)
# ══════════════════════════════════════════════════════════════════════


@_guard
def register_watchdog_tools(mcp: Any) -> None:
    """Register file watcher trigger tools (AU-036)."""
    from pydantic import Field

    @mcp.tool(
        annotations={
            "title": "Check File Change",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
        tags={"agent_os", "watchdog"},
    )
    async def check_file_change(
        filepath: str = Field(description="Path of the changed file to evaluate"),
    ) -> dict:
        """Evaluates a file change against trigger rules and returns any matching query."""
        watcher = _get_watcher()
        trigger = watcher.check_file_change(filepath)
        if trigger:
            return {"triggered": True, **trigger}
        return {"triggered": False, "filepath": filepath}

    @mcp.tool(
        annotations={
            "title": "List Active Watchers",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
        tags={"agent_os", "watchdog"},
    )
    async def list_active_watchers() -> dict:
        """Lists all configured file watcher trigger rules and their status."""
        watcher = _get_watcher()
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

    @mcp.tool(
        annotations={
            "title": "Drain Pending Triggers",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": False,
        },
        tags={"agent_os", "watchdog"},
    )
    async def drain_pending_triggers() -> dict:
        """Drains and returns all pending file watcher triggers for processing."""
        watcher = _get_watcher()
        pending = watcher.drain_pending()
        return {"triggers": pending, "count": len(pending)}


# ══════════════════════════════════════════════════════════════════════
# Tool Group 6: Maintenance (AU-038)
# ══════════════════════════════════════════════════════════════════════


@_guard
def register_maintenance_tools(mcp: Any) -> None:
    """Register autonomous maintenance tools (AU-038)."""
    from pydantic import Field

    @mcp.tool(
        annotations={
            "title": "Get Due Maintenance Tasks",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
        tags={"agent_os", "maintenance"},
    )
    async def list_maintenance_tasks() -> dict:
        """Lists all maintenance tasks and identifies which are currently due for execution."""
        cron = _get_maintenance()
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

    @mcp.tool(
        annotations={
            "title": "Run Maintenance Now",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": False,
        },
        tags={"agent_os", "maintenance"},
    )
    async def run_maintenance_now(
        task_id: str = Field(
            description="ID of the maintenance task to run immediately"
        ),
    ) -> dict:
        """Triggers immediate execution of a specific maintenance task."""
        cron = _get_maintenance()
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

    @mcp.tool(
        annotations={
            "title": "Schedule Maintenance Task",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
        tags={"agent_os", "maintenance"},
    )
    async def schedule_maintenance(
        task_id: str = Field(description="Unique task identifier"),
        name: str = Field(description="Human-readable task name"),
        query: str = Field(description="Graph query to execute"),
        frequency: str = Field(
            description="Frequency: hourly, daily, weekly, on_demand",
            default="daily",
        ),
        priority: str = Field(description="Priority: LOW, MEDIUM, HIGH", default="LOW"),
    ) -> dict:
        """Adds a new custom maintenance task to the autonomous scheduler."""
        cron = _get_maintenance()
        task = MaintenanceTask(
            id=task_id,
            name=name,
            query=query,
            frequency=frequency,
            priority=priority,
        )
        cron.add_task(task)
        return {"success": True, "task_id": task_id, "message": f"Scheduled '{name}'"}

    @mcp.tool(
        annotations={
            "title": "Get Maintenance Log",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
        tags={"agent_os", "maintenance"},
    )
    async def get_maintenance_log() -> dict:
        """Returns the maintenance execution log with token usage statistics."""
        cron = _get_maintenance()
        return cron.summary()
