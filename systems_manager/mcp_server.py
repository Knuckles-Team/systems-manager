#!/usr/bin/env python
import argparse
import asyncio
import ipaddress
import logging
import re
import sys
import warnings
import weakref
from collections.abc import Callable
from typing import Any, Literal, TypeVar, cast

from agent_utilities.base_utilities import to_boolean
from fastmcp import Context, FastMCP
from fastmcp.server.middleware import Middleware, MiddlewareContext
from fastmcp.utilities.logging import get_logger
from pydantic import Field

# Filter RequestsDependencyWarning early to prevent log spam
with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    try:
        from requests.exceptions import RequestsDependencyWarning

        warnings.filterwarnings("ignore", category=RequestsDependencyWarning)
    except ImportError:
        pass

# General urllib3/chardet mismatch warnings
warnings.filterwarnings("ignore", message=".*urllib3.*or chardet.*")
warnings.filterwarnings("ignore", message=".*urllib3.*or charset_normalizer.*")

# Filter AuthlibDeprecationWarning
warnings.filterwarnings("ignore", category=DeprecationWarning, module="authlib.*")

from agent_utilities.core.config import load_config, setting
from agent_utilities.mcp.action_dispatch import resolve_action
from agent_utilities.mcp.concurrency import run_blocking as _agent_run_blocking
from agent_utilities.mcp.context_helpers import ctx_log
from agent_utilities.mcp.server_factory import (
    create_mcp_server,
    mcp_network_run_kwargs,
    protect_stdio_jsonrpc,
)
from agent_utilities.mcp.verbose_tools import register_tool_surface
from agent_utilities.security.request_identity import apply_served_security_profile

from systems_manager.os_provider_tools import register_os_provider_tools
from systems_manager.storage_tools import register_storage_health_tools
from systems_manager.systems_manager import (
    FirewallRuleSpec,
    SystemsManagerBase,
    WindowsManager,
    detect_and_create_manager,
    resolve_managed_path,
)

__version__ = "1.36.0"

logging.basicConfig(
    level=logging.WARNING,
    format="%(levelname)s %(message)s",
)
logger = get_logger("SystemsManagerServer")

_ResultT = TypeVar("_ResultT")


def _bounded_worker_count() -> int:
    """Return a conservative host-operation limit for invalid configuration."""
    try:
        configured = int(setting("SYSTEMS_MANAGER_MAX_BLOCKING_OPERATIONS", 2))
    except (TypeError, ValueError):
        configured = 2
    return max(1, min(8, configured))


_MAX_BLOCKING_OPERATIONS = _bounded_worker_count()
_BLOCKING_OPERATIONS: weakref.WeakKeyDictionary[
    asyncio.AbstractEventLoop, asyncio.Semaphore
] = weakref.WeakKeyDictionary()
_HOST_MUTATION_LOCKS: weakref.WeakKeyDictionary[
    asyncio.AbstractEventLoop, asyncio.Lock
] = weakref.WeakKeyDictionary()
_SERVER_BOUNDARY_STATUS: dict[str, Any] = {
    "transport": "not-started",
    "network_transport": False,
    "authentication_configured": False,
    "tls_boundary_configured": False,
    "ready": False,
}


def _is_loopback_bind(host: object) -> bool:
    """Classify an explicit listener address without DNS resolution."""

    value = str(host or "").strip().casefold()
    if value in {"localhost", "localhost."}:
        return True
    value = value.strip("[]").split("%", 1)[0]
    try:
        return ipaddress.ip_address(value).is_loopback
    except ValueError:
        return False


async def run_blocking(
    function: Callable[..., _ResultT], /, *args: Any, **kwargs: Any
) -> _ResultT:
    """Run synchronous host work off-loop with a bounded server-loop budget."""
    loop = asyncio.get_running_loop()
    limiter = _BLOCKING_OPERATIONS.get(loop)
    if limiter is None:
        limiter = asyncio.Semaphore(_MAX_BLOCKING_OPERATIONS)
        _BLOCKING_OPERATIONS[loop] = limiter
    async with limiter:
        return await _agent_run_blocking(function, *args, **kwargs)


def _host_mutation_lock() -> asyncio.Lock:
    """Return the serialization lock owned by the active server event loop."""
    loop = asyncio.get_running_loop()
    lock = _HOST_MUTATION_LOCKS.get(loop)
    if lock is None:
        lock = asyncio.Lock()
        _HOST_MUTATION_LOCKS[loop] = lock
    return lock


def _approval_text(action: str, detail: str | None = None) -> str:
    safe_action = " ".join(str(action).split())[:128]
    safe_detail = " ".join(str(detail or "").split())[:512]
    if not safe_action:
        raise ValueError("Mutation approval action is required")
    lines = ["SYSTEMS MANAGER MUTATION APPROVAL", f"Action: {safe_action}"]
    if safe_detail:
        lines.append(f"Target: {safe_detail}")
    lines.append("Approve this one operation?")
    return "\n".join(lines)


async def _mutation_approved(
    ctx: Context | None, action: str, detail: str | None = None
) -> bool:
    """Require an explicit per-operation approval in addition to admin policy."""
    if not ctx:
        return False
    try:
        decision = await ctx.elicit(_approval_text(action, detail), response_type=bool)
    except Exception:
        return False
    return decision.action == "accept" and bool(decision.data)


_SYSTEM_MUTATIONS = frozenset(
    {
        "install_applications",
        "update",
        "reboot",
        "clean",
        "optimize",
        "install_python_modules",
        "clean_temp_files",
        "clean_package_cache",
        "enable_windows_features",
        "disable_windows_features",
        "add_repository",
        "install_local_package",
    }
)
_SERVICE_MUTATIONS = frozenset(
    {
        "start_service",
        "stop_service",
        "restart_service",
        "enable_service",
        "disable_service",
    }
)


def _tool_name_and_arguments(context: MiddlewareContext) -> tuple[str, dict[str, Any]]:
    message = getattr(context, "message", None)
    if message is None:
        raise PermissionError("Malformed tool invocation")
    raw_name = getattr(message, "name", None)
    if not isinstance(raw_name, str) or not re.fullmatch(
        r"[A-Za-z][A-Za-z0-9_.-]{0,127}", raw_name
    ):
        raise PermissionError("Malformed tool invocation")
    arguments = getattr(message, "arguments", None)
    if arguments is None:
        params = getattr(message, "params", None)
        arguments = getattr(params, "arguments", None)
    if arguments is None:
        return raw_name, {}
    if (
        not isinstance(arguments, dict)
        or len(arguments) > 128
        or not all(isinstance(key, str) for key in arguments)
    ):
        raise PermissionError("Malformed tool invocation")
    return raw_name, arguments


def _aggregate_policy(
    action: Any,
    *,
    mutations: frozenset[str] = frozenset(),
    reads: frozenset[str] = frozenset(),
    probes: frozenset[str] = frozenset(),
) -> str:
    if action == "list_actions":
        return "public"
    if action in mutations:
        return "host-mutation"
    if action in reads:
        return "sensitive-read"
    if action in probes:
        return "network-probe"
    raise PermissionError(
        "Unsupported or unclassified tool action; use action='list_actions'"
    )


def _classify_tool(name: str, arguments: dict[str, Any]) -> str:
    """Classify every registered operation; unknown calls fail closed."""
    action = arguments.get("action")
    if name in {"health_check", "get_management_capabilities"}:
        return "public"
    if name == "sm_system_operations":
        return _aggregate_policy(
            action,
            mutations=_SYSTEM_MUTATIONS,
            reads=frozenset(SYSTEM_ACTIONS) - _SYSTEM_MUTATIONS,
        )
    if name == "sm_service_operations":
        return _aggregate_policy(
            action,
            mutations=_SERVICE_MUTATIONS,
            reads=frozenset(SERVICE_ACTIONS) - _SERVICE_MUTATIONS,
        )
    if name == "sm_process_operations":
        return _aggregate_policy(
            action,
            mutations=frozenset({"kill_process"}),
            reads=frozenset(PROCESS_ACTIONS) - {"kill_process"},
        )
    if name == "sm_network_operations":
        return _aggregate_policy(
            action,
            reads=frozenset({"list_network_interfaces", "list_open_ports"}),
            probes=frozenset({"ping_host", "dns_lookup"}),
        )
    if name in {"sm_disk_operations", "sm_user_operations"}:
        return _aggregate_policy(
            action,
            reads=frozenset(
                DISK_ACTIONS if name == "sm_disk_operations" else USER_ACTIONS
            ),
        )
    if name == "sm_file_operations":
        if action in {
            "get_system_logs",
            "tail_log_file",
            "list_files",
            "search_files",
            "grep_files",
        }:
            return "sensitive-read"
        if action == "manage_file":
            file_action = arguments.get("file_action", "read")
            if file_action == "read":
                return "sensitive-read"
            if file_action in {"write", "append", "delete", "create"}:
                return "filesystem-mutation"
        if action == "list_actions":
            return "public"
        raise PermissionError("Unsupported or unclassified file operation")
    if name == "sm_cron_operations":
        return _aggregate_policy(
            action,
            mutations=frozenset({"remove_cron_job"}),
            reads=frozenset({"list_cron_jobs"}),
        )
    if name == "sm_firewall_operations":
        return _aggregate_policy(
            action,
            mutations=frozenset({"add_firewall_rule", "remove_firewall_rule"}),
            reads=frozenset({"get_firewall_status"}),
        )
    if name == "sm_advanced_operations":
        return _aggregate_policy(action, mutations=frozenset(ADVANCED_ACTIONS))
    if name in {
        "systems_ingest_host",
        "sm_storage_health",
        "get_process_details",
        "get_network_connections",
        "capture_system_snapshot",
        "list_services",
        "list_kernel_modules",
        "query_system_logs",
    }:
        return "sensitive-read"
    if name in {"manage_service", "start_system_trace", "stop_system_trace"}:
        return "host-mutation"
    agent_policies: dict[str, tuple[frozenset[str], frozenset[str]]] = {
        "sm_agent_identity_operations": (
            frozenset({"issue"}),
            frozenset({"verify"}),
        ),
        "sm_agent_specialist_operations": (
            frozenset({"install", "uninstall"}),
            frozenset({"list", "search"}),
        ),
        "sm_agent_scheduler_operations": (
            frozenset({"preempt"}),
            frozenset({"get_stats", "list_processes"}),
        ),
        "sm_agent_watchdog_operations": (
            frozenset({"drain_triggers"}),
            frozenset({"check_change", "list_watchers"}),
        ),
    }
    if name in agent_policies:
        mutations, reads = agent_policies[name]
        return _aggregate_policy(action, mutations=mutations, reads=reads)
    raise PermissionError("Unclassified tool invocation")


class SystemsSecurityMiddleware(Middleware):
    """Default-deny mutations, sensitive reads, and active network probes."""

    async def on_call_tool(self, context: MiddlewareContext, call_next):
        name, arguments = _tool_name_and_arguments(context)
        policy = _classify_tool(name, arguments)
        mutating = policy in {"host-mutation", "filesystem-mutation"}
        if mutating and not to_boolean(
            setting("SYSTEMS_MANAGER_ALLOW_HOST_MUTATIONS", False)
        ):
            raise PermissionError("Host mutation is disabled by administrator policy")
        if policy == "filesystem-mutation" and not to_boolean(
            setting("SYSTEMS_MANAGER_ALLOW_FILESYSTEM_MUTATIONS", False)
        ):
            raise PermissionError(
                "Generic filesystem mutation is disabled by administrator policy"
            )
        if policy == "sensitive-read" and not to_boolean(
            setting("SYSTEMS_MANAGER_ALLOW_SENSITIVE_READS", False)
        ):
            raise PermissionError(
                "Sensitive host reads are disabled by administrator policy"
            )
        if policy == "network-probe" and not to_boolean(
            setting("SYSTEMS_MANAGER_ALLOW_NETWORK_PROBES", False)
        ):
            raise PermissionError(
                "Active network probes are disabled by administrator policy"
            )
        if not mutating:
            return await call_next(context)
        async with _host_mutation_lock():
            return await call_next(context)


# Canonical action sets per action-routed tool. The provider accepts only these current
# names plus the explicit ``list_actions`` discovery operation.
SYSTEM_ACTIONS = (
    "install_applications",
    "update",
    "reboot",
    "clean",
    "optimize",
    "install_python_modules",
    "get_os_statistics",
    "get_hardware_statistics",
    "search_package",
    "get_package_info",
    "list_installed_packages",
    "list_upgradable_packages",
    "system_health_check",
    "get_uptime",
    "list_env_vars",
    "get_env_var",
    "clean_temp_files",
    "clean_package_cache",
    "list_windows_features",
    "enable_windows_features",
    "disable_windows_features",
    "add_repository",
    "install_local_package",
)
SERVICE_ACTIONS = (
    "list_services",
    "get_service_status",
    "start_service",
    "stop_service",
    "restart_service",
    "enable_service",
    "disable_service",
)
PROCESS_ACTIONS = ("list_processes", "get_process_info", "kill_process")
NETWORK_ACTIONS = (
    "list_network_interfaces",
    "list_open_ports",
    "ping_host",
    "dns_lookup",
)
DISK_ACTIONS = ("list_disks", "get_disk_usage", "get_disk_space_report")
USER_ACTIONS = ("list_users", "list_groups")
FILE_ACTIONS = (
    "get_system_logs",
    "tail_log_file",
    "list_files",
    "search_files",
    "grep_files",
    "manage_file",
)
CRON_ACTIONS = ("list_cron_jobs", "remove_cron_job")
FIREWALL_ACTIONS = (
    "get_firewall_status",
    "add_firewall_rule",
    "remove_firewall_rule",
)
ADVANCED_ACTIONS = (
    "add_authorized_key",
    "install_uv",
    "create_venv",
    "install_package",
    "install_nvm",
    "install_node",
    "use_node",
)


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


_ALL_CLASSIFIED_TOOLS = frozenset(
    {
        "health_check",
        "get_management_capabilities",
        "get_process_details",
        "get_network_connections",
        "capture_system_snapshot",
        "list_services",
        "manage_service",
        "list_kernel_modules",
        "query_system_logs",
        "start_system_trace",
        "stop_system_trace",
        "sm_storage_health",
        "sm_agent_identity_operations",
        "sm_agent_specialist_operations",
        "sm_agent_scheduler_operations",
        "sm_agent_watchdog_operations",
        "sm_system_operations",
        "sm_service_operations",
        "sm_process_operations",
        "sm_network_operations",
        "sm_disk_operations",
        "sm_user_operations",
        "sm_file_operations",
        "sm_cron_operations",
        "sm_firewall_operations",
        "sm_advanced_operations",
        "systems_ingest_host",
    }
)


def _assert_registered_tools_are_classified(mcp: FastMCP) -> None:
    """Refuse startup when a registered tool has no explicit policy class."""
    provider = getattr(mcp, "_local_provider", None)
    components = getattr(provider, "_components", None)
    if not isinstance(components, dict):
        return
    registered = {
        str(getattr(component, "name", "") or "")
        for component in components.values()
        if getattr(component, "name", None)
    }
    unclassified = registered - _ALL_CLASSIFIED_TOOLS
    if unclassified:
        raise RuntimeError(
            "Unclassified MCP tools prevent startup: " + ", ".join(sorted(unclassified))
        )


def register_misc_tools(mcp: FastMCP) -> None:
    """Register non-destructive discovery and readiness tools."""

    @mcp.tool(annotations={"title": "Health Check"})
    async def health_check() -> str:
        return "OK"

    @mcp.tool(
        annotations={
            "title": "Get Management Capabilities",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        }
    )
    async def get_management_capabilities() -> dict[str, Any]:
        root_configured = bool(
            str(setting("SYSTEMS_MANAGER_FILESYSTEM_ROOT", "")).strip()
        )
        root_accessible = False
        if root_configured:
            try:
                await run_blocking(resolve_managed_path, ".", must_exist=True)
                root_accessible = True
            except (FileNotFoundError, PermissionError, ValueError) as exc:
                logger.debug(
                    "Managed root capability check failed: %s",
                    type(exc).__name__,
                )
        manager_name = "unavailable"
        try:
            manager = await run_blocking(detect_and_create_manager)
            manager_name = type(manager).__name__
        except Exception as exc:
            logger.debug(
                "System manager capability detection failed: %s",
                type(exc).__name__,
            )
        return {
            "success": True,
            "manager": manager_name,
            "managed_root": {
                "configured": root_configured,
                "accessible": root_accessible,
                "path_disclosed": False,
            },
            "policy": {
                "host_mutations": to_boolean(
                    setting("SYSTEMS_MANAGER_ALLOW_HOST_MUTATIONS", False)
                ),
                "filesystem_mutations": to_boolean(
                    setting("SYSTEMS_MANAGER_ALLOW_FILESYSTEM_MUTATIONS", False)
                ),
                "sensitive_reads": to_boolean(
                    setting("SYSTEMS_MANAGER_ALLOW_SENSITIVE_READS", False)
                ),
                "network_probes": to_boolean(
                    setting("SYSTEMS_MANAGER_ALLOW_NETWORK_PROBES", False)
                ),
                "per_operation_approval_required": True,
                "mutations_serialized": True,
                "blocking_operation_limit": _MAX_BLOCKING_OPERATIONS,
            },
            "transport_boundary": dict(_SERVER_BOUNDARY_STATUS),
        }


def get_mcp_instance() -> tuple[argparse.Namespace, FastMCP, list[Any]]:
    """Initialize the MCP server."""
    load_config()
    args, mcp, middlewares = create_mcp_server(
        name="systems-manager",
        version=__version__,
        instructions="Systems Manager MCP Server",
    )
    transport = str(getattr(args, "transport", "stdio") or "stdio").casefold()
    auth_type = str(getattr(args, "auth_type", "none") or "none").casefold()
    network_transport = transport in {"streamable-http", "sse"}
    authentication_configured = (
        auth_type
        not in {
            "",
            "none",
            "no-auth",
            "disabled",
        }
        and getattr(mcp, "auth", None) is not None
    )
    direct_tls = bool(
        getattr(args, "tls_certfile", None) and getattr(args, "tls_keyfile", None)
    )
    proxied_tls = bool(
        getattr(args, "tls_terminated", False)
        and getattr(args, "trusted_proxy_cidrs", None)
    )
    loopback = _is_loopback_bind(getattr(args, "host", ""))
    _SERVER_BOUNDARY_STATUS.update(
        {
            "transport": transport,
            "network_transport": network_transport,
            "authentication_configured": authentication_configured,
            "tls_boundary_configured": direct_tls or proxied_tls,
            "ready": not network_transport
            or (authentication_configured and (loopback or direct_tls or proxied_tls)),
        }
    )

    if bool(setting("MISCTOOL", True)):
        register_misc_tools(mcp)

    from systems_manager.agent_os_tools import (
        register_agent_health_tools,
        register_identity_tools,
        register_specialist_registry_tools,
        register_watchdog_tools,
    )

    register_tool_surface(
        mcp,
        client_cls=SystemsManagerBase,
        get_client=detect_and_create_manager,
        service="systems-manager",
        registrars=[
            register_os_provider_tools,
            register_storage_health_tools,
            register_agent_health_tools,
            register_identity_tools,
            register_specialist_registry_tools,
            register_watchdog_tools,
        ],
    )

    @mcp.tool(
        description="System operations for managing packages, system health, and updates"
    )
    async def sm_system_operations(
        action: str = Field(
            ...,
            description="Action to perform. Must be one of: "
            + ", ".join(f"'{a}'" for a in SYSTEM_ACTIONS),
        ),
        packages: list[str] | None = Field(
            None, description="List of applications/packages"
        ),
        package: str | None = Field(None, description="Single package name"),
        repository: str | None = Field(None, description="Repository URL or name"),
        file_path: str | None = Field(None, description="Path to local package file"),
        feature_name: str | None = Field(None, description="Windows feature name"),
        env_var: str | None = Field(None, description="Environment variable name"),
        allow_on_k8s: bool = Field(
            False,
            description=(
                "Override: allow 'update' or 'reboot' to proceed even if this "
                "host is detected as a live Kubernetes (RKE2) node. Prefer the "
                "universal-skills `k8s-node-rolling-update` workflow instead."
            ),
        ),
        ctx: Context | None = None,
    ) -> Any:
        resolved = _resolve_current_action(action, SYSTEM_ACTIONS)
        if isinstance(resolved, dict):
            return resolved
        action = resolved
        manager = detect_and_create_manager()
        ctx_log(
            ctx,
            logger,
            "info",
            f"sm_system_operations: {action}",
        )
        if action in _SYSTEM_MUTATIONS and not await _mutation_approved(
            ctx, action, "configured host"
        ):
            return {"success": False, "error": "Operation approval is required"}
        try:
            if action == "install_applications":
                return await run_blocking(manager.install_applications, packages or [])
            elif action == "update":
                return await run_blocking(
                    manager.update,
                    allow_on_k8s=allow_on_k8s,
                )
            elif action == "reboot":
                return await run_blocking(
                    manager.reboot,
                    allow_on_k8s=allow_on_k8s,
                )
            elif action == "clean":
                return await run_blocking(
                    manager.clean,
                )
            elif action == "optimize":
                return await run_blocking(
                    manager.optimize,
                )
            elif action == "install_python_modules":
                return await run_blocking(
                    manager.install_python_modules, packages or []
                )
            elif action == "get_os_statistics":
                return await run_blocking(
                    manager.get_os_statistics,
                )
            elif action == "get_hardware_statistics":
                return await run_blocking(
                    manager.get_hardware_statistics,
                )
            elif action == "search_package":
                return await run_blocking(manager.search_package, package or "")
            elif action == "get_package_info":
                return await run_blocking(manager.get_package_info, package or "")
            elif action == "list_installed_packages":
                return await run_blocking(
                    manager.list_installed_packages,
                )
            elif action == "list_upgradable_packages":
                return await run_blocking(
                    manager.list_upgradable_packages,
                )
            elif action == "system_health_check":
                return await run_blocking(
                    manager.system_health_check,
                )
            elif action == "get_uptime":
                return await run_blocking(
                    manager.get_uptime,
                )
            elif action == "list_env_vars":
                return await run_blocking(
                    manager.list_env_vars,
                )
            elif action == "get_env_var":
                return await run_blocking(manager.get_env_var, env_var or "")
            elif action == "clean_temp_files":
                return await run_blocking(
                    manager.clean_temp_files,
                )
            elif action == "clean_package_cache":
                return await run_blocking(
                    manager.clean_package_cache,
                )
            elif action == "list_windows_features":
                return (
                    await run_blocking(
                        manager.list_windows_features,
                    )
                    if isinstance(manager, WindowsManager)
                    else "Not supported"
                )
            elif action == "enable_windows_features":
                return (
                    await run_blocking(
                        manager.enable_windows_features,
                        [feature_name] if feature_name else [],
                    )
                    if isinstance(manager, WindowsManager)
                    else "Not supported"
                )
            elif action == "disable_windows_features":
                return (
                    await run_blocking(
                        manager.disable_windows_features,
                        [feature_name] if feature_name else [],
                    )
                    if isinstance(manager, WindowsManager)
                    else "Not supported"
                )
            elif action == "add_repository":
                return await run_blocking(manager.add_repository, repository or "")
            elif action == "install_local_package":
                return await run_blocking(
                    manager.install_local_package, file_path or ""
                )
        except Exception:
            return {"success": False, "error": "Operation failed"}

    @mcp.tool(description="Operations for managing system services")
    async def sm_service_operations(
        action: str = Field(
            ...,
            description="Action to perform. Must be one of: "
            + ", ".join(f"'{a}'" for a in SERVICE_ACTIONS),
        ),
        service_name: str | None = Field(None, description="Name of the service"),
        ctx: Context | None = None,
    ) -> Any:
        resolved = _resolve_current_action(action, SERVICE_ACTIONS)
        if isinstance(resolved, dict):
            return resolved
        action = resolved
        manager = detect_and_create_manager()
        ctx_log(
            ctx,
            logger,
            "info",
            f"sm_service_operations: {action}",
        )
        if action in _SERVICE_MUTATIONS and not await _mutation_approved(
            ctx, action, service_name
        ):
            return {"success": False, "error": "Operation approval is required"}
        try:
            if action == "list_services":
                return await run_blocking(
                    manager.list_services,
                )
            elif action == "get_service_status":
                return await run_blocking(
                    manager.get_service_status, service_name or ""
                )
            elif action == "start_service":
                return await run_blocking(manager.start_service, service_name or "")
            elif action == "stop_service":
                return await run_blocking(manager.stop_service, service_name or "")
            elif action == "restart_service":
                return await run_blocking(manager.restart_service, service_name or "")
            elif action == "enable_service":
                return await run_blocking(manager.enable_service, service_name or "")
            elif action == "disable_service":
                return await run_blocking(manager.disable_service, service_name or "")
        except Exception:
            return {"success": False, "error": "Operation failed"}

    @mcp.tool(description="Operations for managing system processes")
    async def sm_process_operations(
        action: str = Field(
            ...,
            description="Action to perform. Must be one of: "
            + ", ".join(f"'{a}'" for a in PROCESS_ACTIONS),
        ),
        pid: int | None = Field(None, description="Process ID"),
        ctx: Context | None = None,
    ) -> Any:
        resolved = _resolve_current_action(action, PROCESS_ACTIONS)
        if isinstance(resolved, dict):
            return resolved
        action = resolved
        manager = detect_and_create_manager()
        ctx_log(
            ctx,
            logger,
            "info",
            f"sm_process_operations: {action}",
        )
        if action == "kill_process" and not await _mutation_approved(
            ctx, action, f"process {pid}" if pid is not None else None
        ):
            return {"success": False, "error": "Operation approval is required"}
        try:
            if action == "list_processes":
                return await run_blocking(
                    manager.list_processes,
                )
            elif action == "get_process_info":
                if pid is not None:
                    return await run_blocking(manager.get_process_info, pid)
                return "pid is required"
            elif action == "kill_process":
                if pid is not None:
                    return await run_blocking(manager.kill_process, pid)
                return "pid is required"
        except Exception:
            return {"success": False, "error": "Operation failed"}

    @mcp.tool(description="Operations for network analysis")
    async def sm_network_operations(
        action: str = Field(
            ...,
            description="Action to perform. Must be one of: "
            + ", ".join(f"'{a}'" for a in NETWORK_ACTIONS),
        ),
        host: str | None = Field(None, description="Host to ping or lookup"),
        count: int = Field(4, description="Ping count"),
        ctx: Context | None = None,
    ) -> Any:
        resolved = _resolve_current_action(action, NETWORK_ACTIONS)
        if isinstance(resolved, dict):
            return resolved
        action = resolved
        manager = detect_and_create_manager()
        ctx_log(
            ctx,
            logger,
            "info",
            f"sm_network_operations: {action}",
        )
        try:
            if action == "list_network_interfaces":
                return await run_blocking(
                    manager.list_network_interfaces,
                )
            elif action == "list_open_ports":
                return await run_blocking(
                    manager.list_open_ports,
                )
            elif action == "ping_host":
                return await run_blocking(manager.ping_host, host or "", count)
            elif action == "dns_lookup":
                return await run_blocking(manager.dns_lookup, host or "")
        except Exception:
            return {"success": False, "error": "Operation failed"}

    @mcp.tool(description="Operations for managing system disks")
    async def sm_disk_operations(
        action: str = Field(
            ...,
            description="Action to perform. Must be one of: "
            + ", ".join(f"'{a}'" for a in DISK_ACTIONS),
        ),
        path: str | None = Field(None, description="Path for disk usage"),
        ctx: Context | None = None,
    ) -> Any:
        resolved = _resolve_current_action(action, DISK_ACTIONS)
        if isinstance(resolved, dict):
            return resolved
        action = resolved
        manager = detect_and_create_manager()
        ctx_log(
            ctx,
            logger,
            "info",
            f"sm_disk_operations: {action}",
        )
        try:
            if action == "list_disks":
                return await run_blocking(
                    manager.list_disks,
                )
            elif action == "get_disk_usage":
                return await run_blocking(manager.get_disk_usage, path or "/")
            elif action == "get_disk_space_report":
                return await run_blocking(
                    manager.get_disk_space_report,
                )
        except Exception:
            return {"success": False, "error": "Operation failed"}

    @mcp.tool(description="Operations for user and group management")
    async def sm_user_operations(
        action: str = Field(
            ...,
            description="Action to perform. Must be one of: "
            + ", ".join(f"'{a}'" for a in USER_ACTIONS),
        ),
        ctx: Context | None = None,
    ) -> Any:
        resolved = _resolve_current_action(action, USER_ACTIONS)
        if isinstance(resolved, dict):
            return resolved
        action = resolved
        manager = detect_and_create_manager()
        ctx_log(
            ctx,
            logger,
            "info",
            f"sm_user_operations: {action}",
        )
        try:
            if action == "list_users":
                return await run_blocking(
                    manager.list_users,
                )
            elif action == "list_groups":
                return await run_blocking(
                    manager.list_groups,
                )
        except Exception:
            return {"success": False, "error": "Operation failed"}

    @mcp.tool(description="Operations for file and log management")
    async def sm_file_operations(
        action: str = Field(
            ...,
            description="Action to perform. Must be one of: "
            + ", ".join(f"'{a}'" for a in FILE_ACTIONS),
        ),
        filepath: str | None = Field(None, description="Path to file"),
        content: str | None = Field(None, description="Content to write/append"),
        file_action: (
            Literal["read", "write", "append", "delete", "create"] | None
        ) = Field(cast(Any, "read"), description="Action for text editor/manage file"),
        lines: int = Field(100, description="Number of lines to tail"),
        pattern: str | None = Field(None, description="Search pattern"),
        recursive: bool = Field(False, description="Recursive search"),
        depth: int = Field(1, description="Depth for list_files"),
        ctx: Context | None = None,
    ) -> Any:
        resolved = _resolve_current_action(action, FILE_ACTIONS)
        if isinstance(resolved, dict):
            return resolved
        action = resolved
        manager = detect_and_create_manager()
        ctx_log(
            ctx,
            logger,
            "info",
            f"sm_file_operations: {action}",
        )
        if (
            action == "manage_file"
            and file_action
            in {
                "write",
                "append",
                "delete",
                "create",
            }
            and not await _mutation_approved(ctx, file_action, filepath)
        ):
            return {"success": False, "error": "Operation approval is required"}
        try:
            if action == "get_system_logs":
                return await run_blocking(manager.get_system_logs, lines=lines)
            elif action == "tail_log_file":
                return await run_blocking(manager.tail_log_file, filepath or "", lines)
            elif action == "list_files":
                return await run_blocking(
                    manager.fs_manager.list_files, filepath or ".", recursive, depth
                )
            elif action == "search_files":
                return await run_blocking(
                    manager.fs_manager.search_files, filepath or ".", pattern or ""
                )
            elif action == "grep_files":
                return await run_blocking(
                    manager.fs_manager.grep_files,
                    filepath or ".",
                    pattern or "",
                    recursive,
                )
            elif action == "manage_file":
                return await run_blocking(
                    manager.fs_manager.manage_file,
                    file_action or "read",
                    filepath or "",
                    content or "",
                )
        except Exception:
            return {"success": False, "error": "Operation failed"}

    @mcp.tool(description="Operations for cron jobs")
    async def sm_cron_operations(
        action: str = Field(
            ...,
            description="Action to perform. Must be one of: "
            + ", ".join(f"'{a}'" for a in CRON_ACTIONS),
        ),
        job_ref: str | None = Field(
            None, description="Opaque job reference returned by list_cron_jobs"
        ),
        user: str | None = Field(None, description="User for cron job"),
        ctx: Context | None = None,
    ) -> Any:
        resolved = _resolve_current_action(action, CRON_ACTIONS)
        if isinstance(resolved, dict):
            return resolved
        action = resolved
        manager = detect_and_create_manager()
        ctx_log(
            ctx,
            logger,
            "info",
            f"sm_cron_operations: {action}",
        )
        if action == "remove_cron_job" and not await _mutation_approved(
            ctx, action, "configured schedule"
        ):
            return {"success": False, "error": "Operation approval is required"}
        try:
            if action == "list_cron_jobs":
                return await run_blocking(manager.list_cron_jobs, user)
            elif action == "remove_cron_job":
                return await run_blocking(manager.remove_cron_job, job_ref or "", user)
        except Exception:
            return {"success": False, "error": "Operation failed"}

    @mcp.tool(description="Operations for firewall management")
    async def sm_firewall_operations(
        action: str = Field(
            ...,
            description="Action to perform. Must be one of: "
            + ", ".join(f"'{a}'" for a in FIREWALL_ACTIONS),
        ),
        rule: FirewallRuleSpec | None = Field(
            None, description="Structured firewall rule specification"
        ),
        ctx: Context | None = None,
    ) -> Any:
        resolved = _resolve_current_action(action, FIREWALL_ACTIONS)
        if isinstance(resolved, dict):
            return resolved
        action = resolved
        manager = detect_and_create_manager()
        ctx_log(
            ctx,
            logger,
            "info",
            f"sm_firewall_operations: {action}",
        )
        if action in {
            "add_firewall_rule",
            "remove_firewall_rule",
        } and not await _mutation_approved(
            ctx, action, rule.name if rule is not None else None
        ):
            return {"success": False, "error": "Operation approval is required"}
        try:
            if action == "get_firewall_status":
                return await run_blocking(
                    manager.get_firewall_status,
                )
            elif action == "add_firewall_rule":
                if rule is None:
                    return {"success": False, "error": "Structured rule is required"}
                return await run_blocking(manager.add_firewall_rule, rule)
            elif action == "remove_firewall_rule":
                if rule is None:
                    return {"success": False, "error": "Structured rule is required"}
                return await run_blocking(manager.remove_firewall_rule, rule)
        except Exception:
            return {"success": False, "error": "Operation failed"}

    @mcp.tool(description="Operations for SSH and specialized managers")
    async def sm_advanced_operations(
        action: str = Field(
            ...,
            description="Action to perform. Must be one of: "
            + ", ".join(f"'{a}'" for a in ADVANCED_ACTIONS),
        ),
        public_key: str | None = Field(None, description="Public key content"),
        path: str | None = Field(None, description="Path for venv"),
        version: str | None = Field(None, description="Version of python/node"),
        package: str | None = Field(None, description="Package name to install"),
        ctx: Context | None = None,
    ) -> Any:
        resolved = _resolve_current_action(action, ADVANCED_ACTIONS)
        if isinstance(resolved, dict):
            return resolved
        action = resolved
        manager = detect_and_create_manager()
        ctx_log(
            ctx,
            logger,
            "info",
            f"sm_advanced_operations: {action}",
        )
        if not await _mutation_approved(ctx, action, "configured host"):
            return {"success": False, "error": "Operation approval is required"}
        try:
            if action == "add_authorized_key":
                return await run_blocking(manager.add_authorized_key, public_key or "")
            elif action == "install_uv":
                return await run_blocking(manager.python_manager.install_uv)
            elif action == "create_venv":
                return await run_blocking(
                    manager.python_manager.create_venv, path or "", version
                )
            elif action == "install_package":
                return await run_blocking(
                    manager.python_manager.install_package, package or "", path
                )
            elif action == "install_nvm":
                return await run_blocking(manager.node_manager.install_nvm)
            elif action == "install_node":
                return await run_blocking(
                    manager.node_manager.install_node, version or "node"
                )
            elif action == "use_node":
                return await run_blocking(
                    manager.node_manager.use_node, version or "node"
                )
        except Exception:
            return {"success": False, "error": "Operation failed"}

    @mcp.tool(
        description=(
            "Ingest a keyed host telemetry projection through the governed "
            "ChangeEnvelope boundary as typed HardwareNode, NetworkInterface, "
            "and DiskVolume nodes."
        )
    )
    async def systems_ingest_host(
        ctx: Context | None = None,
    ) -> Any:
        """Gather OS/hardware/network/disk state over the manager seam and push it
        into the knowledge graph via the fast engine client.

        CONCEPT:AU-KG.ingest.enterprise-source-extractor.
        """
        from systems_manager.kg_ingest import ingest_host_inventory

        manager = detect_and_create_manager()
        ctx_log(
            ctx,
            logger,
            "info",
            "systems_ingest_host",
        )

        def _as_dict(value: Any) -> Any:
            if hasattr(value, "model_dump"):
                return value.model_dump()
            return value

        try:
            os_stats = _as_dict(await run_blocking(manager.get_os_statistics))
            hw_stats = _as_dict(await run_blocking(manager.get_hardware_statistics))
            net = _as_dict(await run_blocking(manager.list_network_interfaces))
            disks = _as_dict(await run_blocking(manager.list_disks))
        except Exception:  # noqa: BLE001 - return a stable content-free failure
            return {"error": "Telemetry collection failed", "ingested": None}

        report = {
            "host": None,
            "os": os_stats if isinstance(os_stats, dict) else {},
            "hardware": hw_stats if isinstance(hw_stats, dict) else {},
            "interfaces": (
                (net or {}).get("interfaces") if isinstance(net, dict) else None
            ),
            "disks": (disks or {}).get("disks") if isinstance(disks, dict) else None,
        }
        try:
            result = await run_blocking(ingest_host_inventory, report)
        except Exception:  # noqa: BLE001 - do not disclose engine/session details
            return {
                "target": "local",
                "success": False,
                "error": "Graph ingestion failed",
            }
        return {"target": "local", "success": True, "ingested": result}

    _assert_registered_tools_are_classified(mcp)
    mcp.add_middleware(SystemsSecurityMiddleware())
    return args, mcp, middlewares


def mcp_server() -> None:
    args, mcp, middlewares = get_mcp_instance()
    print(f"systems-manager MCP v{__version__}", file=sys.stderr)
    print("\nStarting MCP Server", file=sys.stderr)
    print(f"  Transport: {args.transport.upper()}", file=sys.stderr)
    print(f"  Auth: {args.auth_type}", file=sys.stderr)

    network_transport = args.transport in {"streamable-http", "sse"}
    auth_type = str(getattr(args, "auth_type", "") or "").strip().casefold()
    unauthenticated = auth_type in {"", "none", "no-auth", "disabled"}
    auth_provider = getattr(mcp, "auth", None)
    if network_transport and (unauthenticated or auth_provider is None):
        logger.error("Refusing MCP network transport without configured authentication")
        raise SystemExit(2)

    apply_served_security_profile(
        args.transport,
        transport_auth_configured=not unauthenticated and auth_provider is not None,
    )

    if args.transport == "stdio":
        protect_stdio_jsonrpc()
        mcp.run(transport="stdio")
    elif args.transport == "streamable-http":
        mcp.run(
            transport="streamable-http",
            host=args.host,
            port=args.port,
            **mcp_network_run_kwargs(args),
        )
    elif args.transport == "sse":
        mcp.run(
            transport="sse",
            host=args.host,
            port=args.port,
            **mcp_network_run_kwargs(args),
        )
    else:
        logger.error("Invalid transport", extra={"transport": args.transport})
        sys.exit(1)


def main():
    mcp_server()


if __name__ == "__main__":
    main()
