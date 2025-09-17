#!/usr/bin/env python
# coding: utf-8

from systems_manager.systems_manager import (
    SystemsManagerBase,
    systems_manager,
    WindowsManager,
    detect_and_create_manager,
    setup_logging,
)
from systems_manager.systems_manager_mcp import systems_manager_mcp

"""
system-manager

Install/Update/Clean/Manage your System!
"""

__all__ = [
    "SystemsManagerBase",
    "WindowsManager",
    "setup_logging",
    "systems_manager_mcp",
    "systems_manager",
    "detect_and_create_manager",
]
