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
from importlib.metadata import version as package_version
from typing import Any, Literal, TypeVar, cast

from fastmcp import Context, FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.server.middleware import Middleware, MiddlewareContext
from fastmcp.utilities.logging import get_logger
from pydantic import Field
from scion_sdk.utilities import to_boolean

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

from scion_sdk.config import load_config, setting
from scion_sdk.connector import build_server
from scion_sdk.connector_hooks import RegistrationContext
from scion_sdk.mcp.action_dispatch import resolve_action
from scion_sdk.mcp.action_split import assert_tools_classified
from scion_sdk.mcp.concurrency import run_blocking as _agent_run_blocking
from scion_sdk.mcp.context import ctx_log
from scion_sdk.mcp.tool_surface import register_tool_surface

from systems_manager.confirmation import require_approval
from systems_manager.k8s_detect import is_k8s_node
from systems_manager.os_provider_tools import register_os_provider_tools
from systems_manager.routed import call_routed
from systems_manager.storage_tools import register_storage_health_tools
from systems_manager.systems_manager import (
    FirewallRuleSpec,
    SystemsManagerBase,
    WindowsManager,
    detect_and_create_manager,
    filesystem_anchor,
    resolve_managed_path,
)

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
    if name in _SPLIT_TOOLS:
        name, action = _SPLIT_TOOLS[name]
        arguments = {**arguments, "action": action}
    action = arguments.get("action")
    if name in _SERVICE_TOOLS:
        return "host-mutation"
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
            if file_action in {"create", "update", "delete"}:
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
        "sm_storage_health_faults",
        "sm_storage_health_raid",
        "sm_storage_health_report",
        "sm_storage_health_smart",
        "get_process_details",
        "get_network_connections",
        "capture_system_snapshot",
        "list_services",
        "list_kernel_modules",
        "query_system_logs",
    }:
        return "sensitive-read"
    if name in {"start_system_trace", "stop_system_trace"}:
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


class PolicyDeniedError(ToolError, PermissionError):
    """A deployment-policy denial whose reason reaches the caller.

    Plain ``PermissionError`` is masked as "Internal server error" by the server,
    which hides the administrator gate that refused the call.
    """


class SystemsSecurityMiddleware(Middleware):
    """Default-deny mutations, sensitive reads, and active network probes."""

    async def on_call_tool(self, context: MiddlewareContext, call_next):
        name, arguments = _tool_name_and_arguments(context)
        policy = _classify_tool(name, arguments)
        mutating = policy in {"host-mutation", "filesystem-mutation"}
        if mutating and not to_boolean(
            setting("SYSTEMS_MANAGER_ALLOW_HOST_MUTATIONS", False)
        ):
            raise PolicyDeniedError("Host mutation is disabled by administrator policy")
        if policy == "filesystem-mutation" and not to_boolean(
            setting("SYSTEMS_MANAGER_ALLOW_FILESYSTEM_MUTATIONS", False)
        ):
            raise PolicyDeniedError(
                "Generic filesystem mutation is disabled by administrator policy"
            )
        if policy == "sensitive-read" and not to_boolean(
            setting("SYSTEMS_MANAGER_ALLOW_SENSITIVE_READS", False)
        ):
            raise PolicyDeniedError(
                "Sensitive host reads are disabled by administrator policy"
            )
        if policy == "network-probe" and not to_boolean(
            setting("SYSTEMS_MANAGER_ALLOW_NETWORK_PROBES", False)
        ):
            raise PolicyDeniedError(
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
    "get_host_record",
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


# Each operation is its own tool named ``<prefix>_<action>``. The security middleware
# classifies a call by the routed tool and action the tool stands for.
_ROUTED_TOOLS: dict[str, tuple[str, tuple[str, ...]]] = {
    "sm_system": ("sm_system_operations", SYSTEM_ACTIONS),
    "sm_service": ("sm_service_operations", SERVICE_ACTIONS),
    "sm_process": ("sm_process_operations", PROCESS_ACTIONS),
    "sm_network": ("sm_network_operations", NETWORK_ACTIONS),
    "sm_disk": ("sm_disk_operations", DISK_ACTIONS),
    "sm_user": ("sm_user_operations", USER_ACTIONS),
    "sm_file": ("sm_file_operations", FILE_ACTIONS),
    "sm_cron": ("sm_cron_operations", CRON_ACTIONS),
    "sm_firewall": ("sm_firewall_operations", FIREWALL_ACTIONS),
    "sm_advanced": ("sm_advanced_operations", ADVANCED_ACTIONS),
}
_SPLIT_TOOLS: dict[str, tuple[str, str]] = {
    f"{prefix}_{action}": (routed, action)
    for prefix, (routed, actions) in _ROUTED_TOOLS.items()
    for action in actions
}
_SERVICE_TOOLS = frozenset(
    f"manage_service_{a}" for a in ("start", "stop", "restart", "enable", "disable")
)


_ALL_CLASSIFIED_TOOLS = frozenset(
    {
        "health_check",
        "get_management_capabilities",
        "get_process_details",
        "get_network_connections",
        "capture_system_snapshot",
        "list_services",
        "list_kernel_modules",
        "query_system_logs",
        "start_system_trace",
        "stop_system_trace",
        "sm_storage_health_faults",
        "sm_storage_health_raid",
        "sm_storage_health_report",
        "sm_storage_health_smart",
        "sm_agent_identity_operations",
        "sm_agent_specialist_operations",
        "sm_agent_scheduler_operations",
        "sm_agent_watchdog_operations",
        "systems_ingest_host",
        *_SPLIT_TOOLS,
        *_SERVICE_TOOLS,
        # Meristem intent verbs: find/ask read; act routes governed writes.
        "find",
        "ask",
        "act",
    }
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
    """Build the declared connector's server (args, server, middlewares)."""
    load_config()
    args, mcp = build_server("systems_manager")
    return args, mcp, []


def register_connector_tools(context: RegistrationContext) -> None:
    """Register every systems-manager tool on the SDK-built server."""
    args = context.settings
    mcp = context.server
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

    register_tool_surface(
        mcp,
        client_cls=SystemsManagerBase,
        get_client=detect_and_create_manager,
        service="systems-manager",
        registrars=[
            register_os_provider_tools,
            register_storage_health_tools,
        ],
    )

    async def _sm_system_operations_routed(
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
        confirm: bool = Field(
            False,
            description=(
                "Explicit confirmation for a mutating action. Pass true when the "
                "client cannot answer an approval prompt."
            ),
        ),
        ctx: Context | None = None,
    ) -> Any:
        resolved = _resolve_current_action(action, SYSTEM_ACTIONS)
        if isinstance(resolved, dict):
            return resolved
        action = resolved
        manager = detect_and_create_manager()
        await ctx_log(
            ctx,
            f"sm_system_operations: {action}",
            logger=logger,
        )
        if action in _SYSTEM_MUTATIONS and (
            (
                refused := await require_approval(
                    ctx,
                    action,
                    (
                        "configured host (a live Kubernetes node)"
                        if action in {"update", "reboot"} and is_k8s_node()[0]
                        else "configured host"
                    ),
                    arguments={"action": action},
                    confirm=confirm,
                )
            )
            is not None
        ):
            return refused
        try:
            if action == "install_applications":
                return await run_blocking(manager.install_applications, packages or [])
            elif action == "update":
                return await run_blocking(manager.update)
            elif action == "reboot":
                return await run_blocking(manager.reboot)
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
            elif action == "get_host_record":
                return await run_blocking(
                    manager.get_host_record,
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

    @mcp.tool(
        name="sm_system_install_applications",
        description="Install applications (sm_system_operations). System operations for managing packages, system health, and updates",
        tags={"split-action"},
        annotations={
            "title": "Install Applications",
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": False,
            "openWorldHint": True,
        },
    )
    async def sm_system_install_applications(
        packages: list[str] | None = Field(
            None, description="List of applications/packages"
        ),
        confirm: bool = Field(
            False,
            description=(
                "Explicit confirmation for a mutating action. Pass true when the "
                "client cannot answer an approval prompt."
            ),
        ),
        ctx: Context | None = None,
    ) -> Any:
        """Install applications (one operation of sm_system_operations)."""
        return await call_routed(
            _sm_system_operations_routed,
            "install_applications",
            {"packages": packages, "confirm": confirm, "ctx": ctx},
        )

    @mcp.tool(
        name="sm_system_update",
        description="Update (sm_system_operations). System operations for managing packages, system health, and updates",
        tags={"split-action"},
        annotations={
            "title": "Update",
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": False,
            "openWorldHint": True,
        },
    )
    async def sm_system_update(
        confirm: bool = Field(
            False,
            description=(
                "Explicit confirmation for a mutating action. Pass true when the "
                "client cannot answer an approval prompt."
            ),
        ),
        ctx: Context | None = None,
    ) -> Any:
        """Update (one operation of sm_system_operations)."""
        return await call_routed(
            _sm_system_operations_routed,
            "update",
            {"confirm": confirm, "ctx": ctx},
        )

    @mcp.tool(
        name="sm_system_reboot",
        description="Reboot (sm_system_operations). System operations for managing packages, system health, and updates",
        tags={"split-action"},
        annotations={
            "title": "Reboot",
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": False,
            "openWorldHint": True,
        },
    )
    async def sm_system_reboot(
        confirm: bool = Field(
            False,
            description=(
                "Explicit confirmation for a mutating action. Pass true when the "
                "client cannot answer an approval prompt."
            ),
        ),
        ctx: Context | None = None,
    ) -> Any:
        """Reboot (one operation of sm_system_operations)."""
        return await call_routed(
            _sm_system_operations_routed,
            "reboot",
            {"confirm": confirm, "ctx": ctx},
        )

    @mcp.tool(
        name="sm_system_clean",
        description="Clean (sm_system_operations). System operations for managing packages, system health, and updates",
        tags={"split-action"},
        annotations={
            "title": "Clean",
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": False,
            "openWorldHint": True,
        },
    )
    async def sm_system_clean(
        confirm: bool = Field(
            False,
            description=(
                "Explicit confirmation for a mutating action. Pass true when the "
                "client cannot answer an approval prompt."
            ),
        ),
        ctx: Context | None = None,
    ) -> Any:
        """Clean (one operation of sm_system_operations)."""
        return await call_routed(
            _sm_system_operations_routed, "clean", {"confirm": confirm, "ctx": ctx}
        )

    @mcp.tool(
        name="sm_system_optimize",
        description="Optimize (sm_system_operations). System operations for managing packages, system health, and updates",
        tags={"split-action"},
        annotations={
            "title": "Optimize",
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": False,
            "openWorldHint": True,
        },
    )
    async def sm_system_optimize(
        confirm: bool = Field(
            False,
            description=(
                "Explicit confirmation for a mutating action. Pass true when the "
                "client cannot answer an approval prompt."
            ),
        ),
        ctx: Context | None = None,
    ) -> Any:
        """Optimize (one operation of sm_system_operations)."""
        return await call_routed(
            _sm_system_operations_routed, "optimize", {"confirm": confirm, "ctx": ctx}
        )

    @mcp.tool(
        name="sm_system_install_python_modules",
        description="Install python modules (sm_system_operations). System operations for managing packages, system health, and updates",
        tags={"split-action"},
        annotations={
            "title": "Install Python Modules",
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": False,
            "openWorldHint": True,
        },
    )
    async def sm_system_install_python_modules(
        packages: list[str] | None = Field(
            None, description="List of applications/packages"
        ),
        confirm: bool = Field(
            False,
            description=(
                "Explicit confirmation for a mutating action. Pass true when the "
                "client cannot answer an approval prompt."
            ),
        ),
        ctx: Context | None = None,
    ) -> Any:
        """Install python modules (one operation of sm_system_operations)."""
        return await call_routed(
            _sm_system_operations_routed,
            "install_python_modules",
            {"packages": packages, "confirm": confirm, "ctx": ctx},
        )

    @mcp.tool(
        name="sm_system_get_os_statistics",
        description="Get os statistics (sm_system_operations). System operations for managing packages, system health, and updates",
        tags={"split-action"},
        annotations={
            "title": "Get Os Statistics",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def sm_system_get_os_statistics(
        ctx: Context | None = None,
    ) -> Any:
        """Get os statistics (one operation of sm_system_operations)."""
        return await call_routed(
            _sm_system_operations_routed, "get_os_statistics", {"ctx": ctx}
        )

    @mcp.tool(
        name="sm_system_get_hardware_statistics",
        description="Get hardware statistics (sm_system_operations). System operations for managing packages, system health, and updates",
        tags={"split-action"},
        annotations={
            "title": "Get Hardware Statistics",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def sm_system_get_hardware_statistics(
        ctx: Context | None = None,
    ) -> Any:
        """Get hardware statistics (one operation of sm_system_operations)."""
        return await call_routed(
            _sm_system_operations_routed, "get_hardware_statistics", {"ctx": ctx}
        )

    @mcp.tool(
        name="sm_system_search_package",
        description="Search package (sm_system_operations). System operations for managing packages, system health, and updates",
        tags={"split-action"},
        annotations={
            "title": "Search Package",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def sm_system_search_package(
        package: str | None = Field(None, description="Single package name"),
        ctx: Context | None = None,
    ) -> Any:
        """Search package (one operation of sm_system_operations)."""
        return await call_routed(
            _sm_system_operations_routed,
            "search_package",
            {"package": package, "ctx": ctx},
        )

    @mcp.tool(
        name="sm_system_get_package_info",
        description="Get package info (sm_system_operations). System operations for managing packages, system health, and updates",
        tags={"split-action"},
        annotations={
            "title": "Get Package Info",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def sm_system_get_package_info(
        package: str | None = Field(None, description="Single package name"),
        ctx: Context | None = None,
    ) -> Any:
        """Get package info (one operation of sm_system_operations)."""
        return await call_routed(
            _sm_system_operations_routed,
            "get_package_info",
            {"package": package, "ctx": ctx},
        )

    @mcp.tool(
        name="sm_system_list_installed_packages",
        description="List installed packages (sm_system_operations). System operations for managing packages, system health, and updates",
        tags={"split-action"},
        annotations={
            "title": "List Installed Packages",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def sm_system_list_installed_packages(
        ctx: Context | None = None,
    ) -> Any:
        """List installed packages (one operation of sm_system_operations)."""
        return await call_routed(
            _sm_system_operations_routed, "list_installed_packages", {"ctx": ctx}
        )

    @mcp.tool(
        name="sm_system_list_upgradable_packages",
        description="List upgradable packages (sm_system_operations). System operations for managing packages, system health, and updates",
        tags={"split-action"},
        annotations={
            "title": "List Upgradable Packages",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def sm_system_list_upgradable_packages(
        ctx: Context | None = None,
    ) -> Any:
        """List upgradable packages (one operation of sm_system_operations)."""
        return await call_routed(
            _sm_system_operations_routed, "list_upgradable_packages", {"ctx": ctx}
        )

    @mcp.tool(
        name="sm_system_system_health_check",
        description="System health check (sm_system_operations). System operations for managing packages, system health, and updates",
        tags={"split-action"},
        annotations={
            "title": "System Health Check",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def sm_system_system_health_check(
        ctx: Context | None = None,
    ) -> Any:
        """System health check (one operation of sm_system_operations)."""
        return await call_routed(
            _sm_system_operations_routed, "system_health_check", {"ctx": ctx}
        )

    @mcp.tool(
        name="sm_system_get_uptime",
        description="Get uptime (sm_system_operations). System operations for managing packages, system health, and updates",
        tags={"split-action"},
        annotations={
            "title": "Get Uptime",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def sm_system_get_uptime(
        ctx: Context | None = None,
    ) -> Any:
        """Get uptime (one operation of sm_system_operations)."""
        return await call_routed(
            _sm_system_operations_routed, "get_uptime", {"ctx": ctx}
        )

    @mcp.tool(
        name="sm_system_get_host_record",
        description="Get host record (sm_system_operations). Returns an opaque stable host_id (never a hostname) with pendingUpdates and uptimeSeconds",
        tags={"split-action"},
        annotations={
            "title": "Get Host Record",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def sm_system_get_host_record(
        ctx: Context | None = None,
    ) -> Any:
        """Get host record (one operation of sm_system_operations)."""
        return await call_routed(
            _sm_system_operations_routed, "get_host_record", {"ctx": ctx}
        )

    @mcp.tool(
        name="sm_system_list_env_vars",
        description="List env vars (sm_system_operations). System operations for managing packages, system health, and updates",
        tags={"split-action"},
        annotations={
            "title": "List Env Vars",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def sm_system_list_env_vars(
        ctx: Context | None = None,
    ) -> Any:
        """List env vars (one operation of sm_system_operations)."""
        return await call_routed(
            _sm_system_operations_routed, "list_env_vars", {"ctx": ctx}
        )

    @mcp.tool(
        name="sm_system_get_env_var",
        description="Get env var (sm_system_operations). System operations for managing packages, system health, and updates",
        tags={"split-action"},
        annotations={
            "title": "Get Env Var",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def sm_system_get_env_var(
        env_var: str | None = Field(None, description="Environment variable name"),
        ctx: Context | None = None,
    ) -> Any:
        """Get env var (one operation of sm_system_operations)."""
        return await call_routed(
            _sm_system_operations_routed,
            "get_env_var",
            {"env_var": env_var, "ctx": ctx},
        )

    @mcp.tool(
        name="sm_system_clean_temp_files",
        description="Clean temp files (sm_system_operations). System operations for managing packages, system health, and updates",
        tags={"split-action"},
        annotations={
            "title": "Clean Temp Files",
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": False,
            "openWorldHint": True,
        },
    )
    async def sm_system_clean_temp_files(
        confirm: bool = Field(
            False,
            description=(
                "Explicit confirmation for a mutating action. Pass true when the "
                "client cannot answer an approval prompt."
            ),
        ),
        ctx: Context | None = None,
    ) -> Any:
        """Clean temp files (one operation of sm_system_operations)."""
        return await call_routed(
            _sm_system_operations_routed,
            "clean_temp_files",
            {"confirm": confirm, "ctx": ctx},
        )

    @mcp.tool(
        name="sm_system_clean_package_cache",
        description="Clean package cache (sm_system_operations). System operations for managing packages, system health, and updates",
        tags={"split-action"},
        annotations={
            "title": "Clean Package Cache",
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": False,
            "openWorldHint": True,
        },
    )
    async def sm_system_clean_package_cache(
        confirm: bool = Field(
            False,
            description=(
                "Explicit confirmation for a mutating action. Pass true when the "
                "client cannot answer an approval prompt."
            ),
        ),
        ctx: Context | None = None,
    ) -> Any:
        """Clean package cache (one operation of sm_system_operations)."""
        return await call_routed(
            _sm_system_operations_routed,
            "clean_package_cache",
            {"confirm": confirm, "ctx": ctx},
        )

    @mcp.tool(
        name="sm_system_list_windows_features",
        description="List windows features (sm_system_operations). System operations for managing packages, system health, and updates",
        tags={"split-action"},
        annotations={
            "title": "List Windows Features",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def sm_system_list_windows_features(
        ctx: Context | None = None,
    ) -> Any:
        """List windows features (one operation of sm_system_operations)."""
        return await call_routed(
            _sm_system_operations_routed, "list_windows_features", {"ctx": ctx}
        )

    @mcp.tool(
        name="sm_system_enable_windows_features",
        description="Enable windows features (sm_system_operations). System operations for managing packages, system health, and updates",
        tags={"split-action"},
        annotations={
            "title": "Enable Windows Features",
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": False,
            "openWorldHint": True,
        },
    )
    async def sm_system_enable_windows_features(
        feature_name: str | None = Field(None, description="Windows feature name"),
        confirm: bool = Field(
            False,
            description=(
                "Explicit confirmation for a mutating action. Pass true when the "
                "client cannot answer an approval prompt."
            ),
        ),
        ctx: Context | None = None,
    ) -> Any:
        """Enable windows features (one operation of sm_system_operations)."""
        return await call_routed(
            _sm_system_operations_routed,
            "enable_windows_features",
            {"feature_name": feature_name, "confirm": confirm, "ctx": ctx},
        )

    @mcp.tool(
        name="sm_system_disable_windows_features",
        description="Disable windows features (sm_system_operations). System operations for managing packages, system health, and updates",
        tags={"split-action"},
        annotations={
            "title": "Disable Windows Features",
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": False,
            "openWorldHint": True,
        },
    )
    async def sm_system_disable_windows_features(
        feature_name: str | None = Field(None, description="Windows feature name"),
        confirm: bool = Field(
            False,
            description=(
                "Explicit confirmation for a mutating action. Pass true when the "
                "client cannot answer an approval prompt."
            ),
        ),
        ctx: Context | None = None,
    ) -> Any:
        """Disable windows features (one operation of sm_system_operations)."""
        return await call_routed(
            _sm_system_operations_routed,
            "disable_windows_features",
            {"feature_name": feature_name, "confirm": confirm, "ctx": ctx},
        )

    @mcp.tool(
        name="sm_system_add_repository",
        description="Add repository (sm_system_operations). System operations for managing packages, system health, and updates",
        tags={"split-action"},
        annotations={
            "title": "Add Repository",
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": False,
            "openWorldHint": True,
        },
    )
    async def sm_system_add_repository(
        repository: str | None = Field(None, description="Repository URL or name"),
        confirm: bool = Field(
            False,
            description=(
                "Explicit confirmation for a mutating action. Pass true when the "
                "client cannot answer an approval prompt."
            ),
        ),
        ctx: Context | None = None,
    ) -> Any:
        """Add repository (one operation of sm_system_operations)."""
        return await call_routed(
            _sm_system_operations_routed,
            "add_repository",
            {"repository": repository, "confirm": confirm, "ctx": ctx},
        )

    @mcp.tool(
        name="sm_system_install_local_package",
        description="Install local package (sm_system_operations). System operations for managing packages, system health, and updates",
        tags={"split-action"},
        annotations={
            "title": "Install Local Package",
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": False,
            "openWorldHint": True,
        },
    )
    async def sm_system_install_local_package(
        file_path: str | None = Field(None, description="Path to local package file"),
        confirm: bool = Field(
            False,
            description=(
                "Explicit confirmation for a mutating action. Pass true when the "
                "client cannot answer an approval prompt."
            ),
        ),
        ctx: Context | None = None,
    ) -> Any:
        """Install local package (one operation of sm_system_operations)."""
        return await call_routed(
            _sm_system_operations_routed,
            "install_local_package",
            {"file_path": file_path, "confirm": confirm, "ctx": ctx},
        )

    async def _sm_service_operations_routed(
        action: str = Field(
            ...,
            description="Action to perform. Must be one of: "
            + ", ".join(f"'{a}'" for a in SERVICE_ACTIONS),
        ),
        service_name: str | None = Field(None, description="Name of the service"),
        confirm: bool = Field(
            False,
            description=(
                "Explicit confirmation for a mutating action. Pass true when the "
                "client cannot answer an approval prompt."
            ),
        ),
        ctx: Context | None = None,
    ) -> Any:
        resolved = _resolve_current_action(action, SERVICE_ACTIONS)
        if isinstance(resolved, dict):
            return resolved
        action = resolved
        manager = detect_and_create_manager()
        await ctx_log(
            ctx,
            f"sm_service_operations: {action}",
            logger=logger,
        )
        if action in _SERVICE_MUTATIONS and (
            (
                refused := await require_approval(
                    ctx,
                    action,
                    service_name,
                    arguments={"action": action, "service_name": service_name},
                    confirm=confirm,
                )
            )
            is not None
        ):
            return refused
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

    @mcp.tool(
        name="sm_service_list_services",
        description="List services (sm_service_operations). Operations for managing system services",
        tags={"split-action"},
        annotations={
            "title": "List Services",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def sm_service_list_services(
        ctx: Context | None = None,
    ) -> Any:
        """List services (one operation of sm_service_operations)."""
        return await call_routed(
            _sm_service_operations_routed, "list_services", {"ctx": ctx}
        )

    @mcp.tool(
        name="sm_service_get_service_status",
        description="Get service status (sm_service_operations). Operations for managing system services",
        tags={"split-action"},
        annotations={
            "title": "Get Service Status",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def sm_service_get_service_status(
        service_name: str | None = Field(None, description="Name of the service"),
        ctx: Context | None = None,
    ) -> Any:
        """Get service status (one operation of sm_service_operations)."""
        return await call_routed(
            _sm_service_operations_routed,
            "get_service_status",
            {"service_name": service_name, "ctx": ctx},
        )

    @mcp.tool(
        name="sm_service_start_service",
        description="Start service (sm_service_operations). Operations for managing system services",
        tags={"split-action"},
        annotations={
            "title": "Start Service",
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": False,
            "openWorldHint": True,
        },
    )
    async def sm_service_start_service(
        service_name: str | None = Field(None, description="Name of the service"),
        confirm: bool = Field(
            False,
            description=(
                "Explicit confirmation for a mutating action. Pass true when the "
                "client cannot answer an approval prompt."
            ),
        ),
        ctx: Context | None = None,
    ) -> Any:
        """Start service (one operation of sm_service_operations)."""
        return await call_routed(
            _sm_service_operations_routed,
            "start_service",
            {"service_name": service_name, "confirm": confirm, "ctx": ctx},
        )

    @mcp.tool(
        name="sm_service_stop_service",
        description="Stop service (sm_service_operations). Operations for managing system services",
        tags={"split-action"},
        annotations={
            "title": "Stop Service",
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": False,
            "openWorldHint": True,
        },
    )
    async def sm_service_stop_service(
        service_name: str | None = Field(None, description="Name of the service"),
        confirm: bool = Field(
            False,
            description=(
                "Explicit confirmation for a mutating action. Pass true when the "
                "client cannot answer an approval prompt."
            ),
        ),
        ctx: Context | None = None,
    ) -> Any:
        """Stop service (one operation of sm_service_operations)."""
        return await call_routed(
            _sm_service_operations_routed,
            "stop_service",
            {"service_name": service_name, "confirm": confirm, "ctx": ctx},
        )

    @mcp.tool(
        name="sm_service_restart_service",
        description="Restart service (sm_service_operations). Operations for managing system services",
        tags={"split-action"},
        annotations={
            "title": "Restart Service",
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": False,
            "openWorldHint": True,
        },
    )
    async def sm_service_restart_service(
        service_name: str | None = Field(None, description="Name of the service"),
        confirm: bool = Field(
            False,
            description=(
                "Explicit confirmation for a mutating action. Pass true when the "
                "client cannot answer an approval prompt."
            ),
        ),
        ctx: Context | None = None,
    ) -> Any:
        """Restart service (one operation of sm_service_operations)."""
        return await call_routed(
            _sm_service_operations_routed,
            "restart_service",
            {"service_name": service_name, "confirm": confirm, "ctx": ctx},
        )

    @mcp.tool(
        name="sm_service_enable_service",
        description="Enable service (sm_service_operations). Operations for managing system services",
        tags={"split-action"},
        annotations={
            "title": "Enable Service",
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": False,
            "openWorldHint": True,
        },
    )
    async def sm_service_enable_service(
        service_name: str | None = Field(None, description="Name of the service"),
        confirm: bool = Field(
            False,
            description=(
                "Explicit confirmation for a mutating action. Pass true when the "
                "client cannot answer an approval prompt."
            ),
        ),
        ctx: Context | None = None,
    ) -> Any:
        """Enable service (one operation of sm_service_operations)."""
        return await call_routed(
            _sm_service_operations_routed,
            "enable_service",
            {"service_name": service_name, "confirm": confirm, "ctx": ctx},
        )

    @mcp.tool(
        name="sm_service_disable_service",
        description="Disable service (sm_service_operations). Operations for managing system services",
        tags={"split-action"},
        annotations={
            "title": "Disable Service",
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": False,
            "openWorldHint": True,
        },
    )
    async def sm_service_disable_service(
        service_name: str | None = Field(None, description="Name of the service"),
        confirm: bool = Field(
            False,
            description=(
                "Explicit confirmation for a mutating action. Pass true when the "
                "client cannot answer an approval prompt."
            ),
        ),
        ctx: Context | None = None,
    ) -> Any:
        """Disable service (one operation of sm_service_operations)."""
        return await call_routed(
            _sm_service_operations_routed,
            "disable_service",
            {"service_name": service_name, "confirm": confirm, "ctx": ctx},
        )

    async def _sm_process_operations_routed(
        action: str = Field(
            ...,
            description="Action to perform. Must be one of: "
            + ", ".join(f"'{a}'" for a in PROCESS_ACTIONS),
        ),
        pid: int | None = Field(None, description="Process ID"),
        confirm: bool = Field(
            False,
            description=(
                "Explicit confirmation for a mutating action. Pass true when the "
                "client cannot answer an approval prompt."
            ),
        ),
        ctx: Context | None = None,
    ) -> Any:
        resolved = _resolve_current_action(action, PROCESS_ACTIONS)
        if isinstance(resolved, dict):
            return resolved
        action = resolved
        manager = detect_and_create_manager()
        await ctx_log(
            ctx,
            f"sm_process_operations: {action}",
            logger=logger,
        )
        if action == "kill_process" and (
            (
                refused := await require_approval(
                    ctx,
                    action,
                    f"process {pid}" if pid is not None else None,
                    arguments={"action": action, "pid": pid},
                    confirm=confirm,
                )
            )
            is not None
        ):
            return refused
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

    @mcp.tool(
        name="sm_process_kill_process",
        description="Kill process (sm_process_operations). Operations for managing system processes",
        tags={"split-action"},
        annotations={
            "title": "Kill Process",
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def sm_process_kill_process(
        pid: int | None = Field(None, description="Process ID"),
        confirm: bool = Field(
            False,
            description=(
                "Explicit confirmation for a mutating action. Pass true when the "
                "client cannot answer an approval prompt."
            ),
        ),
        ctx: Context | None = None,
    ) -> Any:
        """Kill process (one operation of sm_process_operations)."""
        return await call_routed(
            _sm_process_operations_routed,
            "kill_process",
            {"pid": pid, "confirm": confirm, "ctx": ctx},
        )

    @mcp.tool(
        name="sm_process_list_processes",
        description="List processes (sm_process_operations). Operations for managing system processes",
        tags={"split-action"},
        annotations={
            "title": "List Processes",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def sm_process_list_processes(
        ctx: Context | None = None,
    ) -> Any:
        """List processes (one operation of sm_process_operations)."""
        return await call_routed(
            _sm_process_operations_routed, "list_processes", {"ctx": ctx}
        )

    @mcp.tool(
        name="sm_process_get_process_info",
        description="Get process info (sm_process_operations). Operations for managing system processes",
        tags={"split-action"},
        annotations={
            "title": "Get Process Info",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def sm_process_get_process_info(
        pid: int | None = Field(None, description="Process ID"),
        ctx: Context | None = None,
    ) -> Any:
        """Get process info (one operation of sm_process_operations)."""
        return await call_routed(
            _sm_process_operations_routed, "get_process_info", {"pid": pid, "ctx": ctx}
        )

    async def _sm_network_operations_routed(
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
        await ctx_log(
            ctx,
            f"sm_network_operations: {action}",
            logger=logger,
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

    @mcp.tool(
        name="sm_network_list_network_interfaces",
        description="List network interfaces (sm_network_operations). Operations for network analysis",
        tags={"split-action"},
        annotations={
            "title": "List Network Interfaces",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def sm_network_list_network_interfaces(
        ctx: Context | None = None,
    ) -> Any:
        """List network interfaces (one operation of sm_network_operations)."""
        return await call_routed(
            _sm_network_operations_routed, "list_network_interfaces", {"ctx": ctx}
        )

    @mcp.tool(
        name="sm_network_list_open_ports",
        description="List open ports (sm_network_operations). Operations for network analysis",
        tags={"split-action"},
        annotations={
            "title": "List Open Ports",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def sm_network_list_open_ports(
        ctx: Context | None = None,
    ) -> Any:
        """List open ports (one operation of sm_network_operations)."""
        return await call_routed(
            _sm_network_operations_routed, "list_open_ports", {"ctx": ctx}
        )

    @mcp.tool(
        name="sm_network_ping_host",
        description="Ping host (sm_network_operations). Operations for network analysis",
        tags={"split-action"},
        annotations={
            "title": "Ping Host",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def sm_network_ping_host(
        host: str | None = Field(None, description="Host to ping or lookup"),
        count: int = Field(4, description="Ping count"),
        ctx: Context | None = None,
    ) -> Any:
        """Ping host (one operation of sm_network_operations)."""
        return await call_routed(
            _sm_network_operations_routed,
            "ping_host",
            {"host": host, "count": count, "ctx": ctx},
        )

    @mcp.tool(
        name="sm_network_dns_lookup",
        description="Dns lookup (sm_network_operations). Operations for network analysis",
        tags={"split-action"},
        annotations={
            "title": "Dns Lookup",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def sm_network_dns_lookup(
        host: str | None = Field(None, description="Host to ping or lookup"),
        ctx: Context | None = None,
    ) -> Any:
        """Dns lookup (one operation of sm_network_operations)."""
        return await call_routed(
            _sm_network_operations_routed, "dns_lookup", {"host": host, "ctx": ctx}
        )

    async def _sm_disk_operations_routed(
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
        await ctx_log(
            ctx,
            f"sm_disk_operations: {action}",
            logger=logger,
        )
        try:
            if action == "list_disks":
                return await run_blocking(
                    manager.list_disks,
                )
            elif action == "get_disk_usage":
                return await run_blocking(
                    manager.get_disk_usage, path or filesystem_anchor()
                )
            elif action == "get_disk_space_report":
                return await run_blocking(
                    manager.get_disk_space_report,
                )
        except Exception:
            return {"success": False, "error": "Operation failed"}

    @mcp.tool(
        name="sm_disk_list_disks",
        description="List disks (sm_disk_operations). Operations for managing system disks",
        tags={"split-action"},
        annotations={
            "title": "List Disks",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def sm_disk_list_disks(
        ctx: Context | None = None,
    ) -> Any:
        """List disks (one operation of sm_disk_operations)."""
        return await call_routed(_sm_disk_operations_routed, "list_disks", {"ctx": ctx})

    @mcp.tool(
        name="sm_disk_get_disk_usage",
        description="Get disk usage (sm_disk_operations). Operations for managing system disks",
        tags={"split-action"},
        annotations={
            "title": "Get Disk Usage",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def sm_disk_get_disk_usage(
        path: str | None = Field(None, description="Path for disk usage"),
        ctx: Context | None = None,
    ) -> Any:
        """Get disk usage (one operation of sm_disk_operations)."""
        return await call_routed(
            _sm_disk_operations_routed, "get_disk_usage", {"path": path, "ctx": ctx}
        )

    @mcp.tool(
        name="sm_disk_get_disk_space_report",
        description="Get disk space report (sm_disk_operations). Operations for managing system disks",
        tags={"split-action"},
        annotations={
            "title": "Get Disk Space Report",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def sm_disk_get_disk_space_report(
        ctx: Context | None = None,
    ) -> Any:
        """Get disk space report (one operation of sm_disk_operations)."""
        return await call_routed(
            _sm_disk_operations_routed, "get_disk_space_report", {"ctx": ctx}
        )

    async def _sm_user_operations_routed(
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
        await ctx_log(
            ctx,
            f"sm_user_operations: {action}",
            logger=logger,
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

    @mcp.tool(
        name="sm_user_list_users",
        description="List users (sm_user_operations). Operations for user and group management",
        tags={"split-action"},
        annotations={
            "title": "List Users",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def sm_user_list_users(
        ctx: Context | None = None,
    ) -> Any:
        """List users (one operation of sm_user_operations)."""
        return await call_routed(_sm_user_operations_routed, "list_users", {"ctx": ctx})

    @mcp.tool(
        name="sm_user_list_groups",
        description="List groups (sm_user_operations). Operations for user and group management",
        tags={"split-action"},
        annotations={
            "title": "List Groups",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def sm_user_list_groups(
        ctx: Context | None = None,
    ) -> Any:
        """List groups (one operation of sm_user_operations)."""
        return await call_routed(
            _sm_user_operations_routed, "list_groups", {"ctx": ctx}
        )

    async def _sm_file_operations_routed(
        action: str = Field(
            ...,
            description="Action to perform. Must be one of: "
            + ", ".join(f"'{a}'" for a in FILE_ACTIONS),
        ),
        filepath: str | None = Field(None, description="Path to file"),
        content: str | None = Field(
            None, description="Content to create or update the file with"
        ),
        file_action: Literal["read", "create", "update", "delete"] | None = Field(
            cast(Any, "read"), description="Action for text editor/manage file"
        ),
        lines: int = Field(100, description="Number of lines to tail"),
        pattern: str | None = Field(None, description="Search pattern"),
        recursive: bool = Field(False, description="Recursive search"),
        depth: int = Field(1, description="Depth for list_files"),
        confirm: bool = Field(
            False,
            description=(
                "Explicit confirmation for a mutating action. Pass true when the "
                "client cannot answer an approval prompt."
            ),
        ),
        ctx: Context | None = None,
    ) -> Any:
        resolved = _resolve_current_action(action, FILE_ACTIONS)
        if isinstance(resolved, dict):
            return resolved
        action = resolved
        manager = detect_and_create_manager()
        await ctx_log(
            ctx,
            f"sm_file_operations: {action}",
            logger=logger,
        )
        if (
            action == "manage_file"
            and file_action
            in {
                "create",
                "update",
                "delete",
            }
            and (
                (
                    refused := await require_approval(
                        ctx,
                        file_action,
                        filepath,
                        arguments={
                            "action": action,
                            "file_action": file_action,
                            "filepath": filepath,
                        },
                        confirm=confirm,
                    )
                )
                is not None
            )
        ):
            return refused
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

    @mcp.tool(
        name="sm_file_manage_file",
        description="Manage file (sm_file_operations). Operations for file and log management",
        tags={"split-action"},
        annotations={
            "title": "Manage File",
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": False,
            "openWorldHint": True,
        },
    )
    async def sm_file_manage_file(
        filepath: str | None = Field(None, description="Path to file"),
        content: str | None = Field(
            None, description="Content to create or update the file with"
        ),
        file_action: Literal["read", "create", "update", "delete"] | None = Field(
            cast(Any, "read"), description="Action for text editor/manage file"
        ),
        confirm: bool = Field(
            False,
            description=(
                "Explicit confirmation for a mutating action. Pass true when the "
                "client cannot answer an approval prompt."
            ),
        ),
        ctx: Context | None = None,
    ) -> Any:
        """Manage file (one operation of sm_file_operations)."""
        return await call_routed(
            _sm_file_operations_routed,
            "manage_file",
            {
                "filepath": filepath,
                "content": content,
                "file_action": file_action,
                "confirm": confirm,
                "ctx": ctx,
            },
        )

    @mcp.tool(
        name="sm_file_get_system_logs",
        description="Get system logs (sm_file_operations). Operations for file and log management",
        tags={"split-action"},
        annotations={
            "title": "Get System Logs",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def sm_file_get_system_logs(
        lines: int = Field(100, description="Number of lines to tail"),
        ctx: Context | None = None,
    ) -> Any:
        """Get system logs (one operation of sm_file_operations)."""
        return await call_routed(
            _sm_file_operations_routed, "get_system_logs", {"lines": lines, "ctx": ctx}
        )

    @mcp.tool(
        name="sm_file_tail_log_file",
        description="Tail log file (sm_file_operations). Operations for file and log management",
        tags={"split-action"},
        annotations={
            "title": "Tail Log File",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def sm_file_tail_log_file(
        filepath: str | None = Field(None, description="Path to file"),
        lines: int = Field(100, description="Number of lines to tail"),
        ctx: Context | None = None,
    ) -> Any:
        """Tail log file (one operation of sm_file_operations)."""
        return await call_routed(
            _sm_file_operations_routed,
            "tail_log_file",
            {"filepath": filepath, "lines": lines, "ctx": ctx},
        )

    @mcp.tool(
        name="sm_file_list_files",
        description="List files (sm_file_operations). Operations for file and log management",
        tags={"split-action"},
        annotations={
            "title": "List Files",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def sm_file_list_files(
        filepath: str | None = Field(None, description="Path to file"),
        recursive: bool = Field(False, description="Recursive search"),
        depth: int = Field(1, description="Depth for list_files"),
        ctx: Context | None = None,
    ) -> Any:
        """List files (one operation of sm_file_operations)."""
        return await call_routed(
            _sm_file_operations_routed,
            "list_files",
            {"filepath": filepath, "recursive": recursive, "depth": depth, "ctx": ctx},
        )

    @mcp.tool(
        name="sm_file_search_files",
        description="Search files (sm_file_operations). Operations for file and log management",
        tags={"split-action"},
        annotations={
            "title": "Search Files",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def sm_file_search_files(
        filepath: str | None = Field(None, description="Path to file"),
        pattern: str | None = Field(None, description="Search pattern"),
        ctx: Context | None = None,
    ) -> Any:
        """Search files (one operation of sm_file_operations)."""
        return await call_routed(
            _sm_file_operations_routed,
            "search_files",
            {"filepath": filepath, "pattern": pattern, "ctx": ctx},
        )

    @mcp.tool(
        name="sm_file_grep_files",
        description="Grep files (sm_file_operations). Operations for file and log management",
        tags={"split-action"},
        annotations={
            "title": "Grep Files",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def sm_file_grep_files(
        filepath: str | None = Field(None, description="Path to file"),
        pattern: str | None = Field(None, description="Search pattern"),
        recursive: bool = Field(False, description="Recursive search"),
        ctx: Context | None = None,
    ) -> Any:
        """Grep files (one operation of sm_file_operations)."""
        return await call_routed(
            _sm_file_operations_routed,
            "grep_files",
            {
                "filepath": filepath,
                "pattern": pattern,
                "recursive": recursive,
                "ctx": ctx,
            },
        )

    async def _sm_cron_operations_routed(
        action: str = Field(
            ...,
            description="Action to perform. Must be one of: "
            + ", ".join(f"'{a}'" for a in CRON_ACTIONS),
        ),
        job_ref: str | None = Field(
            None, description="Opaque job reference returned by list_cron_jobs"
        ),
        user: str | None = Field(None, description="User for cron job"),
        confirm: bool = Field(
            False,
            description=(
                "Explicit confirmation for a mutating action. Pass true when the "
                "client cannot answer an approval prompt."
            ),
        ),
        ctx: Context | None = None,
    ) -> Any:
        resolved = _resolve_current_action(action, CRON_ACTIONS)
        if isinstance(resolved, dict):
            return resolved
        action = resolved
        manager = detect_and_create_manager()
        await ctx_log(
            ctx,
            f"sm_cron_operations: {action}",
            logger=logger,
        )
        if action == "remove_cron_job" and (
            (
                refused := await require_approval(
                    ctx,
                    action,
                    "configured schedule",
                    arguments={"action": action, "job_ref": job_ref, "user": user},
                    confirm=confirm,
                )
            )
            is not None
        ):
            return refused
        try:
            if action == "list_cron_jobs":
                return await run_blocking(manager.list_cron_jobs, user)
            elif action == "remove_cron_job":
                return await run_blocking(manager.remove_cron_job, job_ref or "", user)
        except Exception:
            return {"success": False, "error": "Operation failed"}

    @mcp.tool(
        name="sm_cron_remove_cron_job",
        description="Remove cron job (sm_cron_operations). Operations for cron jobs",
        tags={"split-action"},
        annotations={
            "title": "Remove Cron Job",
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def sm_cron_remove_cron_job(
        job_ref: str | None = Field(
            None, description="Opaque job reference returned by list_cron_jobs"
        ),
        user: str | None = Field(None, description="User for cron job"),
        confirm: bool = Field(
            False,
            description=(
                "Explicit confirmation for a mutating action. Pass true when the "
                "client cannot answer an approval prompt."
            ),
        ),
        ctx: Context | None = None,
    ) -> Any:
        """Remove cron job (one operation of sm_cron_operations)."""
        return await call_routed(
            _sm_cron_operations_routed,
            "remove_cron_job",
            {"job_ref": job_ref, "user": user, "confirm": confirm, "ctx": ctx},
        )

    @mcp.tool(
        name="sm_cron_list_cron_jobs",
        description="List cron jobs (sm_cron_operations). Operations for cron jobs",
        tags={"split-action"},
        annotations={
            "title": "List Cron Jobs",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def sm_cron_list_cron_jobs(
        user: str | None = Field(None, description="User for cron job"),
        ctx: Context | None = None,
    ) -> Any:
        """List cron jobs (one operation of sm_cron_operations)."""
        return await call_routed(
            _sm_cron_operations_routed, "list_cron_jobs", {"user": user, "ctx": ctx}
        )

    async def _sm_firewall_operations_routed(
        action: str = Field(
            ...,
            description="Action to perform. Must be one of: "
            + ", ".join(f"'{a}'" for a in FIREWALL_ACTIONS),
        ),
        rule: FirewallRuleSpec | None = Field(
            None, description="Structured firewall rule specification"
        ),
        confirm: bool = Field(
            False,
            description=(
                "Explicit confirmation for a mutating action. Pass true when the "
                "client cannot answer an approval prompt."
            ),
        ),
        ctx: Context | None = None,
    ) -> Any:
        resolved = _resolve_current_action(action, FIREWALL_ACTIONS)
        if isinstance(resolved, dict):
            return resolved
        action = resolved
        manager = detect_and_create_manager()
        await ctx_log(
            ctx,
            f"sm_firewall_operations: {action}",
            logger=logger,
        )
        if action in {"add_firewall_rule", "remove_firewall_rule"} and (
            (
                refused := await require_approval(
                    ctx,
                    action,
                    rule.name if rule is not None else None,
                    arguments={
                        "action": action,
                        "rule": (
                            rule.model_dump(mode="json") if rule is not None else None
                        ),
                    },
                    confirm=confirm,
                )
            )
            is not None
        ):
            return refused
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

    @mcp.tool(
        name="sm_firewall_get_firewall_status",
        description="Get firewall status (sm_firewall_operations). Operations for firewall management",
        tags={"split-action"},
        annotations={
            "title": "Get Firewall Status",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def sm_firewall_get_firewall_status(
        ctx: Context | None = None,
    ) -> Any:
        """Get firewall status (one operation of sm_firewall_operations)."""
        return await call_routed(
            _sm_firewall_operations_routed, "get_firewall_status", {"ctx": ctx}
        )

    @mcp.tool(
        name="sm_firewall_add_firewall_rule",
        description="Add firewall rule (sm_firewall_operations). Operations for firewall management",
        tags={"split-action"},
        annotations={
            "title": "Add Firewall Rule",
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": False,
            "openWorldHint": True,
        },
    )
    async def sm_firewall_add_firewall_rule(
        rule: FirewallRuleSpec | None = Field(
            None, description="Structured firewall rule specification"
        ),
        confirm: bool = Field(
            False,
            description=(
                "Explicit confirmation for a mutating action. Pass true when the "
                "client cannot answer an approval prompt."
            ),
        ),
        ctx: Context | None = None,
    ) -> Any:
        """Add firewall rule (one operation of sm_firewall_operations)."""
        return await call_routed(
            _sm_firewall_operations_routed,
            "add_firewall_rule",
            {"rule": rule, "confirm": confirm, "ctx": ctx},
        )

    @mcp.tool(
        name="sm_firewall_remove_firewall_rule",
        description="Remove firewall rule (sm_firewall_operations). Operations for firewall management",
        tags={"split-action"},
        annotations={
            "title": "Remove Firewall Rule",
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def sm_firewall_remove_firewall_rule(
        rule: FirewallRuleSpec | None = Field(
            None, description="Structured firewall rule specification"
        ),
        confirm: bool = Field(
            False,
            description=(
                "Explicit confirmation for a mutating action. Pass true when the "
                "client cannot answer an approval prompt."
            ),
        ),
        ctx: Context | None = None,
    ) -> Any:
        """Remove firewall rule (one operation of sm_firewall_operations)."""
        return await call_routed(
            _sm_firewall_operations_routed,
            "remove_firewall_rule",
            {"rule": rule, "confirm": confirm, "ctx": ctx},
        )

    async def _sm_advanced_operations_routed(
        action: str = Field(
            ...,
            description="Action to perform. Must be one of: "
            + ", ".join(f"'{a}'" for a in ADVANCED_ACTIONS),
        ),
        public_key: str | None = Field(None, description="Public key content"),
        path: str | None = Field(None, description="Path for venv"),
        version: str | None = Field(None, description="Version of python/node"),
        package: str | None = Field(None, description="Package name to install"),
        confirm: bool = Field(
            False,
            description=(
                "Explicit confirmation for a mutating action. Pass true when the "
                "client cannot answer an approval prompt."
            ),
        ),
        ctx: Context | None = None,
    ) -> Any:
        resolved = _resolve_current_action(action, ADVANCED_ACTIONS)
        if isinstance(resolved, dict):
            return resolved
        action = resolved
        manager = detect_and_create_manager()
        await ctx_log(
            ctx,
            f"sm_advanced_operations: {action}",
            logger=logger,
        )
        if (
            refused := await require_approval(
                ctx,
                action,
                "configured host",
                arguments={"action": action, "path": path, "package": package},
                confirm=confirm,
            )
        ) is not None:
            return refused
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
        name="sm_advanced_add_authorized_key",
        description="Add authorized key (sm_advanced_operations). Operations for SSH and specialized managers",
        tags={"split-action"},
        annotations={
            "title": "Add Authorized Key",
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": False,
            "openWorldHint": True,
        },
    )
    async def sm_advanced_add_authorized_key(
        public_key: str | None = Field(None, description="Public key content"),
        confirm: bool = Field(
            False,
            description=(
                "Explicit confirmation for a mutating action. Pass true when the "
                "client cannot answer an approval prompt."
            ),
        ),
        ctx: Context | None = None,
    ) -> Any:
        """Add authorized key (one operation of sm_advanced_operations)."""
        return await call_routed(
            _sm_advanced_operations_routed,
            "add_authorized_key",
            {"public_key": public_key, "confirm": confirm, "ctx": ctx},
        )

    @mcp.tool(
        name="sm_advanced_install_uv",
        description="Install uv (sm_advanced_operations). Operations for SSH and specialized managers",
        tags={"split-action"},
        annotations={
            "title": "Install Uv",
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": False,
            "openWorldHint": True,
        },
    )
    async def sm_advanced_install_uv(
        confirm: bool = Field(
            False,
            description=(
                "Explicit confirmation for a mutating action. Pass true when the "
                "client cannot answer an approval prompt."
            ),
        ),
        ctx: Context | None = None,
    ) -> Any:
        """Install uv (one operation of sm_advanced_operations)."""
        return await call_routed(
            _sm_advanced_operations_routed,
            "install_uv",
            {"confirm": confirm, "ctx": ctx},
        )

    @mcp.tool(
        name="sm_advanced_create_venv",
        description="Create venv (sm_advanced_operations). Operations for SSH and specialized managers",
        tags={"split-action"},
        annotations={
            "title": "Create Venv",
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": False,
            "openWorldHint": True,
        },
    )
    async def sm_advanced_create_venv(
        path: str | None = Field(None, description="Path for venv"),
        version: str | None = Field(None, description="Version of python/node"),
        confirm: bool = Field(
            False,
            description=(
                "Explicit confirmation for a mutating action. Pass true when the "
                "client cannot answer an approval prompt."
            ),
        ),
        ctx: Context | None = None,
    ) -> Any:
        """Create venv (one operation of sm_advanced_operations)."""
        return await call_routed(
            _sm_advanced_operations_routed,
            "create_venv",
            {"path": path, "version": version, "confirm": confirm, "ctx": ctx},
        )

    @mcp.tool(
        name="sm_advanced_install_package",
        description="Install package (sm_advanced_operations). Operations for SSH and specialized managers",
        tags={"split-action"},
        annotations={
            "title": "Install Package",
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": False,
            "openWorldHint": True,
        },
    )
    async def sm_advanced_install_package(
        path: str | None = Field(None, description="Path for venv"),
        package: str | None = Field(None, description="Package name to install"),
        confirm: bool = Field(
            False,
            description=(
                "Explicit confirmation for a mutating action. Pass true when the "
                "client cannot answer an approval prompt."
            ),
        ),
        ctx: Context | None = None,
    ) -> Any:
        """Install package (one operation of sm_advanced_operations)."""
        return await call_routed(
            _sm_advanced_operations_routed,
            "install_package",
            {"path": path, "package": package, "confirm": confirm, "ctx": ctx},
        )

    @mcp.tool(
        name="sm_advanced_install_nvm",
        description="Install nvm (sm_advanced_operations). Operations for SSH and specialized managers",
        tags={"split-action"},
        annotations={
            "title": "Install Nvm",
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": False,
            "openWorldHint": True,
        },
    )
    async def sm_advanced_install_nvm(
        confirm: bool = Field(
            False,
            description=(
                "Explicit confirmation for a mutating action. Pass true when the "
                "client cannot answer an approval prompt."
            ),
        ),
        ctx: Context | None = None,
    ) -> Any:
        """Install nvm (one operation of sm_advanced_operations)."""
        return await call_routed(
            _sm_advanced_operations_routed,
            "install_nvm",
            {"confirm": confirm, "ctx": ctx},
        )

    @mcp.tool(
        name="sm_advanced_install_node",
        description="Install node (sm_advanced_operations). Operations for SSH and specialized managers",
        tags={"split-action"},
        annotations={
            "title": "Install Node",
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": False,
            "openWorldHint": True,
        },
    )
    async def sm_advanced_install_node(
        version: str | None = Field(None, description="Version of python/node"),
        confirm: bool = Field(
            False,
            description=(
                "Explicit confirmation for a mutating action. Pass true when the "
                "client cannot answer an approval prompt."
            ),
        ),
        ctx: Context | None = None,
    ) -> Any:
        """Install node (one operation of sm_advanced_operations)."""
        return await call_routed(
            _sm_advanced_operations_routed,
            "install_node",
            {"version": version, "confirm": confirm, "ctx": ctx},
        )

    @mcp.tool(
        name="sm_advanced_use_node",
        description="Use node (sm_advanced_operations). Operations for SSH and specialized managers",
        tags={"split-action"},
        annotations={
            "title": "Use Node",
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": False,
            "openWorldHint": True,
        },
    )
    async def sm_advanced_use_node(
        version: str | None = Field(None, description="Version of python/node"),
        confirm: bool = Field(
            False,
            description=(
                "Explicit confirmation for a mutating action. Pass true when the "
                "client cannot answer an approval prompt."
            ),
        ),
        ctx: Context | None = None,
    ) -> Any:
        """Use node (one operation of sm_advanced_operations)."""
        return await call_routed(
            _sm_advanced_operations_routed,
            "use_node",
            {"version": version, "confirm": confirm, "ctx": ctx},
        )

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
        await ctx_log(
            ctx,
            "systems_ingest_host",
            logger=logger,
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
            result = await ingest_host_inventory(report)
        except Exception:  # noqa: BLE001 - do not disclose engine/session details
            return {
                "target": "local",
                "success": False,
                "error": "Graph ingestion failed",
            }
        return {"target": "local", "success": True, "ingested": result}

    # Fail closed: any registered tool without a policy class refuses startup.
    assert_tools_classified(mcp, _ALL_CLASSIFIED_TOOLS)
    mcp.add_middleware(SystemsSecurityMiddleware())


def mcp_server() -> None:
    args, mcp, _ = get_mcp_instance()
    print(f"systems-manager MCP v{package_version('systems-manager')}", file=sys.stderr)
    print("\nStarting MCP Server", file=sys.stderr)
    print(f"  Transport: {args.transport.upper()}", file=sys.stderr)
    print(f"  Auth: {args.auth_type}", file=sys.stderr)

    # Network transports are fail-closed by the SDK served security profile,
    # applied inside create_mcp_server; nothing to re-check here.
    if args.transport == "stdio":
        # Stdout purity is owned fd-level by the MCP SDK's own stdio_server()
        # (scion-sdk B-19): it claims fd 1 exclusively and dup2()s stderr
        # over it for every other writer, so no process-wide patch is needed.
        mcp.run(transport="stdio")
    elif args.transport == "streamable-http":
        mcp.run(
            transport="streamable-http",
            host=args.host,
            port=args.port,
        )
    elif args.transport == "sse":
        mcp.run(
            transport="sse",
            host=args.host,
            port=args.port,
        )
    else:
        logger.error("Invalid transport", extra={"transport": args.transport})
        sys.exit(1)


def main():
    mcp_server()


if __name__ == "__main__":
    main()
