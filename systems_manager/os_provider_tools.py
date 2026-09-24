from agent_connector_sdk.mcp.context import ctx_confirm_destructive, ctx_log
from fastmcp import Context, FastMCP
from fastmcp.utilities.logging import get_logger
from pydantic import Field

from systems_manager.os_provider import get_os_provider

logger = get_logger("OSProviderTools")


def register_os_provider_tools(mcp: FastMCP):
    """
    Registers the OSProvider tools onto the MCP server.

    CONCEPT:SM-OS.deployment.abstracted-os-provider: Abstracted OS Provider
    """

    @mcp.tool(
        annotations={
            "title": "Get Process Details",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
        tags={"system", "observability"},
    )
    async def get_process_details(
        pid: int | None = Field(
            default=None,
            description="Optional PID to get details for. If empty, lists all processes.",
        ),
        ctx: Context | None = Field(description="MCP context", default=None),
    ) -> dict:
        """
        Retrieves deep cross-platform process details (threads, modules, memory).

        CONCEPT:SM-OS.deployment.deep-introspection-telemetry: Deep Introspection Telemetry
        """
        await ctx_log(ctx, f"Fetching process details for PID: {pid}", logger=logger, level="debug")
        try:
            provider = get_os_provider()
            processes = provider.get_process_details(pid)
            return {"success": True, "processes": processes}
        except Exception:
            await ctx_log(ctx, "Process discovery failed", logger=logger, level="error")
            return {"success": False, "error": "Operation failed"}

    @mcp.tool(
        annotations={
            "title": "Get Network Connections",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
        tags={"system", "observability", "network"},
    )
    async def get_network_connections(
        ctx: Context | None = Field(description="MCP context", default=None),
    ) -> dict:
        """
        Maps active TCP/UDP endpoints directly to owning processes.

        CONCEPT:SM-OS.deployment.deep-introspection-telemetry: Deep Introspection Telemetry
        """
        await ctx_log(ctx, "Fetching network connections", logger=logger, level="debug")
        try:
            provider = get_os_provider()
            connections = provider.get_network_connections()
            return {"success": True, "connections": connections}
        except Exception:
            await ctx_log(ctx, "Network discovery failed", logger=logger, level="error")
            return {"success": False, "error": "Operation failed"}

    @mcp.tool(
        annotations={
            "title": "Capture System Snapshot",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
        tags={"system", "observability"},
    )
    async def capture_system_snapshot(
        ctx: Context | None = Field(description="MCP context", default=None),
    ) -> dict:
        """
        Takes a point-in-time snapshot of the system state (CPU, RAM, Processes).

        CONCEPT:SM-OS.deployment.deep-introspection-telemetry: Deep Introspection Telemetry
        """
        await ctx_log(ctx, "Capturing system snapshot", logger=logger, level="debug")
        try:
            provider = get_os_provider()
            snapshot = provider.capture_system_snapshot()
            return {"success": True, "snapshot": snapshot}
        except Exception:
            await ctx_log(ctx, "Snapshot capture failed", logger=logger, level="error")
            return {"success": False, "error": "Operation failed"}

    @mcp.tool(
        annotations={
            "title": "List Services",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
        tags={"system", "services"},
    )
    async def list_services(
        ctx: Context | None = Field(description="MCP context", default=None),
    ) -> dict:
        """
        Cross-platform service enumeration (systemctl or Get-Service).

        CONCEPT:SM-OS.deployment.package-service-mutation: Package & Service Mutation
        """
        await ctx_log(ctx, "Listing services", logger=logger, level="debug")
        try:
            provider = get_os_provider()
            services = provider.list_services()
            return {"success": True, "services": services}
        except Exception:
            await ctx_log(ctx, "Service discovery failed", logger=logger, level="error")
            return {"success": False, "error": "Operation failed"}

    @mcp.tool(
        annotations={
            "title": "Manage Service",
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": True,
            "openWorldHint": False,
        },
        tags={"system", "services"},
    )
    async def manage_service(
        service_name: str = Field(description="Name of the service"),
        action: str = Field(
            description="Action to perform: start, stop, restart, enable, disable"
        ),
        ctx: Context | None = Field(description="MCP context", default=None),
    ) -> dict:
        """
        Start/Stop/Restart/Enable/Disable services cross-platform.

        CONCEPT:SM-OS.deployment.package-service-mutation: Package & Service Mutation
        """
        await ctx_log(ctx, f"Managing service: {service_name} ({action})", logger=logger, level="debug")

        if not await ctx_confirm_destructive(
            ctx, f"{action.upper()} the service: {service_name}"
        ):
            return {"success": False, "error": "Operation cancelled by user."}

        try:
            provider = get_os_provider()
            result = provider.manage_service(service_name, action)
            return {"success": True, "result": result}
        except Exception:
            await ctx_log(ctx, "Service operation failed", logger=logger, level="error")
            return {"success": False, "error": "Operation failed"}

    @mcp.tool(
        annotations={
            "title": "List Kernel Modules",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
        tags={"system", "drivers"},
    )
    async def list_kernel_modules(
        ctx: Context | None = Field(description="MCP context", default=None),
    ) -> dict:
        """
        List loaded drivers/modules (lsmod or driverquery).

        CONCEPT:SM-OS.deployment.deep-introspection-telemetry: Deep Introspection Telemetry
        """
        await ctx_log(ctx, "Listing kernel modules", logger=logger, level="debug")
        try:
            provider = get_os_provider()
            modules = provider.list_kernel_modules()
            return {"success": True, "modules": modules}
        except Exception:
            await ctx_log(ctx, "Kernel module discovery failed", logger=logger, level="error")
            return {"success": False, "error": "Operation failed"}

    @mcp.tool(
        annotations={
            "title": "Query System Logs",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
        tags={"system", "logs"},
    )
    async def query_system_logs(
        limit: int = Field(default=50, description="Max number of events to fetch"),
        ctx: Context | None = Field(description="MCP context", default=None),
    ) -> dict:
        """
        Cross-platform log querying (journalctl or Get-WinEvent).

        CONCEPT:SM-OS.deployment.deep-introspection-telemetry: Deep Introspection Telemetry
        """
        await ctx_log(ctx, f"Querying system logs (limit: {limit})", logger=logger, level="debug")
        try:
            provider = get_os_provider()
            logs = provider.query_system_logs(limit)
            return {"success": True, "logs": logs}
        except Exception:
            await ctx_log(ctx, "System log query failed", logger=logger, level="error")
            return {"success": False, "error": "Operation failed"}

    @mcp.tool(
        annotations={
            "title": "Start System Trace",
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": True,
            "openWorldHint": False,
        },
        tags={"system", "tracing"},
    )
    async def start_system_trace(
        session_name: str = Field(description="Name of the trace session"),
        ctx: Context | None = Field(description="MCP context", default=None),
    ) -> dict:
        """Start a kernel-level event trace (ETW on Windows, or strace on Linux)."""
        await ctx_log(ctx, f"Starting system trace: {session_name}", logger=logger, level="debug")

        if not await ctx_confirm_destructive(
            ctx, f"START tracing session: {session_name}"
        ):
            return {"success": False, "error": "Operation cancelled by user."}

        try:
            provider = get_os_provider()
            result = provider.start_system_trace(session_name)
            return {"success": True, "result": result}
        except Exception:
            await ctx_log(ctx, "Trace start failed", logger=logger, level="error")
            return {"success": False, "error": "Operation failed"}

    @mcp.tool(
        annotations={
            "title": "Stop System Trace",
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": True,
            "openWorldHint": False,
        },
        tags={"system", "tracing"},
    )
    async def stop_system_trace(
        session_name: str = Field(description="Name of the trace session"),
        ctx: Context | None = Field(description="MCP context", default=None),
    ) -> dict:
        """Stop a kernel-level event trace."""
        await ctx_log(ctx, f"Stopping system trace: {session_name}", logger=logger, level="debug")
        if not await ctx_confirm_destructive(
            ctx, f"STOP tracing session: {session_name}"
        ):
            return {"success": False, "error": "Operation approval is required"}
        try:
            provider = get_os_provider()
            result = provider.stop_system_trace(session_name)
            return {"success": True, "result": result}
        except Exception:
            await ctx_log(ctx, "Trace stop failed", logger=logger, level="error")
            return {"success": False, "error": "Operation failed"}
