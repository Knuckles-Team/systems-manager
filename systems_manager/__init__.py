#!/usr/bin/env python
# coding: utf-8

from systems_manager.systems_manager import (
    SystemsManager,
    main,
    setup_logging,
    WindowsManager,
)
from systems_manager.systems_manager_mcp import systems_manager_mcp

"""
system-manager

Install/Update/Clean/Manage your System!
"""

__all__ = [
    "SystemsManager",
    "WindowsManager",
    "main",
    "setup_logging",
    "systems_manager_mcp",
]
