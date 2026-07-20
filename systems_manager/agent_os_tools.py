#!/usr/bin/python
"""Agent OS MCP Tool Groups for systems-manager.

Exposes kernel-level Agent OS operations (AU-030, AU-031, AU-032, and
AU-036) as privileged MCP tools. All tools are thin wrappers
around ``agent-utilities`` classes, following the existing
``register_*_tools(mcp: FastMCP)`` pattern.

All routing flows through the Knowledge Graph by default —
these tools are registered into the KG at startup and discoverable
via ``sync_mcp_agents()``.

Requires the declared ``agent-utilities`` runtime dependency.
"""

from __future__ import annotations

import logging
from typing import Any

from agent_utilities.core.config import setting
from agent_utilities.mcp.action_dispatch import resolve_action
from agent_utilities.mcp.context_helpers import ctx_confirm_destructive
from pydantic import Field

logger = logging.getLogger(__name__)

# Canonical action sets per action-routed tool, reused by ``resolve_action`` for
# discovery and exact action dispatch.
IDENTITY_ACTIONS = ("issue", "verify")
SPECIALIST_ACTIONS = ("install", "uninstall", "list", "search")
SCHEDULER_ACTIONS = ("get_stats", "list_processes", "preempt")
WATCHDOG_ACTIONS = ("check_change", "list_watchers", "drain_triggers")

from agent_utilities.automation.file_watcher import FileWatcher
from agent_utilities.core.cognitive_scheduler import CognitiveScheduler
from agent_utilities.core.registry.package_adapter import AgentRegistry
from agent_utilities.security.permissions_kernel import AgentRole, PermissionsKernel

# ── Shared singletons (lazily initialized) ────────────────────────────

_scheduler: CognitiveScheduler | None = None
_permissions: PermissionsKernel | None = None
_registry: AgentRegistry | None = None
_watcher: FileWatcher | None = None


def _resolve_current_action(
    action: str, allowed: tuple[str, ...]
) -> str | dict[str, Any]:
    """Resolve discovery while rejecting historical action aliases."""

    if action != "list_actions" and action not in allowed:
        raise ValueError(
            f"Unsupported systems-manager action {action!r}; "
            "call with action='list_actions' for the current contract"
        )
    return resolve_action(action, allowed, service="systems-manager")


def _get_scheduler() -> CognitiveScheduler:
    global _scheduler
    if _scheduler is None:
        max_concurrent = int(setting("MAX_CONCURRENT_AGENTS", 5))
        if not 1 <= max_concurrent <= 64:
            raise ValueError("MAX_CONCURRENT_AGENTS is outside the supported range")
        _scheduler = CognitiveScheduler(max_concurrent=max_concurrent)
    return _scheduler


def _get_permissions() -> PermissionsKernel:
    global _permissions
    if _permissions is None:
        signing_key = setting("PERMISSIONS_SIGNING_KEY")
        policies_path = setting("AGENT_POLICIES_PATH")
        _permissions = PermissionsKernel(
            signing_key=signing_key,
            policies_path=policies_path,
        )
    return _permissions


def _get_registry() -> AgentRegistry:
    global _registry
    if _registry is None:
        registry_path = setting("SPECIALIST_REGISTRY_PATH")
        mcp_config_path = setting("MCP_CONFIG_PATH")
        if not isinstance(registry_path, str) or not registry_path.strip():
            raise ValueError("SPECIALIST_REGISTRY_PATH must be configured explicitly")
        if not isinstance(mcp_config_path, str) or not mcp_config_path.strip():
            raise ValueError("MCP_CONFIG_PATH must be configured explicitly")
        _registry = AgentRegistry(
            registry_path=registry_path.strip(),
            mcp_config_path=mcp_config_path.strip(),
        )
    return _registry


def _get_watcher() -> FileWatcher:
    global _watcher
    if _watcher is None:
        project_root = setting("PROJECT_ROOT")
        if not isinstance(project_root, str) or not project_root:
            raise ValueError("PROJECT_ROOT must be configured explicitly")
        _watcher = FileWatcher(project_root=project_root)
    return _watcher


# ══════════════════════════════════════════════════════════════════════
# Tool Group 1: Identity Management (AU-031)
# ══════════════════════════════════════════════════════════════════════


async def sm_agent_identity_operations(
    action: str = Field(
        description="Action to perform. Must be one of: "
        + ", ".join(f"'{a}'" for a in IDENTITY_ACTIONS),
    ),
    agent_subject: str | None = Field(
        description="Runtime identity subject to pseudonymize before issuance",
        default=None,
    ),
    role: str = Field(
        description="Agent role (for 'issue'): admin, operator, specialist, sandbox, guest",
        default="specialist",
    ),
    agent_id: str | None = Field(
        description="Agent ID to verify or revoke", default=None
    ),
    ctx: Any | None = Field(description="MCP context", default=None),
) -> dict:
    """Issues or verifies privacy-preserving agent identities."""
    resolved = _resolve_current_action(action, IDENTITY_ACTIONS)
    if isinstance(resolved, dict):
        return resolved
    action = resolved
    if action == "issue" and not await ctx_confirm_destructive(
        ctx, f"Approve agent identity operation: {action}"
    ):
        return {"success": False, "error": "Operation approval is required"}
    kernel = _get_permissions()
    if action == "issue":
        if not agent_subject:
            return {
                "success": False,
                "error": "agent_subject is required for 'issue' action",
            }
        try:
            agent_role = AgentRole(role.lower())
        except ValueError:
            return {"success": False, "error": f"Invalid role: {role}"}
        opaque_agent_id = kernel.derive_agent_id(agent_subject)
        identity = kernel.issue_identity(opaque_agent_id, agent_role)
        return {
            "success": True,
            "agent_id": identity.agent_id,
            "role": identity.role.value,
            "issued_at": identity.issued_at,
            "expires_at": identity.expires_at,
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
    else:
        return {"success": False, "error": f"Unsupported action: {action}"}


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
    ctx: Any | None = Field(description="MCP context", default=None),
) -> dict:
    """Manages specialist packages: install, uninstall, list, or search."""
    resolved = _resolve_current_action(action, SPECIALIST_ACTIONS)
    if isinstance(resolved, dict):
        return resolved
    action = resolved
    if action in {"install", "uninstall"} and not await ctx_confirm_destructive(
        ctx, f"Approve specialist registry operation: {action}"
    ):
        return {"success": False, "error": "Operation approval is required"}
    registry = _get_registry()
    if action == "install":
        if not package_name:
            return {
                "success": False,
                "error": "package_name is required for 'install' action",
            }
        result = await registry.install(package_name)
        return {"success": result.startswith("✓"), "package": package_name}
    elif action == "uninstall":
        if not package_name:
            return {
                "success": False,
                "error": "package_name is required for 'uninstall' action",
            }
        result = await registry.uninstall(package_name)
        return {"success": result.startswith("✓"), "package": package_name}
    elif action == "list":
        if status == "installed":
            packages = registry.list_installed()
        elif status == "available":
            packages = registry.list_available()
        else:
            packages = registry.list_installed() + registry.list_available()
        return {
            "packages": [
                {"name": p.name, "version": p.version, "tags": list(p.tags)}
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
    ctx: Any | None = Field(description="MCP context", default=None),
) -> dict:
    """Manages the cognitive scheduler: get stats, list processes, preempt, or reset quota."""
    resolved = _resolve_current_action(action, SCHEDULER_ACTIONS)
    if isinstance(resolved, dict):
        return resolved
    action = resolved
    if action == "preempt" and not await ctx_confirm_destructive(
        ctx, f"Approve scheduler operation: {action}"
    ):
        return {"success": False, "error": "Operation approval is required"}
    scheduler = _get_scheduler()
    if action == "get_stats":
        return scheduler.get_stats()
    elif action == "list_processes":
        table = scheduler.get_process_table()
        return {
            "processes": [
                {
                    "id": process.id,
                    "priority": process.priority,
                    "state": process.state,
                    "token_quota": process.token_quota,
                    "tokens_used": process.tokens_used,
                }
                for process in table
            ],
            "count": len(table),
        }
    elif action == "preempt":
        if not process_id:
            return {
                "success": False,
                "error": "process_id is required for 'preempt' action",
            }
        checkpoint = await scheduler.preempt(process_id, reason=reason)
        if checkpoint:
            return {"success": True, "checkpoint_created": True}
        return {
            "success": False,
            "error": "Process not found or not running",
        }
    else:
        return {"success": False, "error": f"Unsupported action: {action}"}


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
    ctx: Any | None = Field(description="MCP context", default=None),
) -> dict:
    """Manages file watchdog triggers: check file change, list active watchers, or drain triggers."""
    resolved = _resolve_current_action(action, WATCHDOG_ACTIONS)
    if isinstance(resolved, dict):
        return resolved
    action = resolved
    if action == "drain_triggers" and not await ctx_confirm_destructive(
        ctx, "Approve watchdog trigger drain"
    ):
        return {"success": False, "error": "Operation approval is required"}
    watcher = _get_watcher()
    if action == "check_change":
        if not filepath:
            return {
                "success": False,
                "error": "filepath is required for 'check_change' action",
            }
        trigger = watcher.check_file_change(filepath)
        if trigger:
            return {
                "triggered": True,
                "pattern": trigger.get("pattern"),
                "priority": trigger.get("priority"),
            }
        return {"triggered": False}
    elif action == "list_watchers":
        rules = []
        for rule in watcher.triggers:
            rules.append(
                {
                    "pattern": rule.pattern,
                    "priority": rule.priority,
                    "cooldown": rule.cooldown,
                }
            )
        return {
            "rules": rules,
            "count": len(rules),
        }
    elif action == "drain_triggers":
        pending = watcher.drain_pending()
        return {"drained": True, "count": len(pending)}
    else:
        return {"success": False, "error": f"Unsupported action: {action}"}


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
