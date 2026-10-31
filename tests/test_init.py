"""Tests for the strict package-root import surface."""

from systems_manager.systems_manager import (
    SystemsManagerBase,
    detect_and_create_manager,
)


def test_current_core_module_exports_are_available():
    assert SystemsManagerBase.__module__ == "systems_manager.systems_manager"
    assert detect_and_create_manager.__module__ == "systems_manager.systems_manager"
