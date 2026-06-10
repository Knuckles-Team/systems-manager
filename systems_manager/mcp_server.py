#!/usr/bin/env python
import argparse
import logging
import os
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

from agent_utilities.base_utilities import to_boolean
from agent_utilities.mcp_utilities import (
    create_mcp_server,
    ctx_log,
)
from dotenv import find_dotenv, load_dotenv

from systems_manager.os_provider_tools import register_os_provider_tools
from systems_manager.systems_manager import (
    WindowsManager,
    detect_and_create_manager,
)

__version__ = "1.30.0"

logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = get_logger("SystemsManagerServer")


def get_mcp_instance() -> tuple[argparse.Namespace, FastMCP, list[Any]]:
    """Initialize the MCP server."""
    load_dotenv(find_dotenv())
    args, mcp, middlewares = create_mcp_server(
        name="systems-manager",
        version=__version__,
        instructions="Systems Manager MCP Server",
    )

    DEFAULT_MISCTOOL = to_boolean(os.getenv("MISCTOOL", "True"))
    if DEFAULT_MISCTOOL:

        @mcp.tool(annotations={"title": "Health Check"})
        async def health_check() -> str:
            return "OK"

    # Register OS provider tools if needed
    register_os_provider_tools(mcp)

    # Register Agent OS tools
    from systems_manager.agent_os_tools import (
        register_agent_health_tools,
        register_identity_tools,
        register_maintenance_tools,
        register_policy_tools,
        register_specialist_registry_tools,
        register_watchdog_tools,
    )

    register_agent_health_tools(mcp)
    register_identity_tools(mcp)
    register_maintenance_tools(mcp)
    register_policy_tools(mcp)
    register_specialist_registry_tools(mcp)
    register_watchdog_tools(mcp)

    @mcp.tool(
        description="System operations for managing packages, system health, and updates"
    )
    async def sm_system_operations(
        action: Literal[
            "install_applications",
            "update",
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
        ] = Field(..., description="Action to perform"),
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
        ctx: Context | None = None,
    ) -> Any:
        manager = detect_and_create_manager(host=target_host)
        ctx_log(
            ctx,
            logger,
            "info",
            f"sm_system_operations: {action} target_host={target_host}",
        )
        try:
            if action == "install_applications":
                return manager.install_applications(packages or [])
            elif action == "update":
                return manager.update()
            elif action == "clean":
                return manager.clean()
            elif action == "optimize":
                return manager.optimize()
            elif action == "install_python_modules":
                return manager.install_python_modules(packages or [])
            elif action == "get_os_statistics":
                return manager.get_os_statistics()
            elif action == "get_hardware_statistics":
                return manager.get_hardware_statistics()
            elif action == "search_package":
                return manager.search_package(package or "")
            elif action == "get_package_info":
                return manager.get_package_info(package or "")
            elif action == "list_installed_packages":
                return manager.list_installed_packages()
            elif action == "list_upgradable_packages":
                return manager.list_upgradable_packages()
            elif action == "system_health_check":
                return manager.system_health_check()
            elif action == "get_uptime":
                return manager.get_uptime()
            elif action == "list_env_vars":
                return manager.list_env_vars()
            elif action == "get_env_var":
                return manager.get_env_var(env_var or "")
            elif action == "clean_temp_files":
                return manager.clean_temp_files()
            elif action == "clean_package_cache":
                return manager.clean_package_cache()
            elif action == "list_windows_features":
                return (
                    manager.list_windows_features()
                    if isinstance(manager, WindowsManager)
                    else "Not supported"
                )
            elif action == "enable_windows_features":
                return (
                    manager.enable_windows_features(
                        [feature_name] if feature_name else []
                    )
                    if isinstance(manager, WindowsManager)
                    else "Not supported"
                )
            elif action == "disable_windows_features":
                return (
                    manager.disable_windows_features(
                        [feature_name] if feature_name else []
                    )
                    if isinstance(manager, WindowsManager)
                    else "Not supported"
                )
            elif action == "add_repository":
                return manager.add_repository(repository or "")
            elif action == "install_local_package":
                return manager.install_local_package(file_path or "")
        except Exception as e:
            return f"Error: {str(e)}"

    @mcp.tool(description="Operations for managing system services")
    async def sm_service_operations(
        action: Literal[
            "list_services",
            "get_service_status",
            "start_service",
            "stop_service",
            "restart_service",
            "enable_service",
            "disable_service",
        ] = Field(..., description="Action to perform"),
        service_name: str | None = Field(None, description="Name of the service"),
        target_host: str | None = Field(
            None, description="Optional target remote host from inventory"
        ),
        ctx: Context | None = None,
    ) -> Any:
        manager = detect_and_create_manager(host=target_host)
        ctx_log(
            ctx,
            logger,
            "info",
            f"sm_service_operations: {action} {service_name} target_host={target_host}",
        )
        try:
            if action == "list_services":
                return manager.list_services()
            elif action == "get_service_status":
                return manager.get_service_status(service_name or "")
            elif action == "start_service":
                return manager.start_service(service_name or "")
            elif action == "stop_service":
                return manager.stop_service(service_name or "")
            elif action == "restart_service":
                return manager.restart_service(service_name or "")
            elif action == "enable_service":
                return manager.enable_service(service_name or "")
            elif action == "disable_service":
                return manager.disable_service(service_name or "")
        except Exception as e:
            return f"Error: {str(e)}"

    @mcp.tool(description="Operations for managing system processes")
    async def sm_process_operations(
        action: Literal["list_processes", "get_process_info", "kill_process"] = Field(
            ..., description="Action to perform"
        ),
        pid: int | None = Field(None, description="Process ID"),
        name: str | None = Field(None, description="Process name"),
        target_host: str | None = Field(
            None, description="Optional target remote host from inventory"
        ),
        ctx: Context | None = None,
    ) -> Any:
        manager = detect_and_create_manager(host=target_host)
        ctx_log(
            ctx,
            logger,
            "info",
            f"sm_process_operations: {action} pid={pid} name={name} target_host={target_host}",
        )
        try:
            if action == "list_processes":
                return manager.list_processes()
            elif action == "get_process_info":
                if pid is not None:
                    return manager.get_process_info(pid)
                return "pid is required"
            elif action == "kill_process":
                if pid is not None:
                    return manager.kill_process(pid)
                return "pid is required"
        except Exception as e:
            return f"Error: {str(e)}"

    @mcp.tool(description="Operations for network analysis")
    async def sm_network_operations(
        action: Literal[
            "list_network_interfaces", "list_open_ports", "ping_host", "dns_lookup"
        ] = Field(..., description="Action to perform"),
        host: str | None = Field(None, description="Host to ping or lookup"),
        count: int = Field(4, description="Ping count"),
        target_host: str | None = Field(
            None, description="Optional target remote host from inventory"
        ),
        ctx: Context | None = None,
    ) -> Any:
        manager = detect_and_create_manager(host=target_host)
        ctx_log(
            ctx,
            logger,
            "info",
            f"sm_network_operations: {action} target_host={target_host}",
        )
        try:
            if action == "list_network_interfaces":
                return manager.list_network_interfaces()
            elif action == "list_open_ports":
                return manager.list_open_ports()
            elif action == "ping_host":
                return manager.ping_host(host or "", count)
            elif action == "dns_lookup":
                return manager.dns_lookup(host or "")
        except Exception as e:
            return f"Error: {str(e)}"

    @mcp.tool(description="Operations for managing system disks")
    async def sm_disk_operations(
        action: Literal[
            "list_disks", "get_disk_usage", "get_disk_space_report"
        ] = Field(..., description="Action to perform"),
        path: str | None = Field(None, description="Path for disk usage"),
        target_host: str | None = Field(
            None, description="Optional target remote host from inventory"
        ),
        ctx: Context | None = None,
    ) -> Any:
        manager = detect_and_create_manager(host=target_host)
        ctx_log(
            ctx,
            logger,
            "info",
            f"sm_disk_operations: {action} target_host={target_host}",
        )
        try:
            if action == "list_disks":
                return manager.list_disks()
            elif action == "get_disk_usage":
                return manager.get_disk_usage(path or "/")
            elif action == "get_disk_space_report":
                return manager.get_disk_space_report()
        except Exception as e:
            return f"Error: {str(e)}"

    @mcp.tool(description="Operations for user and group management")
    async def sm_user_operations(
        action: Literal["list_users", "list_groups"] = Field(
            ..., description="Action to perform"
        ),
        target_host: str | None = Field(
            None, description="Optional target remote host from inventory"
        ),
        ctx: Context | None = None,
    ) -> Any:
        manager = detect_and_create_manager(host=target_host)
        ctx_log(
            ctx,
            logger,
            "info",
            f"sm_user_operations: {action} target_host={target_host}",
        )
        try:
            if action == "list_users":
                return manager.list_users()
            elif action == "list_groups":
                return manager.list_groups()
        except Exception as e:
            return f"Error: {str(e)}"

    @mcp.tool(description="Operations for file and log management")
    async def sm_file_operations(
        action: Literal[
            "run_command",
            "get_system_logs",
            "tail_log_file",
            "list_files",
            "search_files",
            "grep_files",
            "manage_file",
        ] = Field(..., description="Action to perform"),
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
        manager = detect_and_create_manager(host=target_host)
        ctx_log(
            ctx,
            logger,
            "info",
            f"sm_file_operations: {action} target_host={target_host}",
        )
        try:
            if action == "run_command":
                return manager.run_command(command or "")
            elif action == "get_system_logs":
                return manager.get_system_logs(lines=lines)
            elif action == "tail_log_file":
                return manager.tail_log_file(filepath or "", lines)
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
        action: Literal["list_cron_jobs", "add_cron_job", "remove_cron_job"] = Field(
            ..., description="Action to perform"
        ),
        command: str | None = Field(None, description="Command for cron job"),
        schedule: str | None = Field(None, description="Cron schedule expression"),
        user: str | None = Field(None, description="User for cron job"),
        target_host: str | None = Field(
            None, description="Optional target remote host from inventory"
        ),
        ctx: Context | None = None,
    ) -> Any:
        manager = detect_and_create_manager(host=target_host)
        ctx_log(
            ctx,
            logger,
            "info",
            f"sm_cron_operations: {action} target_host={target_host}",
        )
        try:
            if action == "list_cron_jobs":
                return manager.list_cron_jobs(user)
            elif action == "add_cron_job":
                return manager.add_cron_job(command or "", schedule or "", user)
            elif action == "remove_cron_job":
                return manager.remove_cron_job(command or "", user)
        except Exception as e:
            return f"Error: {str(e)}"

    @mcp.tool(description="Operations for firewall management")
    async def sm_firewall_operations(
        action: Literal[
            "get_firewall_status", "add_firewall_rule", "remove_firewall_rule"
        ] = Field(..., description="Action to perform"),
        rule: str | None = Field(
            None, description="Firewall rule (e.g. 'allow 80/tcp')"
        ),
        target_host: str | None = Field(
            None, description="Optional target remote host from inventory"
        ),
        ctx: Context | None = None,
    ) -> Any:
        manager = detect_and_create_manager(host=target_host)
        ctx_log(
            ctx,
            logger,
            "info",
            f"sm_firewall_operations: {action} target_host={target_host}",
        )
        try:
            if action == "get_firewall_status":
                return manager.get_firewall_status()
            elif action == "add_firewall_rule":
                return manager.add_firewall_rule(rule or "")
            elif action == "remove_firewall_rule":
                return manager.remove_firewall_rule(rule or "")
        except Exception as e:
            return f"Error: {str(e)}"

    @mcp.tool(description="Operations for SSH and specialized managers")
    async def sm_advanced_operations(
        action: Literal[
            "add_authorized_key",
            "add_alias",
            "install_uv",
            "create_venv",
            "install_package",
            "install_nvm",
            "install_node",
            "use_node",
        ] = Field(..., description="Action to perform"),
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
        manager = detect_and_create_manager(host=target_host)
        ctx_log(
            ctx,
            logger,
            "info",
            f"sm_advanced_operations: {action} target_host={target_host}",
        )
        try:
            if action == "add_authorized_key":
                return manager.add_authorized_key(public_key or "")
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
