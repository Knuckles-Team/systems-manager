#!/usr/bin/env python


from dotenv import load_dotenv, find_dotenv
import os
import sys
import logging
import requests
from typing import Optional, Dict, List, Any
from pydantic import Field
from starlette.requests import Request
from starlette.responses import JSONResponse
from fastmcp import FastMCP, Context

from fastmcp.utilities.logging import get_logger
from agent_utilities.base_utilities import to_boolean
from agent_utilities.mcp_utilities import (
    create_mcp_server,
)
from systems_manager.systems_manager import (
    detect_and_create_manager,
    WindowsManager,
)

__version__ = "1.2.49"

logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = get_logger("SystemsManagerServer")


def register_misc_tools(mcp: FastMCP):
    async def health_check(request: Request) -> JSONResponse:
        return JSONResponse({"status": "OK"})


def register_system_tools(mcp: FastMCP):
    @mcp.tool(
        annotations={
            "title": "Install Applications",
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": True,
            "openWorldHint": False,
        },
        tags={"system"},
    )
    async def install_applications(
        apps: List[str] = Field(
            description="List of application names to install", default=None
        ),
        silent: Optional[bool] = Field(
            description="Suppress output",
            default=to_boolean(os.environ.get("SYSTEMS_MANAGER_SILENT", False)),
        ),
        log_file: Optional[str] = Field(
            description="Path to log file",
            default=os.environ.get("SYSTEMS_MANAGER_LOG_FILE", None),
        ),
        ctx: Context = Field(
            description="MCP context for progress reporting", default=None
        ),
    ) -> Dict:
        """Installs applications using the native package manager with Snap fallback."""
        logger = logging.getLogger("SystemsManager")
        logger.debug(f"Installing apps: {apps}, silent: {silent}, log_file: {log_file}")

        if not apps:
            return {"success": False, "error": "No applications provided"}

        if ctx:
            message = f"Are you sure you want to INSTALL the following applications: {', '.join(apps)}?"
            result = await ctx.elicit(message, response_type=bool)
            if result.action != "accept" or not result.data:
                return {"success": False, "error": "Operation cancelled by user."}

        try:
            manager = detect_and_create_manager(silent, log_file)
            total_steps = len(apps)
            current_step = 0

            if ctx:
                await ctx.report_progress(progress=0, total=total_steps)

            result = manager.install_applications(apps)
            current_step = total_steps

            if ctx:
                await ctx.report_progress(progress=current_step, total=total_steps)

            logger.debug(f"Completed installing apps: {apps}, result: {result}")
            return result
        except Exception as e:
            logger.error(f"Failed to install applications: {str(e)}")
            return {"success": False, "error": f"Unexpected error: {str(e)}"}

    @mcp.tool(
        annotations={
            "title": "Update System",
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": True,
            "openWorldHint": False,
        },
        tags={"system"},
    )
    async def update(
        silent: Optional[bool] = Field(
            description="Suppress output",
            default=to_boolean(os.environ.get("SYSTEMS_MANAGER_SILENT", False)),
        ),
        log_file: Optional[str] = Field(
            description="Path to log file",
            default=os.environ.get("SYSTEMS_MANAGER_LOG_FILE", None),
        ),
        ctx: Context = Field(
            description="MCP context for progress reporting", default=None
        ),
    ) -> Dict:
        """Updates the system and applications."""
        logger = logging.getLogger("SystemsManager")
        logger.debug(f"Updating system, silent: {silent}, log_file: {log_file}")

        if ctx:
            message = "Are you sure you want to UPDATE the system?"
            result = await ctx.elicit(message, response_type=bool)
            if result.action != "accept" or not result.data:
                return {"success": False, "error": "Operation cancelled by user."}

        try:
            manager = detect_and_create_manager(silent, log_file)
            if ctx:
                await ctx.report_progress(progress=0, total=100)

            result = manager.update()

            if ctx:
                await ctx.report_progress(progress=100, total=100)

            logger.debug("System update completed")
            return result
        except Exception as e:
            logger.error(f"Failed to update system: {str(e)}")
            return {"success": False, "error": f"Unexpected error: {str(e)}"}

    @mcp.tool(
        annotations={
            "title": "Clean System",
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": True,
            "openWorldHint": False,
        },
        tags={"system"},
    )
    async def clean(
        silent: Optional[bool] = Field(
            description="Suppress output",
            default=to_boolean(os.environ.get("SYSTEMS_MANAGER_SILENT", False)),
        ),
        log_file: Optional[str] = Field(
            description="Path to log file",
            default=os.environ.get("SYSTEMS_MANAGER_LOG_FILE", None),
        ),
        ctx: Context = Field(
            description="MCP context for progress reporting", default=None
        ),
    ) -> Dict:
        """Cleans system resources (e.g., trash/recycle bin)."""
        logger = logging.getLogger("SystemsManager")
        logger.debug(f"Cleaning system, silent: {silent}, log_file: {log_file}")

        if ctx:
            message = "Are you sure you want to CLEAN system resources?"
            result = await ctx.elicit(message, response_type=bool)
            if result.action != "accept" or not result.data:
                return {"success": False, "error": "Operation cancelled by user."}

        try:
            manager = detect_and_create_manager(silent, log_file)
            if ctx:
                await ctx.report_progress(progress=0, total=100)

            result = manager.clean()

            if ctx:
                await ctx.report_progress(progress=100, total=100)

            logger.debug("System cleanup completed")
            return result
        except Exception as e:
            logger.error(f"Failed to clean system: {str(e)}")
            return {"success": False, "error": f"Unexpected error: {str(e)}"}

    @mcp.tool(
        annotations={
            "title": "Optimize System",
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": True,
            "openWorldHint": False,
        },
        tags={"system"},
    )
    async def optimize(
        silent: Optional[bool] = Field(
            description="Suppress output",
            default=to_boolean(os.environ.get("SYSTEMS_MANAGER_SILENT", False)),
        ),
        log_file: Optional[str] = Field(
            description="Path to log file",
            default=os.environ.get("SYSTEMS_MANAGER_LOG_FILE", None),
        ),
        ctx: Context = Field(
            description="MCP context for progress reporting", default=None
        ),
    ) -> Dict:
        """Optimizes system resources (e.g., autoremove, defrag)."""
        logger = logging.getLogger("SystemsManager")
        logger.debug(f"Optimizing system, silent: {silent}, log_file: {log_file}")

        if ctx:
            message = "Are you sure you want to OPTIMIZE system resources?"
            result = await ctx.elicit(message, response_type=bool)
            if result.action != "accept" or not result.data:
                return {"success": False, "error": "Operation cancelled by user."}

        try:
            manager = detect_and_create_manager(silent, log_file)
            if ctx:
                await ctx.report_progress(progress=0, total=100)

            result = manager.optimize()

            if ctx:
                await ctx.report_progress(progress=100, total=100)

            logger.debug("System optimization completed")
            return result
        except Exception as e:
            logger.error(f"Failed to optimize system: {str(e)}")
            return {"success": False, "error": f"Unexpected error: {str(e)}"}

    @mcp.tool(
        annotations={
            "title": "Install Python Modules",
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": True,
            "openWorldHint": False,
        },
        tags={"system"},
    )
    async def install_python_modules(
        modules: List[str] = Field(
            description="List of Python modules to install", default=None
        ),
        silent: Optional[bool] = Field(
            description="Suppress output",
            default=to_boolean(os.environ.get("SYSTEMS_MANAGER_SILENT", False)),
        ),
        log_file: Optional[str] = Field(
            description="Path to log file",
            default=os.environ.get("SYSTEMS_MANAGER_LOG_FILE", None),
        ),
        ctx: Context = Field(
            description="MCP context for progress reporting", default=None
        ),
    ) -> Dict:
        """Installs Python modules via pip."""
        logger = logging.getLogger("SystemsManager")
        logger.debug(
            f"Installing Python modules: {modules}, silent: {silent}, log_file: {log_file}"
        )
        if not modules:
            return {"success": False, "error": "No Python modules provided"}

        if ctx:
            message = f"Are you sure you want to INSTALL Python modules: {', '.join(modules)}?"
            result = await ctx.elicit(message, response_type=bool)
            if result.action != "accept" or not result.data:
                return {"success": False, "error": "Operation cancelled by user."}

        try:
            manager = detect_and_create_manager(silent, log_file)
            total_steps = len(modules) + 1
            current_step = 0

            if ctx:
                await ctx.report_progress(progress=0, total=total_steps)

            result = manager.install_python_modules(modules)
            current_step = total_steps

            if ctx:
                await ctx.report_progress(progress=current_step, total=total_steps)

            logger.debug(f"Completed installing Python modules: {modules}")
            return result
        except Exception as e:
            logger.error(f"Failed to install Python modules: {str(e)}")
            return {"success": False, "error": f"Unexpected error: {str(e)}"}

    @mcp.tool(
        annotations={
            "title": "Install Nerd Fonts",
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": True,
            "openWorldHint": False,
        },
        tags={"system"},
    )
    async def install_fonts(
        fonts: Optional[List[str]] = Field(
            description="List of font names to install (e.g., Hack, Meslo) or 'all' for all fonts",
            default=None,
        ),
        silent: Optional[bool] = Field(
            description="Suppress output",
            default=to_boolean(os.environ.get("SYSTEMS_MANAGER_SILENT", False)),
        ),
        log_file: Optional[str] = Field(
            description="Path to log file",
            default=os.environ.get("SYSTEMS_MANAGER_LOG_FILE", None),
        ),
        ctx: Context = Field(
            description="MCP context for progress reporting", default=None
        ),
    ) -> Dict:
        """Installs specified Nerd Fonts or all available fonts if 'all' is specified."""
        logger = logging.getLogger("SystemsManager")
        logger.debug(
            f"Installing fonts: {fonts}, silent: {silent}, log_file: {log_file}"
        )

        if not fonts:
            fonts = ["Hack"]

        if ctx:
            message = f"Are you sure you want to INSTALL fonts: {', '.join(fonts)}?"
            result = await ctx.elicit(message, response_type=bool)
            if result.action != "accept" or not result.data:
                return {"success": False, "error": "Operation cancelled by user."}

        try:
            manager = detect_and_create_manager(silent, log_file)

            api_url = (
                "https://api.github.com/repos/ryanoasis/nerd-fonts/releases/latest"
            )
            response = requests.get(api_url).json()
            all_assets = [
                a
                for a in response["assets"]
                if a["name"].endswith(".zip") and "FontPatcher" not in a["name"]
            ]
            total_steps = (
                len(all_assets)
                if any(f.lower() == "all" for f in fonts)
                else len(
                    [
                        a
                        for a in all_assets
                        if any(f.lower() in a["name"].lower() for f in fonts)
                    ]
                )
            ) or 1

            if ctx:
                await ctx.report_progress(progress=0, total=total_steps)

            result = manager.font(fonts)

            if ctx:
                await ctx.report_progress(progress=total_steps, total=total_steps)

            logger.debug(f"Font installation completed: {fonts}")
            return result
        except Exception as e:
            logger.error(f"Failed to install fonts: {str(e)}")
            return {"success": False, "error": f"Unexpected error: {str(e)}"}

    @mcp.tool(
        annotations={
            "title": "Get OS Statistics",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
        tags={"system"},
    )
    async def get_os_statistics(
        silent: Optional[bool] = Field(
            description="Suppress output",
            default=to_boolean(os.environ.get("SYSTEMS_MANAGER_SILENT", False)),
        ),
        log_file: Optional[str] = Field(
            description="Path to log file",
            default=os.environ.get("SYSTEMS_MANAGER_LOG_FILE", None),
        ),
        ctx: Context = Field(
            description="MCP context for progress reporting", default=None
        ),
    ) -> Dict:
        """Retrieves operating system statistics."""
        logger = logging.getLogger("SystemsManager")
        logger.debug(f"Fetching OS stats, silent: {silent}, log_file: {log_file}")

        try:
            manager = detect_and_create_manager(silent, log_file)
            stats = manager.get_os_statistics()
            if not stats.get("success", True):
                logger.error(
                    f"Failed to get OS stats. Error: {stats.get('error', 'Unknown error')}"
                )
            else:
                logger.debug("OS stats retrieved successfully.")
            return stats
        except Exception as e:
            logger.error(f"Exception while getting OS stats: {str(e)}")
            return {"success": False, "error": f"Unexpected error: {str(e)}"}

    @mcp.tool(
        annotations={
            "title": "Get Hardware Statistics",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
        tags={"system"},
    )
    async def get_hardware_statistics(
        silent: Optional[bool] = Field(
            description="Suppress output",
            default=to_boolean(os.environ.get("SYSTEMS_MANAGER_SILENT", False)),
        ),
        log_file: Optional[str] = Field(
            description="Path to log file",
            default=os.environ.get("SYSTEMS_MANAGER_LOG_FILE", None),
        ),
        ctx: Context = Field(
            description="MCP context for progress reporting", default=None
        ),
    ) -> Dict:
        """Retrieves hardware statistics."""
        logger = logging.getLogger("SystemsManager")
        logger.debug(f"Fetching hardware stats, silent: {silent}, log_file: {log_file}")

        try:
            manager = detect_and_create_manager(silent, log_file)
            stats = manager.get_hardware_statistics()
            if not stats.get("success", True):
                logger.error(
                    f"Failed to get hardware stats. Error: {stats.get('error', 'Unknown error')}"
                )
            else:
                logger.debug("Hardware stats retrieved successfully.")
            return stats
        except Exception as e:
            logger.error(f"Exception while getting hardware stats: {str(e)}")
            return {"success": False, "error": f"Unexpected error: {str(e)}"}

    @mcp.tool(
        annotations={
            "title": "Search Package",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
        tags={"system"},
    )
    async def search_package(
        query: str = Field(description="Search query for packages"),
        silent: Optional[bool] = Field(
            description="Suppress output",
            default=to_boolean(os.environ.get("SYSTEMS_MANAGER_SILENT", False)),
        ),
        log_file: Optional[str] = Field(
            description="Path to log file",
            default=os.environ.get("SYSTEMS_MANAGER_LOG_FILE", None),
        ),
        ctx: Context = Field(
            description="MCP context for progress reporting", default=None
        ),
    ) -> Dict:
        """Searches for packages in the system package manager repositories."""
        try:
            manager = detect_and_create_manager(silent, log_file)
            return manager.search_package(query)
        except Exception as e:
            return {"success": False, "error": str(e)}

    @mcp.tool(
        annotations={
            "title": "Get Package Info",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
        tags={"system"},
    )
    async def get_package_info(
        package: str = Field(description="Package name to get info about"),
        silent: Optional[bool] = Field(
            description="Suppress output",
            default=to_boolean(os.environ.get("SYSTEMS_MANAGER_SILENT", False)),
        ),
        log_file: Optional[str] = Field(
            description="Path to log file",
            default=os.environ.get("SYSTEMS_MANAGER_LOG_FILE", None),
        ),
        ctx: Context = Field(
            description="MCP context for progress reporting", default=None
        ),
    ) -> Dict:
        """Gets detailed information about a specific package."""
        try:
            manager = detect_and_create_manager(silent, log_file)
            return manager.get_package_info(package)
        except Exception as e:
            return {"success": False, "error": str(e)}

    @mcp.tool(
        annotations={
            "title": "List Installed Packages",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
        tags={"system"},
    )
    async def list_installed_packages(
        silent: Optional[bool] = Field(
            description="Suppress output",
            default=to_boolean(os.environ.get("SYSTEMS_MANAGER_SILENT", False)),
        ),
        log_file: Optional[str] = Field(
            description="Path to log file",
            default=os.environ.get("SYSTEMS_MANAGER_LOG_FILE", None),
        ),
        ctx: Context = Field(
            description="MCP context for progress reporting", default=None
        ),
    ) -> Dict:
        """Lists all installed packages on the system."""
        try:
            manager = detect_and_create_manager(silent, log_file)
            return manager.list_installed_packages()
        except Exception as e:
            return {"success": False, "error": str(e)}

    @mcp.tool(
        annotations={
            "title": "List Upgradable Packages",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
        tags={"system"},
    )
    async def list_upgradable_packages(
        silent: Optional[bool] = Field(
            description="Suppress output",
            default=to_boolean(os.environ.get("SYSTEMS_MANAGER_SILENT", False)),
        ),
        log_file: Optional[str] = Field(
            description="Path to log file",
            default=os.environ.get("SYSTEMS_MANAGER_LOG_FILE", None),
        ),
        ctx: Context = Field(
            description="MCP context for progress reporting", default=None
        ),
    ) -> Dict:
        """Lists all packages that have updates available."""
        try:
            manager = detect_and_create_manager(silent, log_file)
            return manager.list_upgradable_packages()
        except Exception as e:
            return {"success": False, "error": str(e)}

    @mcp.tool(
        annotations={
            "title": "System Health Check",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
        tags={"system"},
    )
    async def system_health_check(
        silent: Optional[bool] = Field(
            description="Suppress output",
            default=to_boolean(os.environ.get("SYSTEMS_MANAGER_SILENT", False)),
        ),
        log_file: Optional[str] = Field(
            description="Path to log file",
            default=os.environ.get("SYSTEMS_MANAGER_LOG_FILE", None),
        ),
        ctx: Context = Field(
            description="MCP context for progress reporting", default=None
        ),
    ) -> Dict:
        """Performs a comprehensive system health check including CPU, memory, disk, swap, and top processes."""
        logger = logging.getLogger("SystemsManager")
        logger.debug("Performing system health check")
        try:
            manager = detect_and_create_manager(silent, log_file)
            result = manager.system_health_check()
            if not result.get("success"):
                logger.error(
                    f"System health check failed. Error: {result.get('error', 'Unknown error')}"
                )
            else:
                logger.debug(
                    f"System health check retrieved successfully. Status: {result.get('status', 'unknown')}"
                )
            return result
        except Exception as e:
            logger.error(f"Exception during system health check: {str(e)}")
            return {"success": False, "error": str(e)}

    @mcp.tool(
        annotations={
            "title": "Get Uptime",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
        tags={"system"},
    )
    async def get_uptime(
        silent: Optional[bool] = Field(
            description="Suppress output",
            default=to_boolean(os.environ.get("SYSTEMS_MANAGER_SILENT", False)),
        ),
        log_file: Optional[str] = Field(
            description="Path to log file",
            default=os.environ.get("SYSTEMS_MANAGER_LOG_FILE", None),
        ),
        ctx: Context = Field(
            description="MCP context for progress reporting", default=None
        ),
    ) -> Dict:
        """Gets system uptime and boot time."""
        logger = logging.getLogger("SystemsManager")
        logger.debug("Fetching system uptime")
        try:
            manager = detect_and_create_manager(silent, log_file)
            result = manager.get_uptime()
            if not result.get("success"):
                logger.error(
                    f"Failed to get uptime. Error: {result.get('error', 'Unknown error')}"
                )
            else:
                logger.debug("Successfully retrieved system uptime.")
            return result
        except Exception as e:
            logger.error(f"Exception while getting uptime: {str(e)}")
            return {"success": False, "error": str(e)}

    @mcp.tool(
        annotations={
            "title": "List Environment Variables",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
        tags={"system"},
    )
    async def list_env_vars(
        silent: Optional[bool] = Field(
            description="Suppress output",
            default=to_boolean(os.environ.get("SYSTEMS_MANAGER_SILENT", False)),
        ),
        log_file: Optional[str] = Field(
            description="Path to log file",
            default=os.environ.get("SYSTEMS_MANAGER_LOG_FILE", None),
        ),
        ctx: Context = Field(
            description="MCP context for progress reporting", default=None
        ),
    ) -> Dict:
        """Lists all environment variables on the system."""
        try:
            manager = detect_and_create_manager(silent, log_file)
            return manager.list_env_vars()
        except Exception as e:
            return {"success": False, "error": str(e)}

    @mcp.tool(
        annotations={
            "title": "Get Environment Variable",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
        tags={"system"},
    )
    async def get_env_var(
        name: str = Field(description="Name of the environment variable"),
        silent: Optional[bool] = Field(
            description="Suppress output",
            default=to_boolean(os.environ.get("SYSTEMS_MANAGER_SILENT", False)),
        ),
        log_file: Optional[str] = Field(
            description="Path to log file",
            default=os.environ.get("SYSTEMS_MANAGER_LOG_FILE", None),
        ),
        ctx: Context = Field(
            description="MCP context for progress reporting", default=None
        ),
    ) -> Dict:
        """Gets the value of a specific environment variable."""
        try:
            manager = detect_and_create_manager(silent, log_file)
            return manager.get_env_var(name)
        except Exception as e:
            return {"success": False, "error": str(e)}

    @mcp.tool(
        annotations={
            "title": "Clean Temp Files",
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": False,
            "openWorldHint": False,
        },
        tags={"system"},
    )
    async def clean_temp_files(
        silent: Optional[bool] = Field(
            description="Suppress output",
            default=to_boolean(os.environ.get("SYSTEMS_MANAGER_SILENT", False)),
        ),
        log_file: Optional[str] = Field(
            description="Path to log file",
            default=os.environ.get("SYSTEMS_MANAGER_LOG_FILE", None),
        ),
        ctx: Context = Field(
            description="MCP context for progress reporting", default=None
        ),
    ) -> Dict:
        """Cleans temporary files from system temp directories."""
        try:
            manager = detect_and_create_manager(silent, log_file)
            return manager.clean_temp_files()
        except Exception as e:
            return {"success": False, "error": str(e)}

    @mcp.tool(
        annotations={
            "title": "Clean Package Cache",
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": False,
            "openWorldHint": False,
        },
        tags={"system"},
    )
    async def clean_package_cache(
        silent: Optional[bool] = Field(
            description="Suppress output",
            default=to_boolean(os.environ.get("SYSTEMS_MANAGER_SILENT", False)),
        ),
        log_file: Optional[str] = Field(
            description="Path to log file",
            default=os.environ.get("SYSTEMS_MANAGER_LOG_FILE", None),
        ),
        ctx: Context = Field(
            description="MCP context for progress reporting", default=None
        ),
    ) -> Dict:
        """Cleans the package manager cache to free disk space."""
        try:
            manager = detect_and_create_manager(silent, log_file)
            return manager.clean_package_cache()
        except Exception as e:
            return {"success": False, "error": str(e)}


def register_system_management_tools(mcp: FastMCP):
    @mcp.tool(
        annotations={
            "title": "List Windows Features",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
        tags={"system_management", "windows"},
    )
    async def list_windows_features(
        silent: Optional[bool] = Field(
            description="Suppress output",
            default=to_boolean(os.environ.get("SYSTEMS_MANAGER_SILENT", False)),
        ),
        log_file: Optional[str] = Field(
            description="Path to log file",
            default=os.environ.get("SYSTEMS_MANAGER_LOG_FILE", None),
        ),
        ctx: Context = Field(
            description="MCP context for progress reporting", default=None
        ),
    ) -> List[Dict]:
        """Lists all Windows features and their status (Windows only)."""
        logger = logging.getLogger("SystemsManager")
        logger.debug(
            f"Listing Windows features, silent: {silent}, log_file: {log_file}"
        )

        try:
            manager = detect_and_create_manager(silent, log_file)
            if not isinstance(manager, WindowsManager):
                return [
                    {
                        "success": False,
                        "error": "Feature listing is only available on Windows",
                    }
                ]
            features = manager.list_windows_features()
            logger.debug(f"Windows features: {features}")
            return features
        except Exception as e:
            logger.error(f"Failed to list Windows features: {str(e)}")
            return [{"success": False, "error": f"Unexpected error: {str(e)}"}]

    @mcp.tool(
        annotations={
            "title": "Enable Windows Features",
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": True,
            "openWorldHint": False,
        },
        tags={"system_management", "windows"},
    )
    async def enable_windows_features(
        features: List[str] = Field(
            description="List of Windows features to enable", default=None
        ),
        silent: Optional[bool] = Field(
            description="Suppress output",
            default=to_boolean(os.environ.get("SYSTEMS_MANAGER_SILENT", False)),
        ),
        log_file: Optional[str] = Field(
            description="Path to log file",
            default=os.environ.get("SYSTEMS_MANAGER_LOG_FILE", None),
        ),
        ctx: Context = Field(
            description="MCP context for progress reporting", default=None
        ),
    ) -> Dict:
        """Enables specified Windows features (Windows only)."""
        logger = logging.getLogger("SystemsManager")
        logger.debug(
            f"Enabling Windows features: {features}, silent: {silent}, log_file: {log_file}"
        )

        if not features:
            return {"success": False, "error": "No features provided"}

        try:
            manager = detect_and_create_manager(silent, log_file)
            if not isinstance(manager, WindowsManager):
                return {
                    "success": False,
                    "error": "Feature enabling is only available on Windows",
                }

            total_steps = len(features)
            current_step = 0

            if ctx:
                await ctx.report_progress(progress=0, total=total_steps)

            result = manager.enable_windows_features(features)
            current_step = total_steps

            if ctx:
                await ctx.report_progress(progress=current_step, total=total_steps)

            logger.debug(f"Completed enabling Windows features: {features}")
            return result
        except Exception as e:
            logger.error(f"Failed to enable Windows features: {str(e)}")
            return {"success": False, "error": f"Unexpected error: {str(e)}"}

    @mcp.tool(
        annotations={
            "title": "Disable Windows Features",
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": True,
            "openWorldHint": False,
        },
        tags={"system_management", "windows"},
    )
    async def disable_windows_features(
        features: List[str] = Field(
            description="List of Windows features to disable", default=None
        ),
        silent: Optional[bool] = Field(
            description="Suppress output",
            default=to_boolean(os.environ.get("SYSTEMS_MANAGER_SILENT", False)),
        ),
        log_file: Optional[str] = Field(
            description="Path to log file",
            default=os.environ.get("SYSTEMS_MANAGER_LOG_FILE", None),
        ),
        ctx: Context = Field(
            description="MCP context for progress reporting", default=None
        ),
    ) -> Dict:
        """Disables specified Windows features (Windows only)."""
        logger = logging.getLogger("SystemsManager")
        logger.debug(
            f"Disabling Windows features: {features}, silent: {silent}, log_file: {log_file}"
        )

        if not features:
            return {"success": True, "message": "No Windows features to disable"}

        try:
            manager = detect_and_create_manager(silent, log_file)
            if not isinstance(manager, WindowsManager):
                return {
                    "success": False,
                    "error": "Feature disabling is only available on Windows",
                }

            total_steps = len(features)
            current_step = 0

            if ctx:
                await ctx.report_progress(progress=0, total=total_steps)

            result = manager.disable_windows_features(features)
            current_step = total_steps

            if ctx:
                await ctx.report_progress(progress=current_step, total=total_steps)

            logger.debug(f"Completed disabling Windows features: {features}")
            return result
        except Exception as e:
            logger.error(f"Failed to disable Windows features: {str(e)}")
            return {"success": False, "error": f"Unexpected error: {str(e)}"}

    @mcp.tool(
        annotations={
            "title": "Add Repository",
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": True,
            "openWorldHint": False,
        },
        tags={"system_management", "linux"},
    )
    async def add_repository(
        repo_url: str = Field(description="URL of the repository to add", default=None),
        name: Optional[str] = Field(
            description="Name of the repository (optional, auto-generated if not provided)",
            default=None,
        ),
        silent: Optional[bool] = Field(
            description="Suppress output",
            default=to_boolean(os.environ.get("SYSTEMS_MANAGER_SILENT", False)),
        ),
        log_file: Optional[str] = Field(
            description="Path to log file",
            default=os.environ.get("SYSTEMS_MANAGER_LOG_FILE", None),
        ),
        ctx: Context = Field(
            description="MCP context for progress reporting", default=None
        ),
    ) -> Dict:
        """Adds an upstream repository to the package manager repository list (Linux only)."""
        logger = logging.getLogger("SystemsManager")
        logger.debug(
            f"Adding repository: {repo_url}, name: {name}, silent: {silent}, log_file: {log_file}"
        )

        if not repo_url:
            return {"success": False, "error": "No repository URL provided"}

        try:
            manager = detect_and_create_manager(silent, log_file)
            if isinstance(manager, WindowsManager):
                return {
                    "success": False,
                    "error": "Repository addition is only available on Linux",
                }

            total_steps = 2
            current_step = 0

            if ctx:
                await ctx.report_progress(progress=0, total=total_steps)

            result = manager.add_repository(repo_url, name)
            current_step = total_steps

            if ctx:
                await ctx.report_progress(progress=current_step, total=total_steps)

            logger.debug(f"Repository addition completed: {repo_url}")
            return result
        except Exception as e:
            logger.error(f"Failed to add repository: {str(e)}")
            return {"success": False, "error": f"Unexpected error: {str(e)}"}

    @mcp.tool(
        annotations={
            "title": "Install Local Package",
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": True,
            "openWorldHint": False,
        },
        tags={"system_management", "linux"},
    )
    async def install_local_package(
        file_path: str = Field(
            description="Path to the local package file to install (.deb or .rpm)",
            default=None,
        ),
        silent: Optional[bool] = Field(
            description="Suppress output",
            default=to_boolean(os.environ.get("SYSTEMS_MANAGER_SILENT", False)),
        ),
        log_file: Optional[str] = Field(
            description="Path to log file",
            default=os.environ.get("SYSTEMS_MANAGER_LOG_FILE", None),
        ),
        ctx: Context = Field(
            description="MCP context for progress reporting", default=None
        ),
    ) -> Dict:
        """Installs a local Linux package file using the appropriate tool (dpkg/rpm/dnf/zypper/pacman). (Linux only)"""
        logger = logging.getLogger("SystemsManager")
        logger.debug(
            f"Installing local package: {file_path}, silent: {silent}, log_file: {log_file}"
        )

        if not file_path:
            return {"success": False, "error": "No package file path provided"}

        try:
            manager = detect_and_create_manager(silent, log_file)
            if isinstance(manager, WindowsManager):
                return {
                    "success": False,
                    "error": "Local package installation is only available on Linux",
                }

            total_steps = 1

            if ctx:
                await ctx.report_progress(progress=0, total=total_steps)

            result = manager.install_local_package(file_path)

            if ctx:
                await ctx.report_progress(progress=total_steps, total=total_steps)

            logger.debug(f"Local package installation completed: {file_path}")
            return result
        except Exception as e:
            logger.error(f"Failed to install local package: {str(e)}")
            return {"success": False, "error": f"Unexpected error: {str(e)}"}

    @mcp.tool(
        annotations={
            "title": "Install Local Package",
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": True,
            "openWorldHint": False,
        },
        tags={"system_management", "linux"},
    )
    async def run_command(
        command: str = Field(
            description="Command to run on the system",
            default=None,
        ),
        elevated: bool = Field(
            description="Elevate the shell to root or administrator privileges",
            default=to_boolean(string="false"),
        ),
        shell: bool = Field(
            description="Optionally execute in shell",
            default=to_boolean(string="false"),
        ),
        silent: Optional[bool] = Field(
            description="Suppress output",
            default=to_boolean(os.environ.get("SYSTEMS_MANAGER_SILENT", False)),
        ),
        log_file: Optional[str] = Field(
            description="Path to log file",
            default=os.environ.get("SYSTEMS_MANAGER_LOG_FILE", None),
        ),
        ctx: Context = Field(
            description="MCP context for progress reporting", default=None
        ),
    ) -> Dict:
        """Runs a command on the host. Can run elevated for administrator or root privileges."""
        logger = logging.getLogger("SystemsManager")
        logger.debug(
            f"Running command: {command}, elevated: {elevated}, shell: {shell}, silent: {silent}, log_file: {log_file}"
        )

        try:
            manager = detect_and_create_manager(silent, log_file)
            if isinstance(manager, WindowsManager):
                return {
                    "success": False,
                    "error": "Local package installation is only available on Linux",
                }

            total_steps = 1

            if ctx:
                await ctx.report_progress(progress=0, total=total_steps)

            result = manager.run_command(
                command=command, elevated=elevated, shell=shell
            )

            if ctx:
                await ctx.report_progress(progress=total_steps, total=total_steps)

            logger.debug(f"Command run completed: {command}\nResult: {result}")
            return result
        except Exception as e:
            logger.error(f"Failed to install local package: {str(e)}")
            return {"success": False, "error": f"Unexpected error: {str(e)}"}


def register_text_editor_tools(mcp: FastMCP):
    @mcp.tool(
        annotations={
            "title": "Text Editor",
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": False,
            "openWorldHint": True,
        },
        tags={"text_editor", "files"},
    )
    async def text_editor(
        command: str = Field(
            description="The command to perform: view, create, str_replace, insert, undo_edit"
        ),
        path: str = Field(description="Path to the file"),
        file_text: Optional[str] = Field(
            description="Content to write or insert", default=None
        ),
        view_range: Optional[List[int]] = Field(
            description="Line range to view [start, end]", default=None
        ),
        old_str: Optional[str] = Field(description="String to replace", default=None),
        new_str: Optional[str] = Field(description="Replacement string", default=None),
        insert_line: Optional[int] = Field(
            description="Line number to insert at", default=None
        ),
        ctx: Context = Field(
            description="MCP context for progress reporting.", default=None
        ),
    ) -> Dict[str, Any]:
        """
        View and edit files on the local filesystem.
        """
        logger.debug(f"Text editor command: {command} on {path}")
        expanded_path = os.path.abspath(os.path.expanduser(path))

        try:
            if command == "view":
                if not os.path.exists(expanded_path):
                    return {"status": 404, "error": "File not found"}
                with open(expanded_path, "r") as f:
                    lines = f.readlines()
                content = "".join(lines)
                if view_range and len(view_range) == 2:
                    start, end = view_range
                    start = max(1, start)
                    end = min(len(lines), end)
                    content = "".join(lines[start - 1 : end])
                return {"status": 200, "content": content, "path": expanded_path}

            elif command == "create":
                if os.path.exists(expanded_path):
                    return {"status": 400, "error": "File already exists"}
                os.makedirs(os.path.dirname(expanded_path), exist_ok=True)
                with open(expanded_path, "w") as f:
                    f.write(file_text or "")
                return {"status": 200, "message": "File created", "path": expanded_path}

            elif command == "str_replace":
                if not os.path.exists(expanded_path):
                    return {"status": 404, "error": "File not found"}
                with open(expanded_path, "r") as f:
                    content = f.read()
                if old_str not in content:
                    return {"status": 400, "error": "Target string not found"}
                new_content = content.replace(old_str, new_str or "", 1)
                with open(expanded_path, "w") as f:
                    f.write(new_content)
                return {"status": 200, "message": "File updated", "path": expanded_path}

            elif command == "insert":
                if not os.path.exists(expanded_path):
                    return {"status": 404, "error": "File not found"}
                with open(expanded_path, "r") as f:
                    lines = f.readlines()
                if insert_line is None:
                    return {"status": 400, "error": "insert_line required"}
                idx = max(0, insert_line)
                new_lines = file_text.splitlines(keepends=True)
                if new_lines and not new_lines[-1].endswith("\n"):
                    new_lines[-1] += "\n"

                lines[idx:idx] = new_lines
                with open(expanded_path, "w") as f:
                    f.writelines(lines)
                return {
                    "status": 200,
                    "message": "Content inserted",
                    "path": expanded_path,
                }

            return {"status": 400, "error": f"Unknown command {command}"}

        except Exception as e:
            return {"status": 500, "error": str(e)}


def register_service_tools(mcp: FastMCP):
    @mcp.tool(
        annotations={
            "title": "List Services",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
        tags={"service"},
    )
    async def list_services(
        silent: Optional[bool] = Field(
            description="Suppress output",
            default=to_boolean(os.environ.get("SYSTEMS_MANAGER_SILENT", False)),
        ),
        log_file: Optional[str] = Field(
            description="Path to log file",
            default=os.environ.get("SYSTEMS_MANAGER_LOG_FILE", None),
        ),
        ctx: Context = Field(
            description="MCP context for progress reporting", default=None
        ),
    ) -> Dict:
        """Lists all system services with their current status."""
        try:
            manager = detect_and_create_manager(silent, log_file)
            if ctx:
                await ctx.report_progress(progress=0, total=1)
            result = manager.list_services()
            if ctx:
                await ctx.report_progress(progress=1, total=1)
            return result
        except Exception as e:
            return {"success": False, "error": str(e)}

    @mcp.tool(
        annotations={
            "title": "Get Service Status",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
        tags={"service"},
    )
    async def get_service_status(
        name: str = Field(description="Name of the service to check"),
        silent: Optional[bool] = Field(
            description="Suppress output",
            default=to_boolean(os.environ.get("SYSTEMS_MANAGER_SILENT", False)),
        ),
        log_file: Optional[str] = Field(
            description="Path to log file",
            default=os.environ.get("SYSTEMS_MANAGER_LOG_FILE", None),
        ),
        ctx: Context = Field(
            description="MCP context for progress reporting", default=None
        ),
    ) -> Dict:
        """Gets the status of a specific system service."""
        try:
            manager = detect_and_create_manager(silent, log_file)
            if ctx:
                await ctx.report_progress(progress=0, total=1)
            result = manager.get_service_status(name)
            if ctx:
                await ctx.report_progress(progress=1, total=1)
            return result
        except Exception as e:
            return {"success": False, "error": str(e)}

    @mcp.tool(
        annotations={
            "title": "Start Service",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
        tags={"service"},
    )
    async def start_service(
        name: str = Field(description="Name of the service to start"),
        silent: Optional[bool] = Field(
            description="Suppress output",
            default=to_boolean(os.environ.get("SYSTEMS_MANAGER_SILENT", False)),
        ),
        log_file: Optional[str] = Field(
            description="Path to log file",
            default=os.environ.get("SYSTEMS_MANAGER_LOG_FILE", None),
        ),
        ctx: Context = Field(
            description="MCP context for progress reporting", default=None
        ),
    ) -> Dict:
        """Starts a system service."""
        try:
            manager = detect_and_create_manager(silent, log_file)
            result = manager.start_service(name)
            return result
        except Exception as e:
            return {"success": False, "error": str(e)}

    @mcp.tool(
        annotations={
            "title": "Stop Service",
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": True,
            "openWorldHint": False,
        },
        tags={"service"},
    )
    async def stop_service(
        name: str = Field(description="Name of the service to stop"),
        silent: Optional[bool] = Field(
            description="Suppress output",
            default=to_boolean(os.environ.get("SYSTEMS_MANAGER_SILENT", False)),
        ),
        log_file: Optional[str] = Field(
            description="Path to log file",
            default=os.environ.get("SYSTEMS_MANAGER_LOG_FILE", None),
        ),
        ctx: Context = Field(
            description="MCP context for progress reporting", default=None
        ),
    ) -> Dict:
        """Stops a system service."""
        try:
            manager = detect_and_create_manager(silent, log_file)
            result = manager.stop_service(name)
            return result
        except Exception as e:
            return {"success": False, "error": str(e)}

    @mcp.tool(
        annotations={
            "title": "Restart Service",
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": True,
            "openWorldHint": False,
        },
        tags={"service"},
    )
    async def restart_service(
        name: str = Field(description="Name of the service to restart"),
        silent: Optional[bool] = Field(
            description="Suppress output",
            default=to_boolean(os.environ.get("SYSTEMS_MANAGER_SILENT", False)),
        ),
        log_file: Optional[str] = Field(
            description="Path to log file",
            default=os.environ.get("SYSTEMS_MANAGER_LOG_FILE", None),
        ),
        ctx: Context = Field(
            description="MCP context for progress reporting", default=None
        ),
    ) -> Dict:
        """Restarts a system service."""
        try:
            manager = detect_and_create_manager(silent, log_file)
            result = manager.restart_service(name)
            return result
        except Exception as e:
            return {"success": False, "error": str(e)}

    @mcp.tool(
        annotations={
            "title": "Enable Service",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
        tags={"service"},
    )
    async def enable_service(
        name: str = Field(description="Name of the service to enable at boot"),
        silent: Optional[bool] = Field(
            description="Suppress output",
            default=to_boolean(os.environ.get("SYSTEMS_MANAGER_SILENT", False)),
        ),
        log_file: Optional[str] = Field(
            description="Path to log file",
            default=os.environ.get("SYSTEMS_MANAGER_LOG_FILE", None),
        ),
        ctx: Context = Field(
            description="MCP context for progress reporting", default=None
        ),
    ) -> Dict:
        """Enables a system service to start at boot."""
        try:
            manager = detect_and_create_manager(silent, log_file)
            result = manager.enable_service(name)
            return result
        except Exception as e:
            return {"success": False, "error": str(e)}

    @mcp.tool(
        annotations={
            "title": "Disable Service",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
        tags={"service"},
    )
    async def disable_service(
        name: str = Field(description="Name of the service to disable at boot"),
        silent: Optional[bool] = Field(
            description="Suppress output",
            default=to_boolean(os.environ.get("SYSTEMS_MANAGER_SILENT", False)),
        ),
        log_file: Optional[str] = Field(
            description="Path to log file",
            default=os.environ.get("SYSTEMS_MANAGER_LOG_FILE", None),
        ),
        ctx: Context = Field(
            description="MCP context for progress reporting", default=None
        ),
    ) -> Dict:
        """Disables a system service from starting at boot."""
        try:
            manager = detect_and_create_manager(silent, log_file)
            result = manager.disable_service(name)
            return result
        except Exception as e:
            return {"success": False, "error": str(e)}


def register_process_tools(mcp: FastMCP):
    @mcp.tool(
        annotations={
            "title": "List Processes",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
        tags={"process"},
    )
    async def list_processes(
        silent: Optional[bool] = Field(
            description="Suppress output",
            default=to_boolean(os.environ.get("SYSTEMS_MANAGER_SILENT", False)),
        ),
        log_file: Optional[str] = Field(
            description="Path to log file",
            default=os.environ.get("SYSTEMS_MANAGER_LOG_FILE", None),
        ),
        ctx: Context = Field(
            description="MCP context for progress reporting", default=None
        ),
    ) -> Dict:
        """Lists all running processes with PID, name, CPU%, memory%, and status."""
        try:
            manager = detect_and_create_manager(silent, log_file)
            return manager.list_processes()
        except Exception as e:
            return {"success": False, "error": str(e)}

    @mcp.tool(
        annotations={
            "title": "Get Process Info",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
        tags={"process"},
    )
    async def get_process_info(
        pid: int = Field(description="Process ID to get information about"),
        silent: Optional[bool] = Field(
            description="Suppress output",
            default=to_boolean(os.environ.get("SYSTEMS_MANAGER_SILENT", False)),
        ),
        log_file: Optional[str] = Field(
            description="Path to log file",
            default=os.environ.get("SYSTEMS_MANAGER_LOG_FILE", None),
        ),
        ctx: Context = Field(
            description="MCP context for progress reporting", default=None
        ),
    ) -> Dict:
        """Gets detailed information about a specific process by PID."""
        try:
            manager = detect_and_create_manager(silent, log_file)
            return manager.get_process_info(pid)
        except Exception as e:
            return {"success": False, "error": str(e)}

    @mcp.tool(
        annotations={
            "title": "Kill Process",
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": False,
            "openWorldHint": False,
        },
        tags={"process"},
    )
    async def kill_process(
        pid: int = Field(description="Process ID to kill"),
        signal: Optional[int] = Field(
            description="Signal to send (15=SIGTERM, 9=SIGKILL)", default=15
        ),
        silent: Optional[bool] = Field(
            description="Suppress output",
            default=to_boolean(os.environ.get("SYSTEMS_MANAGER_SILENT", False)),
        ),
        log_file: Optional[str] = Field(
            description="Path to log file",
            default=os.environ.get("SYSTEMS_MANAGER_LOG_FILE", None),
        ),
        ctx: Context = Field(
            description="MCP context for progress reporting", default=None
        ),
    ) -> Dict:
        """Kills a process by PID. Default signal is SIGTERM (15), use 9 for SIGKILL."""
        try:
            manager = detect_and_create_manager(silent, log_file)
            return manager.kill_process(pid, signal)
        except Exception as e:
            return {"success": False, "error": str(e)}


def register_network_tools(mcp: FastMCP):
    @mcp.tool(
        annotations={
            "title": "List Network Interfaces",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
        tags={"network"},
    )
    async def list_network_interfaces(
        silent: Optional[bool] = Field(
            description="Suppress output",
            default=to_boolean(os.environ.get("SYSTEMS_MANAGER_SILENT", False)),
        ),
        log_file: Optional[str] = Field(
            description="Path to log file",
            default=os.environ.get("SYSTEMS_MANAGER_LOG_FILE", None),
        ),
        ctx: Context = Field(
            description="MCP context for progress reporting", default=None
        ),
    ) -> Dict:
        """Lists all network interfaces with IP addresses, speed, and MTU."""
        try:
            manager = detect_and_create_manager(silent, log_file)
            return manager.list_network_interfaces()
        except Exception as e:
            return {"success": False, "error": str(e)}

    @mcp.tool(
        annotations={
            "title": "List Open Ports",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
        tags={"network"},
    )
    async def list_open_ports(
        silent: Optional[bool] = Field(
            description="Suppress output",
            default=to_boolean(os.environ.get("SYSTEMS_MANAGER_SILENT", False)),
        ),
        log_file: Optional[str] = Field(
            description="Path to log file",
            default=os.environ.get("SYSTEMS_MANAGER_LOG_FILE", None),
        ),
        ctx: Context = Field(
            description="MCP context for progress reporting", default=None
        ),
    ) -> Dict:
        """Lists all open/listening network ports with associated PIDs."""
        try:
            manager = detect_and_create_manager(silent, log_file)
            return manager.list_open_ports()
        except Exception as e:
            return {"success": False, "error": str(e)}

    @mcp.tool(
        annotations={
            "title": "Ping Host",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
        tags={"network"},
    )
    async def ping_host(
        host: str = Field(description="Hostname or IP address to ping"),
        count: Optional[int] = Field(
            description="Number of ping packets to send", default=4
        ),
        silent: Optional[bool] = Field(
            description="Suppress output",
            default=to_boolean(os.environ.get("SYSTEMS_MANAGER_SILENT", False)),
        ),
        log_file: Optional[str] = Field(
            description="Path to log file",
            default=os.environ.get("SYSTEMS_MANAGER_LOG_FILE", None),
        ),
        ctx: Context = Field(
            description="MCP context for progress reporting", default=None
        ),
    ) -> Dict:
        """Pings a host and returns the results."""
        try:
            manager = detect_and_create_manager(silent, log_file)
            return manager.ping_host(host, count)
        except Exception as e:
            return {"success": False, "error": str(e)}

    @mcp.tool(
        annotations={
            "title": "DNS Lookup",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
        tags={"network"},
    )
    async def dns_lookup(
        hostname: str = Field(description="Hostname to resolve"),
        silent: Optional[bool] = Field(
            description="Suppress output",
            default=to_boolean(os.environ.get("SYSTEMS_MANAGER_SILENT", False)),
        ),
        log_file: Optional[str] = Field(
            description="Path to log file",
            default=os.environ.get("SYSTEMS_MANAGER_LOG_FILE", None),
        ),
        ctx: Context = Field(
            description="MCP context for progress reporting", default=None
        ),
    ) -> Dict:
        """Performs a DNS lookup for a hostname and returns resolved IP addresses."""
        try:
            manager = detect_and_create_manager(silent, log_file)
            return manager.dns_lookup(hostname)
        except Exception as e:
            return {"success": False, "error": str(e)}


def register_disk_tools(mcp: FastMCP):
    @mcp.tool(
        annotations={
            "title": "List Disks",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
        tags={"disk"},
    )
    async def list_disks(
        silent: Optional[bool] = Field(
            description="Suppress output",
            default=to_boolean(os.environ.get("SYSTEMS_MANAGER_SILENT", False)),
        ),
        log_file: Optional[str] = Field(
            description="Path to log file",
            default=os.environ.get("SYSTEMS_MANAGER_LOG_FILE", None),
        ),
        ctx: Context = Field(
            description="MCP context for progress reporting", default=None
        ),
    ) -> Dict:
        """Lists all disk partitions with mount points and usage statistics."""
        try:
            manager = detect_and_create_manager(silent, log_file)
            return manager.list_disks()
        except Exception as e:
            return {"success": False, "error": str(e)}

    @mcp.tool(
        annotations={
            "title": "Get Disk Usage",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
        tags={"disk"},
    )
    async def get_disk_usage(
        path: Optional[str] = Field(
            description="Path to check disk usage for", default="/"
        ),
        silent: Optional[bool] = Field(
            description="Suppress output",
            default=to_boolean(os.environ.get("SYSTEMS_MANAGER_SILENT", False)),
        ),
        log_file: Optional[str] = Field(
            description="Path to log file",
            default=os.environ.get("SYSTEMS_MANAGER_LOG_FILE", None),
        ),
        ctx: Context = Field(
            description="MCP context for progress reporting", default=None
        ),
    ) -> Dict:
        """Gets disk usage statistics for a specific path."""
        try:
            manager = detect_and_create_manager(silent, log_file)
            return manager.get_disk_usage(path)
        except Exception as e:
            return {"success": False, "error": str(e)}

    @mcp.tool(
        annotations={
            "title": "Get Disk Space Report",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
        tags={"disk"},
    )
    async def get_disk_space_report(
        path: Optional[str] = Field(description="Base path to analyze", default="/"),
        top_n: Optional[int] = Field(
            description="Number of largest directories to show", default=10
        ),
        silent: Optional[bool] = Field(
            description="Suppress output",
            default=to_boolean(os.environ.get("SYSTEMS_MANAGER_SILENT", False)),
        ),
        log_file: Optional[str] = Field(
            description="Path to log file",
            default=os.environ.get("SYSTEMS_MANAGER_LOG_FILE", None),
        ),
        ctx: Context = Field(
            description="MCP context for progress reporting", default=None
        ),
    ) -> Dict:
        """Gets a report of the largest directories under a path."""
        try:
            manager = detect_and_create_manager(silent, log_file)
            return manager.get_disk_space_report(path, top_n)
        except Exception as e:
            return {"success": False, "error": str(e)}


def register_user_tools(mcp: FastMCP):
    @mcp.tool(
        annotations={
            "title": "List Users",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
        tags={"user"},
    )
    async def list_users(
        silent: Optional[bool] = Field(
            description="Suppress output",
            default=to_boolean(os.environ.get("SYSTEMS_MANAGER_SILENT", False)),
        ),
        log_file: Optional[str] = Field(
            description="Path to log file",
            default=os.environ.get("SYSTEMS_MANAGER_LOG_FILE", None),
        ),
        ctx: Context = Field(
            description="MCP context for progress reporting", default=None
        ),
    ) -> Dict:
        """Lists all system users with UID, GID, home directory, and shell."""
        try:
            manager = detect_and_create_manager(silent, log_file)
            return manager.list_users()
        except Exception as e:
            return {"success": False, "error": str(e)}

    @mcp.tool(
        annotations={
            "title": "List Groups",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
        tags={"user"},
    )
    async def list_groups(
        silent: Optional[bool] = Field(
            description="Suppress output",
            default=to_boolean(os.environ.get("SYSTEMS_MANAGER_SILENT", False)),
        ),
        log_file: Optional[str] = Field(
            description="Path to log file",
            default=os.environ.get("SYSTEMS_MANAGER_LOG_FILE", None),
        ),
        ctx: Context = Field(
            description="MCP context for progress reporting", default=None
        ),
    ) -> Dict:
        """Lists all system groups with GID and members."""
        try:
            manager = detect_and_create_manager(silent, log_file)
            return manager.list_groups()
        except Exception as e:
            return {"success": False, "error": str(e)}


def register_log_tools(mcp: FastMCP):
    @mcp.tool(
        annotations={
            "title": "Get System Logs",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
        tags={"log"},
    )
    async def get_system_logs(
        unit: Optional[str] = Field(
            description="Systemd unit to filter logs by", default=None
        ),
        lines: Optional[int] = Field(
            description="Number of log lines to return", default=100
        ),
        priority: Optional[str] = Field(
            description="Log priority filter (emerg,alert,crit,err,warning,notice,info,debug)",
            default=None,
        ),
        silent: Optional[bool] = Field(
            description="Suppress output",
            default=to_boolean(os.environ.get("SYSTEMS_MANAGER_SILENT", False)),
        ),
        log_file: Optional[str] = Field(
            description="Path to log file",
            default=os.environ.get("SYSTEMS_MANAGER_LOG_FILE", None),
        ),
        ctx: Context = Field(
            description="MCP context for progress reporting", default=None
        ),
    ) -> Dict:
        """Gets system logs from journalctl (Linux) or Event Log (Windows)."""
        logger = logging.getLogger("SystemsManager")
        logger.debug(
            f"Getting system logs, unit: {unit}, lines: {lines}, priority: {priority}"
        )
        try:
            manager = detect_and_create_manager(silent, log_file)
            result = manager.get_system_logs(unit, lines, priority)
            if not result.get("success"):
                logger.error(
                    f"Failed to get system logs. Error: {result.get('error', result.get('logs', 'Unknown error'))}"
                )
            else:
                logger.debug("Successfully retrieved system logs.")
            return result
        except Exception as e:
            logger.error(f"Exception while getting system logs: {str(e)}")
            return {"success": False, "error": str(e)}

    @mcp.tool(
        annotations={
            "title": "Tail Log File",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
        tags={"log"},
    )
    async def tail_log_file(
        path: str = Field(description="Path to the log file to tail"),
        lines: Optional[int] = Field(
            description="Number of lines to read from the end", default=50
        ),
        silent: Optional[bool] = Field(
            description="Suppress output",
            default=to_boolean(os.environ.get("SYSTEMS_MANAGER_SILENT", False)),
        ),
        log_file: Optional[str] = Field(
            description="Path to log file",
            default=os.environ.get("SYSTEMS_MANAGER_LOG_FILE", None),
        ),
        ctx: Context = Field(
            description="MCP context for progress reporting", default=None
        ),
    ) -> Dict:
        """Reads the last N lines of a log file."""
        logger = logging.getLogger("SystemsManager")
        logger.debug(f"Tailing log file: {path}, lines: {lines}")
        try:
            manager = detect_and_create_manager(silent, log_file)
            result = manager.tail_log_file(path, lines)
            if not result.get("success"):
                logger.error(
                    f"Failed to tail log file. Error: {result.get('error', result.get('logs', 'Unknown error'))}"
                )
            else:
                logger.debug("Successfully tailed log file.")
            return result
        except Exception as e:
            logger.error(f"Exception while tailing log file: {str(e)}")
            return {"success": False, "error": str(e)}


def register_cron_tools(mcp: FastMCP):
    @mcp.tool(
        annotations={
            "title": "List Cron Jobs",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
        tags={"cron"},
    )
    async def list_cron_jobs(
        user: Optional[str] = Field(
            description="User whose cron jobs to list (Linux only)", default=None
        ),
        silent: Optional[bool] = Field(
            description="Suppress output",
            default=to_boolean(os.environ.get("SYSTEMS_MANAGER_SILENT", False)),
        ),
        log_file: Optional[str] = Field(
            description="Path to log file",
            default=os.environ.get("SYSTEMS_MANAGER_LOG_FILE", None),
        ),
        ctx: Context = Field(
            description="MCP context for progress reporting", default=None
        ),
    ) -> Dict:
        """Lists cron jobs (Linux) or scheduled tasks (Windows)."""
        try:
            manager = detect_and_create_manager(silent, log_file)
            return manager.list_cron_jobs(user)
        except Exception as e:
            return {"success": False, "error": str(e)}

    @mcp.tool(
        annotations={
            "title": "Add Cron Job",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": False,
        },
        tags={"cron"},
    )
    async def add_cron_job(
        schedule: str = Field(
            description="Cron schedule expression (e.g. '0 * * * *' for hourly)"
        ),
        command: str = Field(description="Command to run on schedule"),
        user: Optional[str] = Field(
            description="User to add cron job for (Linux only)", default=None
        ),
        silent: Optional[bool] = Field(
            description="Suppress output",
            default=to_boolean(os.environ.get("SYSTEMS_MANAGER_SILENT", False)),
        ),
        log_file: Optional[str] = Field(
            description="Path to log file",
            default=os.environ.get("SYSTEMS_MANAGER_LOG_FILE", None),
        ),
        ctx: Context = Field(
            description="MCP context for progress reporting", default=None
        ),
    ) -> Dict:
        """Adds a new cron job (Linux only)."""
        try:
            manager = detect_and_create_manager(silent, log_file)
            return manager.add_cron_job(schedule, command, user)
        except Exception as e:
            return {"success": False, "error": str(e)}

    @mcp.tool(
        annotations={
            "title": "Remove Cron Job",
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": False,
            "openWorldHint": False,
        },
        tags={"cron"},
    )
    async def remove_cron_job(
        pattern: str = Field(description="Pattern to match cron jobs for removal"),
        user: Optional[str] = Field(
            description="User whose cron tab to modify (Linux only)", default=None
        ),
        silent: Optional[bool] = Field(
            description="Suppress output",
            default=to_boolean(os.environ.get("SYSTEMS_MANAGER_SILENT", False)),
        ),
        log_file: Optional[str] = Field(
            description="Path to log file",
            default=os.environ.get("SYSTEMS_MANAGER_LOG_FILE", None),
        ),
        ctx: Context = Field(
            description="MCP context for progress reporting", default=None
        ),
    ) -> Dict:
        """Removes cron jobs matching a pattern (Linux only)."""
        try:
            manager = detect_and_create_manager(silent, log_file)
            return manager.remove_cron_job(pattern, user)
        except Exception as e:
            return {"success": False, "error": str(e)}


def register_firewall_management_tools(mcp: FastMCP):
    @mcp.tool(
        annotations={
            "title": "Get Firewall Status",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
        tags={"firewall_management"},
    )
    async def get_firewall_status(
        silent: Optional[bool] = Field(
            description="Suppress output",
            default=to_boolean(os.environ.get("SYSTEMS_MANAGER_SILENT", False)),
        ),
        log_file: Optional[str] = Field(
            description="Path to log file",
            default=os.environ.get("SYSTEMS_MANAGER_LOG_FILE", None),
        ),
        ctx: Context = Field(
            description="MCP context for progress reporting", default=None
        ),
    ) -> Dict:
        """Gets the current firewall status (ufw/firewalld/iptables on Linux, netsh on Windows)."""
        try:
            manager = detect_and_create_manager(silent, log_file)
            return manager.get_firewall_status()
        except Exception as e:
            return {"success": False, "error": str(e)}

    @mcp.tool(
        annotations={
            "title": "List Firewall Rules",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
        tags={"firewall_management"},
    )
    async def list_firewall_rules(
        silent: Optional[bool] = Field(
            description="Suppress output",
            default=to_boolean(os.environ.get("SYSTEMS_MANAGER_SILENT", False)),
        ),
        log_file: Optional[str] = Field(
            description="Path to log file",
            default=os.environ.get("SYSTEMS_MANAGER_LOG_FILE", None),
        ),
        ctx: Context = Field(
            description="MCP context for progress reporting", default=None
        ),
    ) -> Dict:
        """Lists all firewall rules."""
        try:
            manager = detect_and_create_manager(silent, log_file)
            return manager.list_firewall_rules()
        except Exception as e:
            return {"success": False, "error": str(e)}

    @mcp.tool(
        annotations={
            "title": "Add Firewall Rule",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": False,
        },
        tags={"firewall_management"},
    )
    async def add_firewall_rule(
        rule: str = Field(
            description="Firewall rule specification (e.g. 'allow 80/tcp' for ufw)"
        ),
        silent: Optional[bool] = Field(
            description="Suppress output",
            default=to_boolean(os.environ.get("SYSTEMS_MANAGER_SILENT", False)),
        ),
        log_file: Optional[str] = Field(
            description="Path to log file",
            default=os.environ.get("SYSTEMS_MANAGER_LOG_FILE", None),
        ),
        ctx: Context = Field(
            description="MCP context for progress reporting", default=None
        ),
    ) -> Dict:
        """Adds a firewall rule using the detected firewall tool."""
        try:
            manager = detect_and_create_manager(silent, log_file)
            return manager.add_firewall_rule(rule)
        except Exception as e:
            return {"success": False, "error": str(e)}

    @mcp.tool(
        annotations={
            "title": "Remove Firewall Rule",
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": False,
            "openWorldHint": False,
        },
        tags={"firewall_management"},
    )
    async def remove_firewall_rule(
        rule: str = Field(description="Firewall rule specification to remove"),
        silent: Optional[bool] = Field(
            description="Suppress output",
            default=to_boolean(os.environ.get("SYSTEMS_MANAGER_SILENT", False)),
        ),
        log_file: Optional[str] = Field(
            description="Path to log file",
            default=os.environ.get("SYSTEMS_MANAGER_LOG_FILE", None),
        ),
        ctx: Context = Field(
            description="MCP context for progress reporting", default=None
        ),
    ) -> Dict:
        """Removes a firewall rule using the detected firewall tool."""
        try:
            manager = detect_and_create_manager(silent, log_file)
            return manager.remove_firewall_rule(rule)
        except Exception as e:
            return {"success": False, "error": str(e)}


def register_ssh_management_tools(mcp: FastMCP):
    @mcp.tool(
        annotations={
            "title": "List SSH Keys",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
        tags={"ssh_management"},
    )
    async def list_ssh_keys(
        silent: Optional[bool] = Field(
            description="Suppress output",
            default=to_boolean(os.environ.get("SYSTEMS_MANAGER_SILENT", False)),
        ),
        log_file: Optional[str] = Field(
            description="Path to log file",
            default=os.environ.get("SYSTEMS_MANAGER_LOG_FILE", None),
        ),
        ctx: Context = Field(
            description="MCP context for progress reporting", default=None
        ),
    ) -> Dict:
        """Lists all SSH keys in the user's ~/.ssh directory."""
        try:
            manager = detect_and_create_manager(silent, log_file)
            return manager.list_ssh_keys()
        except Exception as e:
            return {"success": False, "error": str(e)}

    @mcp.tool(
        annotations={
            "title": "Generate SSH Key",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": False,
        },
        tags={"ssh_management"},
    )
    async def generate_ssh_key(
        key_type: Optional[str] = Field(
            description="Key type (ed25519, rsa, ecdsa)", default="ed25519"
        ),
        comment: Optional[str] = Field(description="Comment for the key", default=""),
        passphrase: Optional[str] = Field(
            description="Passphrase for the key (empty for no passphrase)", default=""
        ),
        silent: Optional[bool] = Field(
            description="Suppress output",
            default=to_boolean(os.environ.get("SYSTEMS_MANAGER_SILENT", False)),
        ),
        log_file: Optional[str] = Field(
            description="Path to log file",
            default=os.environ.get("SYSTEMS_MANAGER_LOG_FILE", None),
        ),
        ctx: Context = Field(
            description="MCP context for progress reporting", default=None
        ),
    ) -> Dict:
        """Generates a new SSH key pair."""
        try:
            manager = detect_and_create_manager(silent, log_file)
            return manager.generate_ssh_key(key_type, comment, passphrase)
        except Exception as e:
            return {"success": False, "error": str(e)}

    @mcp.tool(
        annotations={
            "title": "Add Authorized Key",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
        tags={"ssh_management"},
    )
    async def add_authorized_key(
        public_key: str = Field(
            description="Public key string to add to authorized_keys"
        ),
        silent: Optional[bool] = Field(
            description="Suppress output",
            default=to_boolean(os.environ.get("SYSTEMS_MANAGER_SILENT", False)),
        ),
        log_file: Optional[str] = Field(
            description="Path to log file",
            default=os.environ.get("SYSTEMS_MANAGER_LOG_FILE", None),
        ),
        ctx: Context = Field(
            description="MCP context for progress reporting", default=None
        ),
    ) -> Dict:
        """Adds a public key to the authorized_keys file."""
        try:
            manager = detect_and_create_manager(silent, log_file)
            return manager.add_authorized_key(public_key)
        except Exception as e:
            return {"success": False, "error": str(e)}


def register_filesystem_tools(mcp: FastMCP):
    @mcp.tool(
        annotations={
            "title": "List Files",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
        tags={"filesystem"},
    )
    async def list_files(
        path: str = Field(description="Path to list files from", default="."),
        recursive: bool = Field(description="List recursively", default=False),
        depth: int = Field(description="Recursion depth", default=1),
        silent: Optional[bool] = Field(
            description="Suppress output",
            default=to_boolean(os.environ.get("SYSTEMS_MANAGER_SILENT", False)),
        ),
        log_file: Optional[str] = Field(
            description="Path to log file",
            default=os.environ.get("SYSTEMS_MANAGER_LOG_FILE", None),
        ),
        ctx: Context = Field(
            description="MCP context for progress reporting", default=None
        ),
    ) -> Dict:
        """Lists files and directories in a path."""
        try:
            manager = detect_and_create_manager(silent, log_file)
            return manager.fs_manager.list_files(path, recursive, depth)
        except Exception as e:
            return {"success": False, "error": str(e)}

    @mcp.tool(
        annotations={
            "title": "Search Files",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
        tags={"filesystem"},
    )
    async def search_files(
        path: str = Field(description="Path to search in"),
        pattern: str = Field(description="Pattern to search for in filenames"),
        silent: Optional[bool] = Field(
            description="Suppress output",
            default=to_boolean(os.environ.get("SYSTEMS_MANAGER_SILENT", False)),
        ),
        log_file: Optional[str] = Field(
            description="Path to log file",
            default=os.environ.get("SYSTEMS_MANAGER_LOG_FILE", None),
        ),
        ctx: Context = Field(
            description="MCP context for progress reporting", default=None
        ),
    ) -> Dict:
        """Searches for files matching a pattern."""
        try:
            manager = detect_and_create_manager(silent, log_file)
            return manager.fs_manager.search_files(path, pattern)
        except Exception as e:
            return {"success": False, "error": str(e)}

    @mcp.tool(
        annotations={
            "title": "Grep Files",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
        tags={"filesystem"},
    )
    async def grep_files(
        path: str = Field(description="Path to search within"),
        pattern: str = Field(description="Text pattern to search for inside files"),
        recursive: bool = Field(description="Search recursively", default=False),
        silent: Optional[bool] = Field(
            description="Suppress output",
            default=to_boolean(os.environ.get("SYSTEMS_MANAGER_SILENT", False)),
        ),
        log_file: Optional[str] = Field(
            description="Path to log file",
            default=os.environ.get("SYSTEMS_MANAGER_LOG_FILE", None),
        ),
        ctx: Context = Field(
            description="MCP context for progress reporting", default=None
        ),
    ) -> Dict:
        """Searches for text content inside files (like grep)."""
        try:
            manager = detect_and_create_manager(silent, log_file)
            return manager.fs_manager.grep_files(path, pattern, recursive)
        except Exception as e:
            return {"success": False, "error": str(e)}

    @mcp.tool(
        annotations={
            "title": "Manage File",
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": False,
            "openWorldHint": True,
        },
        tags={"filesystem"},
    )
    async def manage_file(
        action: str = Field(
            description="Action to perform: create, update, delete, read"
        ),
        path: str = Field(description="Path to the file"),
        content: Optional[str] = Field(
            description="Content for create/update", default=None
        ),
        silent: Optional[bool] = Field(
            description="Suppress output",
            default=to_boolean(os.environ.get("SYSTEMS_MANAGER_SILENT", False)),
        ),
        log_file: Optional[str] = Field(
            description="Path to log file",
            default=os.environ.get("SYSTEMS_MANAGER_LOG_FILE", None),
        ),
        ctx: Context = Field(
            description="MCP context for progress reporting", default=None
        ),
    ) -> Dict:
        """Creates, updates, deletes, or reads a file."""
        try:
            manager = detect_and_create_manager(silent, log_file)
            return manager.fs_manager.manage_file(action, path, content)
        except Exception as e:
            return {"success": False, "error": str(e)}


def register_shell_tools(mcp: FastMCP):
    @mcp.tool(
        annotations={
            "title": "Add Shell Alias",
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": True,
            "openWorldHint": False,
        },
        tags={"shell"},
    )
    async def add_shell_alias(
        name: str = Field(description="Alias name"),
        command: str = Field(description="Command to alias"),
        shell: str = Field(description="Shell type (bash, zsh, fish)", default="bash"),
        silent: Optional[bool] = Field(
            description="Suppress output",
            default=to_boolean(os.environ.get("SYSTEMS_MANAGER_SILENT", False)),
        ),
        log_file: Optional[str] = Field(
            description="Path to log file",
            default=os.environ.get("SYSTEMS_MANAGER_LOG_FILE", None),
        ),
        ctx: Context = Field(
            description="MCP context for progress reporting", default=None
        ),
    ) -> Dict:
        """Adds an alias to the user's shell profile."""
        try:
            manager = detect_and_create_manager(silent, log_file)
            return manager.shell_manager.add_alias(name, command, shell)
        except Exception as e:
            return {"success": False, "error": str(e)}


def register_python_tools(mcp: FastMCP):
    @mcp.tool(
        annotations={
            "title": "Install uv",
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": True,
            "openWorldHint": False,
        },
        tags={"python"},
    )
    async def install_uv(
        silent: Optional[bool] = Field(
            description="Suppress output",
            default=to_boolean(os.environ.get("SYSTEMS_MANAGER_SILENT", False)),
        ),
        log_file: Optional[str] = Field(
            description="Path to log file",
            default=os.environ.get("SYSTEMS_MANAGER_LOG_FILE", None),
        ),
        ctx: Context = Field(
            description="MCP context for progress reporting", default=None
        ),
    ) -> Dict:
        """Installs uv (Python package manager)."""
        try:
            manager = detect_and_create_manager(silent, log_file)
            return manager.python_manager.install_uv()
        except Exception as e:
            return {"success": False, "error": str(e)}

    @mcp.tool(
        annotations={
            "title": "Create Python Venv",
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": True,
            "openWorldHint": True,
        },
        tags={"python"},
    )
    async def create_python_venv(
        path: str = Field(description="Path to create venv at"),
        python_version: Optional[str] = Field(
            description="Python version to use (e.g., 3.11)", default=None
        ),
        silent: Optional[bool] = Field(
            description="Suppress output",
            default=to_boolean(os.environ.get("SYSTEMS_MANAGER_SILENT", False)),
        ),
        log_file: Optional[str] = Field(
            description="Path to log file",
            default=os.environ.get("SYSTEMS_MANAGER_LOG_FILE", None),
        ),
        ctx: Context = Field(
            description="MCP context for progress reporting", default=None
        ),
    ) -> Dict:
        """Creates a Python virtual environment using uv."""
        try:
            manager = detect_and_create_manager(silent, log_file)
            return manager.python_manager.create_venv(path, python_version)
        except Exception as e:
            return {"success": False, "error": str(e)}

    @mcp.tool(
        annotations={
            "title": "Install Python Package (uv)",
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": True,
            "openWorldHint": False,
        },
        tags={"python"},
    )
    async def install_python_package_uv(
        package: str = Field(description="Package name"),
        venv_path: Optional[str] = Field(
            description="Path to virtual environment", default=None
        ),
        silent: Optional[bool] = Field(
            description="Suppress output",
            default=to_boolean(os.environ.get("SYSTEMS_MANAGER_SILENT", False)),
        ),
        log_file: Optional[str] = Field(
            description="Path to log file",
            default=os.environ.get("SYSTEMS_MANAGER_LOG_FILE", None),
        ),
        ctx: Context = Field(
            description="MCP context for progress reporting", default=None
        ),
    ) -> Dict:
        """Installs a Python package using uv pip."""
        try:
            manager = detect_and_create_manager(silent, log_file)
            return manager.python_manager.install_package(package, venv_path)
        except Exception as e:
            return {"success": False, "error": str(e)}


def register_nodejs_tools(mcp: FastMCP):
    @mcp.tool(
        annotations={
            "title": "Install NVM",
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": True,
            "openWorldHint": False,
        },
        tags={"nodejs"},
    )
    async def install_nvm(
        silent: Optional[bool] = Field(
            description="Suppress output",
            default=to_boolean(os.environ.get("SYSTEMS_MANAGER_SILENT", False)),
        ),
        log_file: Optional[str] = Field(
            description="Path to log file",
            default=os.environ.get("SYSTEMS_MANAGER_LOG_FILE", None),
        ),
        ctx: Context = Field(
            description="MCP context for progress reporting", default=None
        ),
    ) -> Dict:
        """Installs NVM (Node Version Manager)."""
        try:
            manager = detect_and_create_manager(silent, log_file)
            return manager.node_manager.install_nvm()
        except Exception as e:
            return {"success": False, "error": str(e)}

    @mcp.tool(
        annotations={
            "title": "Install Node.js",
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": True,
            "openWorldHint": False,
        },
        tags={"nodejs"},
    )
    async def install_node(
        version: str = Field(description="Node version to install", default="--lts"),
        silent: Optional[bool] = Field(
            description="Suppress output",
            default=to_boolean(os.environ.get("SYSTEMS_MANAGER_SILENT", False)),
        ),
        log_file: Optional[str] = Field(
            description="Path to log file",
            default=os.environ.get("SYSTEMS_MANAGER_LOG_FILE", None),
        ),
        ctx: Context = Field(
            description="MCP context for progress reporting", default=None
        ),
    ) -> Dict:
        """Installs a Node.js version using NVM."""
        try:
            manager = detect_and_create_manager(silent, log_file)
            return manager.node_manager.install_node(version)
        except Exception as e:
            return {"success": False, "error": str(e)}

    @mcp.tool(
        annotations={
            "title": "Use Node Version",
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": False,
            "openWorldHint": False,
        },
        tags={"nodejs"},
    )
    async def use_node(
        version: str = Field(description="Node version to use"),
        silent: Optional[bool] = Field(
            description="Suppress output",
            default=to_boolean(os.environ.get("SYSTEMS_MANAGER_SILENT", False)),
        ),
        log_file: Optional[str] = Field(
            description="Path to log file",
            default=os.environ.get("SYSTEMS_MANAGER_LOG_FILE", None),
        ),
        ctx: Context = Field(
            description="MCP context for progress reporting", default=None
        ),
    ) -> Dict:
        """Switches the active Node.js version using NVM."""
        try:
            manager = detect_and_create_manager(silent, log_file)
            return manager.node_manager.use_node(version)
        except Exception as e:
            return {"success": False, "error": str(e)}


def get_mcp_instance() -> tuple[Any, Any, Any, Any]:
    """Initialize and return the MCP instance, args, and middlewares."""
    load_dotenv(find_dotenv())

    args, mcp, middlewares = create_mcp_server(
        name="SystemsManagerMCP",
        version=__version__,
        instructions="Systems Manager MCP Utility — Manage system, applications, services, processes, networks, disks, users, and logs.",
    )

    DEFAULT_MISCTOOL = to_boolean(os.getenv("MISCTOOL", "True"))
    if DEFAULT_MISCTOOL:
        register_misc_tools(mcp)
    DEFAULT_SYSTEMTOOL = to_boolean(os.getenv("SYSTEMTOOL", "True"))
    if DEFAULT_SYSTEMTOOL:
        register_system_tools(mcp)
    DEFAULT_SYSTEM_MANAGEMENTTOOL = to_boolean(
        os.getenv("SYSTEM_MANAGEMENTTOOL", "True")
    )
    if DEFAULT_SYSTEM_MANAGEMENTTOOL:
        register_system_management_tools(mcp)
    DEFAULT_TEXT_EDITORTOOL = to_boolean(os.getenv("TEXT_EDITORTOOL", "True"))
    if DEFAULT_TEXT_EDITORTOOL:
        register_text_editor_tools(mcp)
    DEFAULT_SERVICETOOL = to_boolean(os.getenv("SERVICETOOL", "True"))
    if DEFAULT_SERVICETOOL:
        register_service_tools(mcp)
    DEFAULT_PROCESSTOOL = to_boolean(os.getenv("PROCESSTOOL", "True"))
    if DEFAULT_PROCESSTOOL:
        register_process_tools(mcp)
    DEFAULT_NETWORKTOOL = to_boolean(os.getenv("NETWORKTOOL", "True"))
    if DEFAULT_NETWORKTOOL:
        register_network_tools(mcp)
    DEFAULT_DISKTOOL = to_boolean(os.getenv("DISKTOOL", "True"))
    if DEFAULT_DISKTOOL:
        register_disk_tools(mcp)
    DEFAULT_USERTOOL = to_boolean(os.getenv("USERTOOL", "True"))
    if DEFAULT_USERTOOL:
        register_user_tools(mcp)
    DEFAULT_LOGTOOL = to_boolean(os.getenv("LOGTOOL", "True"))
    if DEFAULT_LOGTOOL:
        register_log_tools(mcp)
    DEFAULT_CRONTOOL = to_boolean(os.getenv("CRONTOOL", "True"))
    if DEFAULT_CRONTOOL:
        register_cron_tools(mcp)
    DEFAULT_FIREWALL_MANAGEMENTTOOL = to_boolean(
        os.getenv("FIREWALL_MANAGEMENTTOOL", "True")
    )
    if DEFAULT_FIREWALL_MANAGEMENTTOOL:
        register_firewall_management_tools(mcp)
    DEFAULT_SSH_MANAGEMENTTOOL = to_boolean(os.getenv("SSH_MANAGEMENTTOOL", "True"))
    if DEFAULT_SSH_MANAGEMENTTOOL:
        register_ssh_management_tools(mcp)
    DEFAULT_FILESYSTEMTOOL = to_boolean(os.getenv("FILESYSTEMTOOL", "True"))
    if DEFAULT_FILESYSTEMTOOL:
        register_filesystem_tools(mcp)
    DEFAULT_SHELLTOOL = to_boolean(os.getenv("SHELLTOOL", "True"))
    if DEFAULT_SHELLTOOL:
        register_shell_tools(mcp)
    DEFAULT_PYTHONTOOL = to_boolean(os.getenv("PYTHONTOOL", "True"))
    if DEFAULT_PYTHONTOOL:
        register_python_tools(mcp)
    DEFAULT_NODEJSTOOL = to_boolean(os.getenv("NODEJSTOOL", "True"))
    if DEFAULT_NODEJSTOOL:
        register_nodejs_tools(mcp)

    for mw in middlewares:
        mcp.add_middleware(mw)

    DEFAULT_MISCTOOL = to_boolean(os.getenv("MISCTOOL", "True"))
    if DEFAULT_MISCTOOL:
        register_misc_tools(mcp)
    DEFAULT_SYSTEMTOOL = to_boolean(os.getenv("SYSTEMTOOL", "True"))
    if DEFAULT_SYSTEMTOOL:
        register_system_tools(mcp)
    DEFAULT_SYSTEM_MANAGEMENTTOOL = to_boolean(
        os.getenv("SYSTEM_MANAGEMENTTOOL", "True")
    )
    if DEFAULT_SYSTEM_MANAGEMENTTOOL:
        register_system_management_tools(mcp)
    DEFAULT_TEXT_EDITORTOOL = to_boolean(os.getenv("TEXT_EDITORTOOL", "True"))
    if DEFAULT_TEXT_EDITORTOOL:
        register_text_editor_tools(mcp)
    DEFAULT_SERVICETOOL = to_boolean(os.getenv("SERVICETOOL", "True"))
    if DEFAULT_SERVICETOOL:
        register_service_tools(mcp)
    DEFAULT_PROCESSTOOL = to_boolean(os.getenv("PROCESSTOOL", "True"))
    if DEFAULT_PROCESSTOOL:
        register_process_tools(mcp)
    DEFAULT_NETWORKTOOL = to_boolean(os.getenv("NETWORKTOOL", "True"))
    if DEFAULT_NETWORKTOOL:
        register_network_tools(mcp)
    DEFAULT_DISKTOOL = to_boolean(os.getenv("DISKTOOL", "True"))
    if DEFAULT_DISKTOOL:
        register_disk_tools(mcp)
    DEFAULT_USERTOOL = to_boolean(os.getenv("USERTOOL", "True"))
    if DEFAULT_USERTOOL:
        register_user_tools(mcp)
    DEFAULT_LOGTOOL = to_boolean(os.getenv("LOGTOOL", "True"))
    if DEFAULT_LOGTOOL:
        register_log_tools(mcp)
    DEFAULT_CRONTOOL = to_boolean(os.getenv("CRONTOOL", "True"))
    if DEFAULT_CRONTOOL:
        register_cron_tools(mcp)
    DEFAULT_FIREWALL_MANAGEMENTTOOL = to_boolean(
        os.getenv("FIREWALL_MANAGEMENTTOOL", "True")
    )
    if DEFAULT_FIREWALL_MANAGEMENTTOOL:
        register_firewall_management_tools(mcp)
    DEFAULT_SSH_MANAGEMENTTOOL = to_boolean(os.getenv("SSH_MANAGEMENTTOOL", "True"))
    if DEFAULT_SSH_MANAGEMENTTOOL:
        register_ssh_management_tools(mcp)
    DEFAULT_FILESYSTEMTOOL = to_boolean(os.getenv("FILESYSTEMTOOL", "True"))
    if DEFAULT_FILESYSTEMTOOL:
        register_filesystem_tools(mcp)
    DEFAULT_SHELLTOOL = to_boolean(os.getenv("SHELLTOOL", "True"))
    if DEFAULT_SHELLTOOL:
        register_shell_tools(mcp)
    DEFAULT_PYTHONTOOL = to_boolean(os.getenv("PYTHONTOOL", "True"))
    if DEFAULT_PYTHONTOOL:
        register_python_tools(mcp)
    DEFAULT_NODEJSTOOL = to_boolean(os.getenv("NODEJSTOOL", "True"))
    if DEFAULT_NODEJSTOOL:
        register_nodejs_tools(mcp)

    for mw in middlewares:
        mcp.add_middleware(mw)
    registered_tags = []
    return mcp, args, middlewares, registered_tags


def mcp_server() -> None:
    mcp, args, middlewares, registered_tags = get_mcp_instance()
    print(f"{args.name or 'systems-manager'} MCP v{__version__}", file=sys.stderr)
    print("\nStarting MCP Server", file=sys.stderr)
    print(f"  Transport: {args.transport.upper()}", file=sys.stderr)
    print(f"  Auth: {args.auth_type}", file=sys.stderr)
    print(f"  Dynamic Tags Loaded: {len(set(registered_tags))}", file=sys.stderr)

    if args.transport == "stdio":
        mcp.run(transport="stdio")
    elif args.transport == "streamable-http":
        mcp.run(transport="streamable-http", host=args.host, port=args.port)
    elif args.transport == "sse":
        mcp.run(transport="sse", host=args.host, port=args.port)
    else:
        logger.error("Invalid transport", extra={"transport": args.transport})
        sys.exit(1)


if __name__ == "__main__":
    mcp_server()
