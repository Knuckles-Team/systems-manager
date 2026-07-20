"""MCP tool registration modules for systems-manager.

Functions are imported from os_provider_tools.py and agent_os_tools.py.
"""

from systems_manager.agent_os_tools import (
    register_agent_health_tools,
    register_identity_tools,
    register_specialist_registry_tools,
    register_watchdog_tools,
)
from systems_manager.os_provider_tools import register_os_provider_tools

__all__ = [
    "register_os_provider_tools",
    "register_agent_health_tools",
    "register_identity_tools",
    "register_specialist_registry_tools",
    "register_watchdog_tools",
]
