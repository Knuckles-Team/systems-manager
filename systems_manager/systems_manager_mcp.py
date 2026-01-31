#!/usr/bin/env python
# coding: utf-8

import argparse
import os
import sys
import logging
import requests
from typing import Optional, Dict, List, Union, Any
from pydantic import Field
from starlette.requests import Request
from starlette.responses import JSONResponse
from fastmcp import FastMCP, Context
from fastmcp.server.auth.oidc_proxy import OIDCProxy
from fastmcp.server.auth import OAuthProxy, RemoteAuthProvider
from fastmcp.server.auth.providers.jwt import JWTVerifier, StaticTokenVerifier
from fastmcp.server.middleware.logging import LoggingMiddleware
from fastmcp.server.middleware.timing import TimingMiddleware
from fastmcp.server.middleware.rate_limiting import RateLimitingMiddleware
from fastmcp.server.middleware.error_handling import ErrorHandlingMiddleware

from eunomia_mcp.middleware import EunomiaMcpMiddleware
from fastmcp.utilities.logging import get_logger
from systems_manager.utils import to_integer, to_boolean
from systems_manager.middlewares import UserTokenMiddleware, JWTClaimsLoggingMiddleware
from systems_manager.systems_manager import (
    detect_and_create_manager,
    WindowsManager,
)

__version__ = "1.1.25"

logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = get_logger("SystemsManagerServer")

config = {
    "enable_delegation": to_boolean(os.environ.get("ENABLE_DELEGATION", "False")),
    "audience": os.environ.get("AUDIENCE", None),
    "delegated_scopes": os.environ.get("DELEGATED_SCOPES", "api"),
    "token_endpoint": None,  # Will be fetched dynamically from OIDC config
    "oidc_client_id": os.environ.get("OIDC_CLIENT_ID", None),
    "oidc_client_secret": os.environ.get("OIDC_CLIENT_SECRET", None),
    "oidc_config_url": os.environ.get("OIDC_CONFIG_URL", None),
    "jwt_jwks_uri": os.getenv("FASTMCP_SERVER_AUTH_JWT_JWKS_URI", None),
    "jwt_issuer": os.getenv("FASTMCP_SERVER_AUTH_JWT_ISSUER", None),
    "jwt_audience": os.getenv("FASTMCP_SERVER_AUTH_JWT_AUDIENCE", None),
    "jwt_algorithm": os.getenv("FASTMCP_SERVER_AUTH_JWT_ALGORITHM", None),
    "jwt_secret": os.getenv("FASTMCP_SERVER_AUTH_JWT_PUBLIC_KEY", None),
    "jwt_required_scopes": os.getenv("FASTMCP_SERVER_AUTH_JWT_REQUIRED_SCOPES", None),
}

DEFAULT_TRANSPORT = os.getenv("TRANSPORT", "stdio")
DEFAULT_HOST = os.getenv("HOST", "0.0.0.0")
DEFAULT_PORT = to_integer(string=os.getenv("PORT", "8000"))


def register_tools(mcp: FastMCP):
    @mcp.custom_route("/health", methods=["GET"])
    async def health_check(request: Request) -> JSONResponse:
        return JSONResponse({"status": "OK"})

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
        tags={"system_management"},
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
        tags={"system_management"},
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
        tags={"system_management"},
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
        tags={"system_management"},
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

            # Approximate steps based on fonts
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
        tags={"system_management"},
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

            total_steps = 2  # add and refresh/update
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
                    # 1-based indexing for view_range typically? Let's assume 1-based to match editors
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
                new_content = content.replace(
                    old_str, new_str or "", 1
                )  # Replace first occurrence only? Anthropic usually implies uniqueness or single block
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
                # Insert AFTER the line? Or AT? Anthropic usually 0-indexed or 1-indexed? Assume 1-based
                idx = max(0, insert_line)
                # If idx is 0, insert at start?
                # Let's append
                new_lines = file_text.splitlines(keepends=True)
                # handle missing newlines
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


def systems_manager_mcp():
    print(f"systems_manager_mcp v{__version__}")
    parser = argparse.ArgumentParser(description="System Manager MCP Utility")
    parser.add_argument(
        "-t",
        "--transport",
        default=DEFAULT_TRANSPORT,
        choices=["stdio", "streamable-http", "sse"],
        help="Transport method: 'stdio', 'streamable-http', or 'sse' [legacy] (default: stdio)",
    )
    parser.add_argument(
        "-s",
        "--host",
        default=DEFAULT_HOST,
        help="Host address for HTTP transport (default: 0.0.0.0)",
    )
    parser.add_argument(
        "-p",
        "--port",
        type=int,
        default=DEFAULT_PORT,
        help="Port number for HTTP transport (default: 8000)",
    )
    parser.add_argument(
        "--auth-type",
        default="none",
        choices=["none", "static", "jwt", "oauth-proxy", "oidc-proxy", "remote-oauth"],
        help="Authentication type for MCP server: 'none' (disabled), 'static' (internal), 'jwt' (external token verification), 'oauth-proxy', 'oidc-proxy', 'remote-oauth' (external) (default: none)",
    )
    # JWT/Token params
    parser.add_argument(
        "--token-jwks-uri", default=None, help="JWKS URI for JWT verification"
    )
    parser.add_argument(
        "--token-issuer", default=None, help="Issuer for JWT verification"
    )
    parser.add_argument(
        "--token-audience", default=None, help="Audience for JWT verification"
    )
    parser.add_argument(
        "--token-algorithm",
        default=os.getenv("FASTMCP_SERVER_AUTH_JWT_ALGORITHM"),
        choices=[
            "HS256",
            "HS384",
            "HS512",
            "RS256",
            "RS384",
            "RS512",
            "ES256",
            "ES384",
            "ES512",
        ],
        help="JWT signing algorithm (required for HMAC or static key). Auto-detected for JWKS.",
    )
    parser.add_argument(
        "--token-secret",
        default=os.getenv("FASTMCP_SERVER_AUTH_JWT_PUBLIC_KEY"),
        help="Shared secret for HMAC (HS*) or PEM public key for static asymmetric verification.",
    )
    parser.add_argument(
        "--token-public-key",
        default=os.getenv("FASTMCP_SERVER_AUTH_JWT_PUBLIC_KEY"),
        help="Path to PEM public key file or inline PEM string (for static asymmetric keys).",
    )
    parser.add_argument(
        "--required-scopes",
        default=os.getenv("FASTMCP_SERVER_AUTH_JWT_REQUIRED_SCOPES"),
        help="Comma-separated list of required scopes (e.g., gitlab.read,gitlab.write).",
    )
    # OAuth Proxy params
    parser.add_argument(
        "--oauth-upstream-auth-endpoint",
        default=None,
        help="Upstream authorization endpoint for OAuth Proxy",
    )
    parser.add_argument(
        "--oauth-upstream-token-endpoint",
        default=None,
        help="Upstream token endpoint for OAuth Proxy",
    )
    parser.add_argument(
        "--oauth-upstream-client-id",
        default=None,
        help="Upstream client ID for OAuth Proxy",
    )
    parser.add_argument(
        "--oauth-upstream-client-secret",
        default=None,
        help="Upstream client secret for OAuth Proxy",
    )
    parser.add_argument(
        "--oauth-base-url", default=None, help="Base URL for OAuth Proxy"
    )
    # OIDC Proxy params
    parser.add_argument(
        "--oidc-config-url", default=None, help="OIDC configuration URL"
    )
    parser.add_argument("--oidc-client-id", default=None, help="OIDC client ID")
    parser.add_argument("--oidc-client-secret", default=None, help="OIDC client secret")
    parser.add_argument("--oidc-base-url", default=None, help="Base URL for OIDC Proxy")
    # Remote OAuth params
    parser.add_argument(
        "--remote-auth-servers",
        default=None,
        help="Comma-separated list of authorization servers for Remote OAuth",
    )
    parser.add_argument(
        "--remote-base-url", default=None, help="Base URL for Remote OAuth"
    )
    # Common
    parser.add_argument(
        "--allowed-client-redirect-uris",
        default=None,
        help="Comma-separated list of allowed client redirect URIs",
    )
    # Eunomia params
    parser.add_argument(
        "--eunomia-type",
        default="none",
        choices=["none", "embedded", "remote"],
        help="Eunomia authorization type: 'none' (disabled), 'embedded' (built-in), 'remote' (external) (default: none)",
    )
    parser.add_argument(
        "--eunomia-policy-file",
        default="mcp_policies.json",
        help="Policy file for embedded Eunomia (default: mcp_policies.json)",
    )
    parser.add_argument(
        "--eunomia-remote-url", default=None, help="URL for remote Eunomia server"
    )
    # Delegation params
    parser.add_argument(
        "--enable-delegation",
        action="store_true",
        default=to_boolean(os.environ.get("ENABLE_DELEGATION", "False")),
        help="Enable OIDC token delegation",
    )
    parser.add_argument(
        "--audience",
        default=os.environ.get("AUDIENCE", None),
        help="Audience for the delegated token",
    )
    parser.add_argument(
        "--delegated-scopes",
        default=os.environ.get("DELEGATED_SCOPES", "api"),
        help="Scopes for the delegated token (space-separated)",
    )
    parser.add_argument(
        "--openapi-file",
        default=None,
        help="Path to the OpenAPI JSON file to import additional tools from",
    )
    parser.add_argument(
        "--openapi-base-url",
        default=None,
        help="Base URL for the OpenAPI client (overrides instance URL)",
    )
    parser.add_argument(
        "--openapi-use-token",
        action="store_true",
        help="Use the incoming Bearer token (from MCP request) to authenticate OpenAPI import",
    )

    parser.add_argument(
        "--openapi-username",
        default=os.getenv("OPENAPI_USERNAME"),
        help="Username for basic auth during OpenAPI import",
    )

    parser.add_argument(
        "--openapi-password",
        default=os.getenv("OPENAPI_PASSWORD"),
        help="Password for basic auth during OpenAPI import",
    )

    parser.add_argument(
        "--openapi-client-id",
        default=os.getenv("OPENAPI_CLIENT_ID"),
        help="OAuth client ID for OpenAPI import",
    )

    parser.add_argument(
        "--openapi-client-secret",
        default=os.getenv("OPENAPI_CLIENT_SECRET"),
        help="OAuth client secret for OpenAPI import",
    )

    args = parser.parse_args()

    if args.port < 0 or args.port > 65535:
        print(f"Error: Port {args.port} is out of valid range (0-65535).")
        sys.exit(1)

    # Update config with CLI arguments
    config["enable_delegation"] = args.enable_delegation
    config["audience"] = args.audience or config["audience"]
    config["delegated_scopes"] = args.delegated_scopes or config["delegated_scopes"]
    config["oidc_config_url"] = args.oidc_config_url or config["oidc_config_url"]
    config["oidc_client_id"] = args.oidc_client_id or config["oidc_client_id"]
    config["oidc_client_secret"] = (
        args.oidc_client_secret or config["oidc_client_secret"]
    )

    # Configure delegation if enabled
    if config["enable_delegation"]:
        if args.auth_type != "oidc-proxy":
            logger.error("Token delegation requires auth-type=oidc-proxy")
            sys.exit(1)
        if not config["audience"]:
            logger.error("audience is required for delegation")
            sys.exit(1)
        if not all(
            [
                config["oidc_config_url"],
                config["oidc_client_id"],
                config["oidc_client_secret"],
            ]
        ):
            logger.error(
                "Delegation requires complete OIDC configuration (oidc-config-url, oidc-client-id, oidc-client-secret)"
            )
            sys.exit(1)

        # Fetch OIDC configuration to get token_endpoint
        try:
            logger.info(
                "Fetching OIDC configuration",
                extra={"oidc_config_url": config["oidc_config_url"]},
            )
            oidc_config_resp = requests.get(config["oidc_config_url"])
            oidc_config_resp.raise_for_status()
            oidc_config = oidc_config_resp.json()
            config["token_endpoint"] = oidc_config.get("token_endpoint")
            if not config["token_endpoint"]:
                logger.error("No token_endpoint found in OIDC configuration")
                raise ValueError("No token_endpoint found in OIDC configuration")
            logger.info(
                "OIDC configuration fetched successfully",
                extra={"token_endpoint": config["token_endpoint"]},
            )
        except Exception as e:
            print(f"Failed to fetch OIDC configuration: {e}")
            logger.error(
                "Failed to fetch OIDC configuration",
                extra={"error_type": type(e).__name__, "error_message": str(e)},
            )
            sys.exit(1)

    # Set auth based on type
    auth = None
    allowed_uris = (
        args.allowed_client_redirect_uris.split(",")
        if args.allowed_client_redirect_uris
        else None
    )

    if args.auth_type == "none":
        auth = None
    elif args.auth_type == "static":
        auth = StaticTokenVerifier(
            tokens={
                "test-token": {"client_id": "test-user", "scopes": ["read", "write"]},
                "admin-token": {"client_id": "admin", "scopes": ["admin"]},
            }
        )
    elif args.auth_type == "jwt":
        # Fallback to env vars if not provided via CLI
        jwks_uri = args.token_jwks_uri or os.getenv("FASTMCP_SERVER_AUTH_JWT_JWKS_URI")
        issuer = args.token_issuer or os.getenv("FASTMCP_SERVER_AUTH_JWT_ISSUER")
        audience = args.token_audience or os.getenv("FASTMCP_SERVER_AUTH_JWT_AUDIENCE")
        algorithm = args.token_algorithm
        secret_or_key = args.token_secret or args.token_public_key
        public_key_pem = None

        if not (jwks_uri or secret_or_key):
            logger.error(
                "JWT auth requires either --token-jwks-uri or --token-secret/--token-public-key"
            )
            sys.exit(1)
        if not (issuer and audience):
            logger.error("JWT requires --token-issuer and --token-audience")
            sys.exit(1)

        # Load static public key from file if path is given
        if args.token_public_key and os.path.isfile(args.token_public_key):
            try:
                with open(args.token_public_key, "r") as f:
                    public_key_pem = f.read()
                logger.info(f"Loaded static public key from {args.token_public_key}")
            except Exception as e:
                print(f"Failed to read public key file: {e}")
                logger.error(f"Failed to read public key file: {e}")
                sys.exit(1)
        elif args.token_public_key:
            public_key_pem = args.token_public_key  # Inline PEM

        # Validation: Conflicting options
        if jwks_uri and (algorithm or secret_or_key):
            logger.warning(
                "JWKS mode ignores --token-algorithm and --token-secret/--token-public-key"
            )

        # HMAC mode
        if algorithm and algorithm.startswith("HS"):
            if not secret_or_key:
                logger.error(f"HMAC algorithm {algorithm} requires --token-secret")
                sys.exit(1)
            if jwks_uri:
                logger.error("Cannot use --token-jwks-uri with HMAC")
                sys.exit(1)
            public_key = secret_or_key
        else:
            public_key = public_key_pem

        # Required scopes
        required_scopes = None
        if args.required_scopes:
            required_scopes = [
                s.strip() for s in args.required_scopes.split(",") if s.strip()
            ]

        try:
            auth = JWTVerifier(
                jwks_uri=jwks_uri,
                public_key=public_key,
                issuer=issuer,
                audience=audience,
                algorithm=(
                    algorithm if algorithm and algorithm.startswith("HS") else None
                ),
                required_scopes=required_scopes,
            )
            logger.info(
                "JWTVerifier configured",
                extra={
                    "mode": (
                        "JWKS"
                        if jwks_uri
                        else (
                            "HMAC"
                            if algorithm and algorithm.startswith("HS")
                            else "Static Key"
                        )
                    ),
                    "algorithm": algorithm,
                    "required_scopes": required_scopes,
                },
            )
        except Exception as e:
            print(f"Failed to initialize JWTVerifier: {e}")
            logger.error(f"Failed to initialize JWTVerifier: {e}")
            sys.exit(1)
    elif args.auth_type == "oauth-proxy":
        if not (
            args.oauth_upstream_auth_endpoint
            and args.oauth_upstream_token_endpoint
            and args.oauth_upstream_client_id
            and args.oauth_upstream_client_secret
            and args.oauth_base_url
            and args.token_jwks_uri
            and args.token_issuer
            and args.token_audience
        ):
            print(
                "oauth-proxy requires oauth-upstream-auth-endpoint, oauth-upstream-token-endpoint, "
                "oauth-upstream-client-id, oauth-upstream-client-secret, oauth-base-url, token-jwks-uri, "
                "token-issuer, token-audience"
            )
            logger.error(
                "oauth-proxy requires oauth-upstream-auth-endpoint, oauth-upstream-token-endpoint, "
                "oauth-upstream-client-id, oauth-upstream-client-secret, oauth-base-url, token-jwks-uri, "
                "token-issuer, token-audience",
                extra={
                    "auth_endpoint": args.oauth_upstream_auth_endpoint,
                    "token_endpoint": args.oauth_upstream_token_endpoint,
                    "client_id": args.oauth_upstream_client_id,
                    "base_url": args.oauth_base_url,
                    "jwks_uri": args.token_jwks_uri,
                    "issuer": args.token_issuer,
                    "audience": args.token_audience,
                },
            )
            sys.exit(1)
        token_verifier = JWTVerifier(
            jwks_uri=args.token_jwks_uri,
            issuer=args.token_issuer,
            audience=args.token_audience,
        )
        auth = OAuthProxy(
            upstream_authorization_endpoint=args.oauth_upstream_auth_endpoint,
            upstream_token_endpoint=args.oauth_upstream_token_endpoint,
            upstream_client_id=args.oauth_upstream_client_id,
            upstream_client_secret=args.oauth_upstream_client_secret,
            token_verifier=token_verifier,
            base_url=args.oauth_base_url,
            allowed_client_redirect_uris=allowed_uris,
        )
    elif args.auth_type == "oidc-proxy":
        if not (
            args.oidc_config_url
            and args.oidc_client_id
            and args.oidc_client_secret
            and args.oidc_base_url
        ):
            logger.error(
                "oidc-proxy requires oidc-config-url, oidc-client-id, oidc-client-secret, oidc-base-url",
                extra={
                    "config_url": args.oidc_config_url,
                    "client_id": args.oidc_client_id,
                    "base_url": args.oidc_base_url,
                },
            )
            sys.exit(1)
        auth = OIDCProxy(
            config_url=args.oidc_config_url,
            client_id=args.oidc_client_id,
            client_secret=args.oidc_client_secret,
            base_url=args.oidc_base_url,
            allowed_client_redirect_uris=allowed_uris,
        )
    elif args.auth_type == "remote-oauth":
        if not (
            args.remote_auth_servers
            and args.remote_base_url
            and args.token_jwks_uri
            and args.token_issuer
            and args.token_audience
        ):
            logger.error(
                "remote-oauth requires remote-auth-servers, remote-base-url, token-jwks-uri, token-issuer, token-audience",
                extra={
                    "auth_servers": args.remote_auth_servers,
                    "base_url": args.remote_base_url,
                    "jwks_uri": args.token_jwks_uri,
                    "issuer": args.token_issuer,
                    "audience": args.token_audience,
                },
            )
            sys.exit(1)
        auth_servers = [url.strip() for url in args.remote_auth_servers.split(",")]
        token_verifier = JWTVerifier(
            jwks_uri=args.token_jwks_uri,
            issuer=args.token_issuer,
            audience=args.token_audience,
        )
        auth = RemoteAuthProvider(
            token_verifier=token_verifier,
            authorization_servers=auth_servers,
            base_url=args.remote_base_url,
        )

    # === 2. Build Middleware List ===
    middlewares: List[
        Union[
            UserTokenMiddleware,
            ErrorHandlingMiddleware,
            RateLimitingMiddleware,
            TimingMiddleware,
            LoggingMiddleware,
            JWTClaimsLoggingMiddleware,
            EunomiaMcpMiddleware,
        ]
    ] = [
        ErrorHandlingMiddleware(include_traceback=True, transform_errors=True),
        RateLimitingMiddleware(max_requests_per_second=10.0, burst_capacity=20),
        TimingMiddleware(),
        LoggingMiddleware(),
        JWTClaimsLoggingMiddleware(),
    ]
    if config["enable_delegation"] or args.auth_type == "jwt":
        middlewares.insert(0, UserTokenMiddleware(config=config))  # Must be first

    if args.eunomia_type in ["embedded", "remote"]:
        try:
            from eunomia_mcp import create_eunomia_middleware

            policy_file = args.eunomia_policy_file or "mcp_policies.json"
            eunomia_endpoint = (
                args.eunomia_remote_url if args.eunomia_type == "remote" else None
            )
            eunomia_mw = create_eunomia_middleware(
                policy_file=policy_file, eunomia_endpoint=eunomia_endpoint
            )
            middlewares.append(eunomia_mw)
            logger.info(f"Eunomia middleware enabled ({args.eunomia_type})")
        except Exception as e:
            print(f"Failed to load Eunomia middleware: {e}")
            logger.error("Failed to load Eunomia middleware", extra={"error": str(e)})
            sys.exit(1)

    mcp = FastMCP(name="SystemsManagerMCP", auth=auth)
    register_tools(mcp)

    for mw in middlewares:
        mcp.add_middleware(mw)

    print("\nStarting Systems Manager MCP Server")
    print(f"  Transport: {args.transport.upper()}")
    print(f"  Auth: {args.auth_type}")
    print(f"  Delegation: {'ON' if config['enable_delegation'] else 'OFF'}")
    print(f"  Eunomia: {args.eunomia_type}")

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
    systems_manager_mcp()
