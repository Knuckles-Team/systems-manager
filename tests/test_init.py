"""Tests for the strict package-root import surface."""

import systems_manager
from systems_manager.systems_manager import (
    SystemsManagerBase,
    detect_and_create_manager,
)


def test_package_root_has_no_dynamic_compatibility_exports():
    assert not hasattr(systems_manager, "_MCP_AVAILABLE")
    assert not hasattr(systems_manager, "_AGENT_AVAILABLE")
    assert not hasattr(systems_manager, "detect_and_create_manager")
    assert not hasattr(systems_manager, "SystemsManagerBase")


def test_current_core_module_exports_are_available():
    assert SystemsManagerBase.__module__ == "systems_manager.systems_manager"
    assert detect_and_create_manager.__module__ == "systems_manager.systems_manager"
