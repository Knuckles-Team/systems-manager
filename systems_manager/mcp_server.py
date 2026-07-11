#!/usr/bin/env python
import argparse
import logging
import sys
import warnings
from typing import Any, Literal, cast

from fastmcp import Context, FastMCP
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

from agent_utilities.core.config import setting
from agent_utilities.mcp_utilities import (
    create_mcp_server,
    ctx_log,
    load_config,
    register_tool_surface,
    resolve_action,
    run_blocking,
)

from systems_manager.os_provider_tools import register_os_provider_tools
from systems_manager.storage_tools import register_storage_health_tools
from systems_manager.systems_manager import (
    SystemsManagerBase,
    WindowsManager,
    detect_and_create_manager,
)

__version__ = "1.35.3"

logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = get_logger("SystemsManagerServer")

# Canonical action sets per action-routed tool. Used both as the documented
# enum in each tool's ``action`` Field and by ``resolve_action`` to provide
# list_actions discovery, plural->singular aliases, and did-you-mean errors.
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
    "run_command",
    "get_system_logs",
    "tail_log_file",
    "list_files",
    "search_files",
    "grep_files",
    "manage_file",
)
CRON_ACTIONS = ("list_cron_jobs", "add_cron_job", "remove_cron_job")
FIREWALL_ACTIONS = (
    "get_firewall_status",
    "add_firewall_rule",
    "remove_firewall_rule",
)
ADVANCED_ACTIONS = (
    "add_authorized_key",
    "add_alias",
    "install_uv",
    "create_venv",
    "install_package",
    "install_nvm",
    "install_node",
    "use_node",
)


def get_mcp_instance() -> tuple[argparse.Namespace, FastMCP, list[Any]]:
    """Initialize the MCP server."""
    load_config()
    args, mcp, middlewares = create_mcp_server(
        name="systems-manager",
        version=__version__,
        instructions="Systems Manager MCP Server",
    )

    if bool(setting("MISCTOOL", True)):

        @mcp.tool(annotations={"title": "Health Check"})
        async def health_check() -> str:
            return "OK"

    from systems_manager.agent_os_tools import (
        register_agent_health_tools,
        register_identity_tools,
        register_maintenance_tools,
        register_policy_tools,
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
            register_maintenance_tools,
            register_policy_tools,
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
        target_host: str | None = Field(
            None, description="Optional target remote host from inventory"
        ),
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
        resolved = resolve_action(action, SYSTEM_ACTIONS, service="systems-manager")
        if isinstance(resolved, dict):
            return resolved
        action = resolved
        manager = detect_and_create_manager(host=target_host)
        ctx_log(
            ctx,
            logger,
            "info",
            f"sm_system_operations: {action} target_host={target_host}",
        )
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
        except Exception as e:
            return f"Error: {str(e)}"

    @mcp.tool(description="Operations for managing system services")
    async def sm_service_operations(
        action: str = Field(
            ...,
            description="Action to perform. Must be one of: "
            + ", ".join(f"'{a}'" for a in SERVICE_ACTIONS),
        ),
        service_name: str | None = Field(None, description="Name of the service"),
        target_host: str | None = Field(
            None, description="Optional target remote host from inventory"
        ),
        ctx: Context | None = None,
    ) -> Any:
        resolved = resolve_action(action, SERVICE_ACTIONS, service="systems-manager")
        if isinstance(resolved, dict):
            return resolved
        action = resolved
        manager = detect_and_create_manager(host=target_host)
        ctx_log(
            ctx,
            logger,
            "info",
            f"sm_service_operations: {action} {service_name} target_host={target_host}",
        )
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
        except Exception as e:
            return f"Error: {str(e)}"

    @mcp.tool(description="Operations for managing system processes")
    async def sm_process_operations(
        action: str = Field(
            ...,
            description="Action to perform. Must be one of: "
            + ", ".join(f"'{a}'" for a in PROCESS_ACTIONS),
        ),
        pid: int | None = Field(None, description="Process ID"),
        name: str | None = Field(None, description="Process name"),
        target_host: str | None = Field(
            None, description="Optional target remote host from inventory"
        ),
        ctx: Context | None = None,
    ) -> Any:
        resolved = resolve_action(action, PROCESS_ACTIONS, service="systems-manager")
        if isinstance(resolved, dict):
            return resolved
        action = resolved
        manager = detect_and_create_manager(host=target_host)
        ctx_log(
            ctx,
            logger,
            "info",
            f"sm_process_operations: {action} pid={pid} name={name} target_host={target_host}",
        )
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
        except Exception as e:
            return f"Error: {str(e)}"

    @mcp.tool(description="Operations for network analysis")
    async def sm_network_operations(
        action: str = Field(
            ...,
            description="Action to perform. Must be one of: "
            + ", ".join(f"'{a}'" for a in NETWORK_ACTIONS),
        ),
        host: str | None = Field(None, description="Host to ping or lookup"),
        count: int = Field(4, description="Ping count"),
        target_host: str | None = Field(
            None, description="Optional target remote host from inventory"
        ),
        ctx: Context | None = None,
    ) -> Any:
        resolved = resolve_action(action, NETWORK_ACTIONS, service="systems-manager")
        if isinstance(resolved, dict):
            return resolved
        action = resolved
        manager = detect_and_create_manager(host=target_host)
        ctx_log(
            ctx,
            logger,
            "info",
            f"sm_network_operations: {action} target_host={target_host}",
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
        except Exception as e:
            return f"Error: {str(e)}"

    @mcp.tool(description="Operations for managing system disks")
    async def sm_disk_operations(
        action: str = Field(
            ...,
            description="Action to perform. Must be one of: "
            + ", ".join(f"'{a}'" for a in DISK_ACTIONS),
        ),
        path: str | None = Field(None, description="Path for disk usage"),
        target_host: str | None = Field(
            None, description="Optional target remote host from inventory"
        ),
        ctx: Context | None = None,
    ) -> Any:
        resolved = resolve_action(action, DISK_ACTIONS, service="systems-manager")
        if isinstance(resolved, dict):
            return resolved
        action = resolved
        manager = detect_and_create_manager(host=target_host)
        ctx_log(
            ctx,
            logger,
            "info",
            f"sm_disk_operations: {action} target_host={target_host}",
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
        except Exception as e:
            return f"Error: {str(e)}"

    @mcp.tool(description="Operations for user and group management")
    async def sm_user_operations(
        action: str = Field(
            ...,
            description="Action to perform. Must be one of: "
            + ", ".join(f"'{a}'" for a in USER_ACTIONS),
        ),
        target_host: str | None = Field(
            None, description="Optional target remote host from inventory"
        ),
        ctx: Context | None = None,
    ) -> Any:
        resolved = resolve_action(action, USER_ACTIONS, service="systems-manager")
        if isinstance(resolved, dict):
            return resolved
        action = resolved
        manager = detect_and_create_manager(host=target_host)
        ctx_log(
            ctx,
            logger,
            "info",
            f"sm_user_operations: {action} target_host={target_host}",
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
        except Exception as e:
            return f"Error: {str(e)}"

    @mcp.tool(description="Operations for file and log management")
    async def sm_file_operations(
        action: str = Field(
            ...,
            description="Action to perform. Must be one of: "
            + ", ".join(f"'{a}'" for a in FILE_ACTIONS),
        ),
        command: str | None = Field(None, description="Command to run"),
        filepath: str | None = Field(None, description="Path to file"),
        content: str | None = Field(None, description="Content to write/append"),
        file_action: (
            Literal["read", "write", "append", "delete", "create"] | None
        ) = Field(cast(Any, "read"), description="Action for text editor/manage file"),
        lines: int = Field(100, description="Number of lines to tail"),
        pattern: str | None = Field(None, description="Search pattern"),
        recursive: bool = Field(False, description="Recursive search"),
        depth: int = Field(1, description="Depth for list_files"),
        target_host: str | None = Field(
            None, description="Optional target remote host from inventory"
        ),
        ctx: Context | None = None,
    ) -> Any:
        resolved = resolve_action(action, FILE_ACTIONS, service="systems-manager")
        if isinstance(resolved, dict):
            return resolved
        action = resolved
        manager = detect_and_create_manager(host=target_host)
        ctx_log(
            ctx,
            logger,
            "info",
            f"sm_file_operations: {action} target_host={target_host}",
        )
        try:
            if action == "run_command":
                return await run_blocking(manager.run_command, command or "")
            elif action == "get_system_logs":
                return await run_blocking(manager.get_system_logs, lines=lines)
            elif action == "tail_log_file":
                return await run_blocking(manager.tail_log_file, filepath or "", lines)
            elif action == "list_files":
                return manager.fs_manager.list_files(filepath or ".", recursive, depth)
            elif action == "search_files":
                return manager.fs_manager.search_files(filepath or ".", pattern or "")
            elif action == "grep_files":
                return manager.fs_manager.grep_files(
                    filepath or ".", pattern or "", recursive
                )
            elif action == "manage_file":
                return manager.fs_manager.manage_file(
                    file_action or "read", filepath or "", content or ""
                )
        except Exception as e:
            return f"Error: {str(e)}"

    @mcp.tool(description="Operations for cron jobs")
    async def sm_cron_operations(
        action: str = Field(
            ...,
            description="Action to perform. Must be one of: "
            + ", ".join(f"'{a}'" for a in CRON_ACTIONS),
        ),
        command: str | None = Field(None, description="Command for cron job"),
        schedule: str | None = Field(None, description="Cron schedule expression"),
        user: str | None = Field(None, description="User for cron job"),
        target_host: str | None = Field(
            None, description="Optional target remote host from inventory"
        ),
        ctx: Context | None = None,
    ) -> Any:
        resolved = resolve_action(action, CRON_ACTIONS, service="systems-manager")
        if isinstance(resolved, dict):
            return resolved
        action = resolved
        manager = detect_and_create_manager(host=target_host)
        ctx_log(
            ctx,
            logger,
            "info",
            f"sm_cron_operations: {action} target_host={target_host}",
        )
        try:
            if action == "list_cron_jobs":
                return await run_blocking(manager.list_cron_jobs, user)
            elif action == "add_cron_job":
                return await run_blocking(
                    manager.add_cron_job, command or "", schedule or "", user
                )
            elif action == "remove_cron_job":
                return await run_blocking(manager.remove_cron_job, command or "", user)
        except Exception as e:
            return f"Error: {str(e)}"

    @mcp.tool(description="Operations for firewall management")
    async def sm_firewall_operations(
        action: str = Field(
            ...,
            description="Action to perform. Must be one of: "
            + ", ".join(f"'{a}'" for a in FIREWALL_ACTIONS),
        ),
        rule: str | None = Field(
            None, description="Firewall rule (e.g. 'allow 80/tcp')"
        ),
        target_host: str | None = Field(
            None, description="Optional target remote host from inventory"
        ),
        ctx: Context | None = None,
    ) -> Any:
        resolved = resolve_action(action, FIREWALL_ACTIONS, service="systems-manager")
        if isinstance(resolved, dict):
            return resolved
        action = resolved
        manager = detect_and_create_manager(host=target_host)
        ctx_log(
            ctx,
            logger,
            "info",
            f"sm_firewall_operations: {action} target_host={target_host}",
        )
        try:
            if action == "get_firewall_status":
                return await run_blocking(
                    manager.get_firewall_status,
                )
            elif action == "add_firewall_rule":
                return await run_blocking(manager.add_firewall_rule, rule or "")
            elif action == "remove_firewall_rule":
                return await run_blocking(manager.remove_firewall_rule, rule or "")
        except Exception as e:
            return f"Error: {str(e)}"

    @mcp.tool(description="Operations for SSH and specialized managers")
    async def sm_advanced_operations(
        action: str = Field(
            ...,
            description="Action to perform. Must be one of: "
            + ", ".join(f"'{a}'" for a in ADVANCED_ACTIONS),
        ),
        public_key: str | None = Field(None, description="Public key content"),
        name: str | None = Field(None, description="Name for alias or environment"),
        command: str | None = Field(None, description="Command for alias"),
        path: str | None = Field(None, description="Path for venv"),
        version: str | None = Field(None, description="Version of python/node"),
        package: str | None = Field(None, description="Package name to install"),
        target_host: str | None = Field(
            None, description="Optional target remote host from inventory"
        ),
        ctx: Context | None = None,
    ) -> Any:
        resolved = resolve_action(action, ADVANCED_ACTIONS, service="systems-manager")
        if isinstance(resolved, dict):
            return resolved
        action = resolved
        manager = detect_and_create_manager(host=target_host)
        ctx_log(
            ctx,
            logger,
            "info",
            f"sm_advanced_operations: {action} target_host={target_host}",
        )
        try:
            if action == "add_authorized_key":
                return await run_blocking(manager.add_authorized_key, public_key or "")
            elif action == "add_alias":
                return manager.shell_manager.add_alias(name or "", command or "")
            elif action == "install_uv":
                return manager.python_manager.install_uv()
            elif action == "create_venv":
                return manager.python_manager.create_venv(path or "", version)
            elif action == "install_package":
                return manager.python_manager.install_package(package or "", path)
            elif action == "install_nvm":
                return manager.node_manager.install_nvm()
            elif action == "install_node":
                return manager.node_manager.install_node(version or "node")
            elif action == "use_node":
                return manager.node_manager.use_node(version or "node")
        except Exception as e:
            return f"Error: {str(e)}"

    @mcp.tool(
        description=(
            "Natively ingest a host's telemetry into the epistemic-graph "
            "knowledge graph as typed :HardwareNode + :NetworkInterface + "
            ":DiskVolume nodes (Wire-First). Best-effort: no-ops when no engine "
            "is reachable."
        )
    )
    async def systems_ingest_host(
        target_host: str | None = Field(
            None, description="Optional target remote host from inventory"
        ),
        ctx: Context | None = None,
    ) -> Any:
        """Gather OS/hardware/network/disk state over the manager seam and push it
        into the knowledge graph via the fast engine client.

        CONCEPT:AU-KG.ingest.enterprise-source-extractor.
        """
        from systems_manager.kg_ingest import ingest_host_inventory

        manager = detect_and_create_manager(host=target_host)
        ctx_log(
            ctx,
            logger,
            "info",
            f"systems_ingest_host: target_host={target_host}",
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
        except Exception as e:  # noqa: BLE001 — telemetry gather is best-effort
            return {"error": str(e), "ingested": None}

        report = {
            "host": target_host,
            "os": os_stats if isinstance(os_stats, dict) else {},
            "hardware": hw_stats if isinstance(hw_stats, dict) else {},
            "interfaces": (
                (net or {}).get("interfaces") if isinstance(net, dict) else None
            ),
            "disks": (disks or {}).get("disks") if isinstance(disks, dict) else None,
        }
        result = ingest_host_inventory(report)
        return {"host": target_host or "localhost", "ingested": result}

    return args, mcp, middlewares


def mcp_server() -> None:
    args, mcp, middlewares = get_mcp_instance()
    print(f"systems-manager MCP v{__version__}", file=sys.stderr)
    print("\nStarting MCP Server", file=sys.stderr)
    print(f"  Transport: {args.transport.upper()}", file=sys.stderr)
    print(f"  Auth: {args.auth_type}", file=sys.stderr)

    if args.transport == "stdio":
        mcp.run(transport="stdio")
    elif args.transport == "streamable-http":
        mcp.run(transport="streamable-http", host=args.host, port=args.port)
    elif args.transport == "sse":
        mcp.run(transport="sse", host=args.host, port=args.port)
    else:
        logger.error("Invalid transport", extra={"transport": args.transport})
        sys.exit(1)


def main():
    mcp_server()


if __name__ == "__main__":
    main()
