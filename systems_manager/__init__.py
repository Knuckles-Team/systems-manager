#!/usr/bin/env python
# coding: utf-8

from systems_manager.systems_manager import (
    SystemsManagerBase,
    main,
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
    "main",
    "systems_manager_mcp",
    "detect_and_create_manager",
]
