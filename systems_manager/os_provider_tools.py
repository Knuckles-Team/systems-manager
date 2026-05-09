from agent_utilities.mcp_utilities import ctx_log
from fastmcp import Context, FastMCP
from fastmcp.utilities.logging import get_logger
from pydantic import Field

from systems_manager.os_provider import get_os_provider

logger = get_logger("OSProviderTools")


def register_os_provider_tools(mcp: FastMCP):
    """
    Registers the OSProvider tools onto the MCP server.

    CONCEPT:SYS-1.0: Abstracted OS Provider
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
        ctx: Context = Field(description="MCP context", default=None),
    ) -> dict:
        """
        Retrieves deep cross-platform process details (threads, modules, memory).

        CONCEPT:SYS-1.2: Deep Introspection Telemetry
        """
        ctx_log(ctx, logger, "debug", f"Fetching process details for PID: {pid}")
        try:
            provider = get_os_provider()
            processes = provider.get_process_details(pid)
            return {"success": True, "processes": processes}
        except Exception as e:
            ctx_log(ctx, logger, "error", f"Error fetching processes: {str(e)}")
            return {"success": False, "error": str(e)}

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
        ctx: Context = Field(description="MCP context", default=None),
    ) -> dict:
        """
        Maps active TCP/UDP endpoints directly to owning processes.

        CONCEPT:SYS-1.2: Deep Introspection Telemetry
        """
        ctx_log(ctx, logger, "debug", "Fetching network connections")
        try:
            provider = get_os_provider()
            connections = provider.get_network_connections()
            return {"success": True, "connections": connections}
        except Exception as e:
            ctx_log(
                ctx, logger, "error", f"Error fetching network connections: {str(e)}"
            )
            return {"success": False, "error": str(e)}

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
        ctx: Context = Field(description="MCP context", default=None),
    ) -> dict:
        """
        Takes a point-in-time snapshot of the system state (CPU, RAM, Processes).

        CONCEPT:SYS-1.2: Deep Introspection Telemetry
        """
        ctx_log(ctx, logger, "debug", "Capturing system snapshot")
        try:
            provider = get_os_provider()
            snapshot = provider.capture_system_snapshot()
            return {"success": True, "snapshot": snapshot}
        except Exception as e:
            ctx_log(ctx, logger, "error", f"Error capturing snapshot: {str(e)}")
            return {"success": False, "error": str(e)}

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
        ctx: Context = Field(description="MCP context", default=None),
    ) -> dict:
        """
        Cross-platform service enumeration (systemctl or Get-Service).

        CONCEPT:SYS-1.3: Package & Service Mutation
        """
        ctx_log(ctx, logger, "debug", "Listing services")
        try:
            provider = get_os_provider()
            services = provider.list_services()
            return {"success": True, "services": services}
        except Exception as e:
            ctx_log(ctx, logger, "error", f"Error listing services: {str(e)}")
            return {"success": False, "error": str(e)}

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
        ctx: Context = Field(description="MCP context", default=None),
    ) -> dict:
        """
        Start/Stop/Restart/Enable/Disable services cross-platform.

        CONCEPT:SYS-1.3: Package & Service Mutation
        """
        ctx_log(ctx, logger, "debug", f"Managing service: {service_name} ({action})")

        if ctx:
            message = f"Are you sure you want to {action.upper()} the service: {service_name}?"
            result = await ctx.elicit(message, response_type=bool)
            if result.action != "accept" or not result.data:
                return {"success": False, "error": "Operation cancelled by user."}

        try:
            provider = get_os_provider()
            result = provider.manage_service(service_name, action)
            return {"success": True, "result": result}
        except Exception as e:
            ctx_log(ctx, logger, "error", f"Error managing service: {str(e)}")
            return {"success": False, "error": str(e)}

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
        ctx: Context = Field(description="MCP context", default=None),
    ) -> dict:
        """
        List loaded drivers/modules (lsmod or driverquery).

        CONCEPT:SYS-1.2: Deep Introspection Telemetry
        """
        ctx_log(ctx, logger, "debug", "Listing kernel modules")
        try:
            provider = get_os_provider()
            modules = provider.list_kernel_modules()
            return {"success": True, "modules": modules}
        except Exception as e:
            ctx_log(ctx, logger, "error", f"Error listing kernel modules: {str(e)}")
            return {"success": False, "error": str(e)}

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
        ctx: Context = Field(description="MCP context", default=None),
    ) -> dict:
        """
        Cross-platform log querying (journalctl or Get-WinEvent).

        CONCEPT:SYS-1.2: Deep Introspection Telemetry
        """
        ctx_log(ctx, logger, "debug", f"Querying system logs (limit: {limit})")
        try:
            provider = get_os_provider()
            logs = provider.query_system_logs(limit)
            return {"success": True, "logs": logs}
        except Exception as e:
            ctx_log(ctx, logger, "error", f"Error querying system logs: {str(e)}")
            return {"success": False, "error": str(e)}

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
        ctx: Context = Field(description="MCP context", default=None),
    ) -> dict:
        """Start a kernel-level event trace (ETW on Windows, or strace on Linux)."""
        ctx_log(ctx, logger, "debug", f"Starting system trace: {session_name}")

        if ctx:
            message = f"Are you sure you want to START tracing session: {session_name}?"
            result = await ctx.elicit(message, response_type=bool)
            if result.action != "accept" or not result.data:
                return {"success": False, "error": "Operation cancelled by user."}

        try:
            provider = get_os_provider()
            result = provider.start_system_trace(session_name)
            return {"success": True, "result": result}
        except Exception as e:
            ctx_log(ctx, logger, "error", f"Error starting system trace: {str(e)}")
            return {"success": False, "error": str(e)}

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
        ctx: Context = Field(description="MCP context", default=None),
    ) -> dict:
        """Stop a kernel-level event trace."""
        ctx_log(ctx, logger, "debug", f"Stopping system trace: {session_name}")
        try:
            provider = get_os_provider()
            result = provider.stop_system_trace(session_name)
            return {"success": True, "result": result}
        except Exception as e:
            ctx_log(ctx, logger, "error", f"Error stopping system trace: {str(e)}")
            return {"success": False, "error": str(e)}
