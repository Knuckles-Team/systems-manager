#!/usr/bin/env python
# coding: utf-8

import getopt
import os
import sys
import logging
from typing import Optional, List, Dict

import requests
from fastmcp import FastMCP, Context
from pydantic import Field
from systems_manager.systems_manager import (
    detect_and_create_manager,
    WindowsManager,
    setup_logging,
)

# Initialize logging for MCP server
setup_logging(is_mcp_server=True, log_file="systems_manager_mcp.log")

mcp = FastMCP(name="SystemsManagerServer")


def to_boolean(string):
    normalized = str(string).strip().lower()
    true_values = {"t", "true", "y", "yes", "1"}
    false_values = {"f", "false", "n", "no", "0"}
    if normalized in true_values:
        return True
    elif normalized in false_values:
        return False
    else:
        raise ValueError(f"Cannot convert '{string}' to boolean")


environment_silent = os.environ.get("SILENT", False)
environment_log_file = os.environ.get("LOG_FILE", None)

if environment_silent:
    environment_silent = to_boolean(environment_silent)


@mcp.tool(
    annotations={
        "title": "Install Applications",
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": True,
        "openWorldHint": False,
    },
    tags={"system_management"},
)
async def install_applications(
    apps: List[str] = Field(
        description="List of application names to install", default=None
    ),
    silent: Optional[bool] = Field(
        description="Suppress output", default=environment_silent
    ),
    log_file: Optional[str] = Field(
        description="Path to log file", default=environment_log_file
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
    tags={"system_management"},
)
async def update(
    silent: Optional[bool] = Field(
        description="Suppress output", default=environment_silent
    ),
    log_file: Optional[str] = Field(
        description="Path to log file", default=environment_log_file
    ),
    ctx: Context = Field(
        description="MCP context for progress reporting", default=None
    ),
) -> Dict:
    """Updates the system and applications."""
    logger = logging.getLogger("SystemsManager")
    logger.debug(f"Updating system, silent: {silent}, log_file: {log_file}")

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
    tags={"system_management"},
)
async def clean(
    silent: Optional[bool] = Field(
        description="Suppress output", default=environment_silent
    ),
    log_file: Optional[str] = Field(
        description="Path to log file", default=environment_log_file
    ),
    ctx: Context = Field(
        description="MCP context for progress reporting", default=None
    ),
) -> Dict:
    """Cleans system resources (e.g., trash/recycle bin)."""
    logger = logging.getLogger("SystemsManager")
    logger.debug(f"Cleaning system, silent: {silent}, log_file: {log_file}")

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
    tags={"system_management"},
)
async def optimize(
    silent: Optional[bool] = Field(
        description="Suppress output", default=environment_silent
    ),
    log_file: Optional[str] = Field(
        description="Path to log file", default=environment_log_file
    ),
    ctx: Context = Field(
        description="MCP context for progress reporting", default=None
    ),
) -> Dict:
    """Optimizes system resources (e.g., autoremove, defrag)."""
    logger = logging.getLogger("SystemsManager")
    logger.debug(f"Optimizing system, silent: {silent}, log_file: {log_file}")

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
    tags={"system_management"},
)
async def install_python_modules(
    modules: List[str] = Field(
        description="List of Python modules to install", default=None
    ),
    silent: Optional[bool] = Field(
        description="Suppress output", default=environment_silent
    ),
    log_file: Optional[str] = Field(
        description="Path to log file", default=environment_log_file
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

    try:
        manager = detect_and_create_manager(silent, log_file)
        total_steps = len(modules) + 1  # +1 for pip upgrade
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
    tags={"system_management"},
)
async def install_fonts(
    fonts: Optional[List[str]] = Field(
        description="List of font names to install (e.g., Hack, Meslo) or 'all' for all fonts",
        default=None,
    ),
    silent: Optional[bool] = Field(
        description="Suppress output", default=environment_silent
    ),
    log_file: Optional[str] = Field(
        description="Path to log file", default=environment_log_file
    ),
    ctx: Context = Field(
        description="MCP context for progress reporting", default=None
    ),
) -> Dict:
    """Installs specified Nerd Fonts or all available fonts if 'all' is specified."""
    logger = logging.getLogger("SystemsManager")
    logger.debug(f"Installing fonts: {fonts}, silent: {silent}, log_file: {log_file}")

    if not fonts:
        fonts = ["Hack"]

    try:
        manager = detect_and_create_manager(silent, log_file)

        # Approximate steps based on fonts
        api_url = "https://api.github.com/repos/ryanoasis/nerd-fonts/releases/latest"
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
    tags={"system_management"},
)
async def get_os_statistics(
    silent: Optional[bool] = Field(
        description="Suppress output", default=environment_silent
    ),
    log_file: Optional[str] = Field(
        description="Path to log file", default=environment_log_file
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
        stats = manager.get_os_stats()
        logger.debug(f"OS stats: {stats}")
        return stats
    except Exception as e:
        logger.error(f"Failed to get OS stats: {str(e)}")
        return {"success": False, "error": f"Unexpected error: {str(e)}"}


@mcp.tool(
    annotations={
        "title": "Get Hardware Statistics",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
    tags={"system_management"},
)
async def get_hardware_statistics(
    silent: Optional[bool] = Field(
        description="Suppress output", default=environment_silent
    ),
    log_file: Optional[str] = Field(
        description="Path to log file", default=environment_log_file
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
        stats = manager.get_hardware_stats()
        logger.debug(f"Hardware stats: {stats}")
        return stats
    except Exception as e:
        logger.error(f"Failed to get hardware stats: {str(e)}")
        return {"success": False, "error": f"Unexpected error: {str(e)}"}


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
        description="Suppress output", default=environment_silent
    ),
    log_file: Optional[str] = Field(
        description="Path to log file", default=environment_log_file
    ),
    ctx: Context = Field(
        description="MCP context for progress reporting", default=None
    ),
) -> List[Dict]:
    """Lists all Windows features and their status (Windows only)."""
    logger = logging.getLogger("SystemsManager")
    logger.debug(f"Listing Windows features, silent: {silent}, log_file: {log_file}")

    try:
        manager = detect_and_create_manager(silent, log_file)
        if not isinstance(manager, WindowsManager):
            return {
                "success": False,
                "error": "Feature listing is only available on Windows",
            }

        features = manager.list_windows_features()
        logger.debug(f"Windows features: {features}")
        return features
    except Exception as e:
        logger.error(f"Failed to list Windows features: {str(e)}")
        return {"success": False, "error": f"Unexpected error: {str(e)}"}


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
        description="Suppress output", default=environment_silent
    ),
    log_file: Optional[str] = Field(
        description="Path to log file", default=environment_log_file
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
        description="Suppress output", default=environment_silent
    ),
    log_file: Optional[str] = Field(
        description="Path to log file", default=environment_log_file
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


def systems_manager_mcp(argv):
    transport = "stdio"
    host = "0.0.0.0"
    port = 8000
    try:
        opts, args = getopt.getopt(
            argv,
            "ht:h:p:",
            ["help", "transport=", "host=", "port="],
        )
    except getopt.GetoptError:
        logger = logging.getLogger("SystemsManager")
        logger.error("Incorrect arguments")
        sys.exit(2)
    for opt, arg in opts:
        if opt in ("-h", "--help"):
            sys.exit()
        elif opt in ("-t", "--transport"):
            transport = arg
        elif opt in ("-h", "--host"):
            host = arg
        elif opt in ("-p", "--port"):
            try:
                port = int(arg)
                if not (0 <= port <= 65535):
                    print(f"Error: Port {arg} is out of valid range (0-65535).")
                    sys.exit(1)
            except ValueError:
                print(f"Error: Port {arg} is not a valid integer.")
                sys.exit(1)
    if transport == "stdio":
        mcp.run(transport="stdio")
    elif transport == "http":
        mcp.run(transport="http", host=host, port=port)
    else:
        logger = logging.getLogger("SystemsManager")
        logger.error("Transport not supported")
        sys.exit(1)


def main():
    systems_manager_mcp(sys.argv[1:])


if __name__ == "__main__":
    systems_manager_mcp(sys.argv[1:])
