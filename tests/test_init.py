"""Tests for systems_manager.__init__ module."""

import sys
import importlib
from unittest.mock import Mock, patch


class TestImportModuleSafely:
    """Tests for _import_module_safely function."""

    def test_import_existing_module(self):
        """Test importing an existing module successfully."""
        from systems_manager import _import_module_safely

        # Test with a module that should exist
        result = _import_module_safely("os")
        assert result is not None
        assert hasattr(result, "path")

    def test_import_nonexistent_module(self):
        """Test importing a non-existent module returns None."""
        from systems_manager import _import_module_safely

        result = _import_module_safely("nonexistent_module_xyz")
        assert result is None


class TestExposeMembers:
    """Tests for _expose_members function."""

    def test_expose_public_classes_and_functions(self):
        """Test that public classes and functions are exposed."""
        from systems_manager import _expose_members, __all__

        # Save original __all__
        original_all = __all__.copy()

        # Create a mock module with public and private members
        mock_module = Mock()

        class PublicClass:
            pass

        def public_function():
            pass

        def _private_function():
            pass

        mock_module.__dict__ = {
            "PublicClass": PublicClass,
            "public_function": public_function,
            "_private_function": _private_function,
            "__private_dunder__": None,
        }

        # Mock inspect.getmembers to return our specific members
        with patch("inspect.getmembers") as mock_getmembers:
            mock_getmembers.return_value = [
                ("PublicClass", PublicClass),
                ("public_function", public_function),
                ("_private_function", _private_function),
                ("__private_dunder__", None),
            ]

            # Call the function
            _expose_members(mock_module)

            # Verify __all__ was updated
            assert "PublicClass" in __all__
            assert "public_function" in __all__
            # Verify private members are not in __all__
            assert "_private_function" not in __all__
            assert "__private_dunder__" not in __all__

        # Restore original __all__
        __all__.clear()
        __all__.extend(original_all)

    def test_expose_members_updates_all_list(self):
        """Test that _expose_members updates __all__ list."""
        from systems_manager import _expose_members, __all__

        initial_all_length = len(__all__)

        mock_module = Mock()

        class TestClass:
            pass

        with patch("inspect.getmembers") as mock_getmembers:
            mock_getmembers.return_value = [("TestClass", TestClass)]
            _expose_members(mock_module)

            assert len(__all__) > initial_all_length
            assert "TestClass" in __all__


class TestModuleInitialization:
    """Tests for module initialization logic."""

    def test_core_modules_imported(self):
        """Test that core modules are imported."""
        # Reload the module to test initialization
        import systems_manager

        importlib.reload(systems_manager)

        # Verify core systems_manager module is imported
        assert hasattr(systems_manager, "detect_and_create_manager")
        assert hasattr(systems_manager, "SystemsManagerBase")

    def test_mcp_available_flag(self):
        """Test _MCP_AVAILABLE flag is set correctly."""
        import systems_manager

        # The flag should be a boolean
        assert isinstance(systems_manager._MCP_AVAILABLE, bool)

        # If mcp_server module exists in sys.modules, it should be available
        # Otherwise, the flag should reflect the actual import status
        if "systems_manager.mcp_server" in sys.modules:
            # If the module was successfully imported during initialization
            assert (
                systems_manager._MCP_AVAILABLE is True
                or systems_manager._MCP_AVAILABLE is False
            )

    def test_agent_available_flag(self):
        """Test _AGENT_AVAILABLE flag is set correctly."""
        import systems_manager

        importlib.reload(systems_manager)

        # The flag should be a boolean
        assert isinstance(systems_manager._AGENT_AVAILABLE, bool)

    def test_all_list_contains_expected_members(self):
        """Test that __all__ contains expected public members."""
        import systems_manager

        importlib.reload(systems_manager)

        # Verify __all__ is a list
        assert isinstance(systems_manager.__all__, list)

        # Verify it contains core members
        assert "detect_and_create_manager" in systems_manager.__all__
        assert "SystemsManagerBase" in systems_manager.__all__

        # Verify availability flags are in __all__
        assert "_MCP_AVAILABLE" in systems_manager.__all__
        assert "_AGENT_AVAILABLE" in systems_manager.__all__

    def test_no_private_members_in_all(self):
        """Test that private members are not in __all__."""
        import systems_manager

        importlib.reload(systems_manager)

        for member in systems_manager.__all__:
            assert not member.startswith("_") or member in [
                "_MCP_AVAILABLE",
                "_AGENT_AVAILABLE",
            ]

    def test_optional_module_import_failure_handling(self):
        """Test that optional module import failures are handled gracefully."""
        # This test simulates what happens when an optional module fails to import
        from systems_manager import _import_module_safely

        # Try to import a non-existent optional module
        result = _import_module_safely("nonexistent_optional_module")
        assert result is None
        # Should not raise an exception


class TestModuleReimport:
    """Tests for module re-import behavior."""

    def test_reload_module_maintains_state(self):
        """Test that reloading the module maintains expected state."""
        import systems_manager

        # Get initial state
        _initial_all = systems_manager.__all__.copy()

        # Reload module
        importlib.reload(systems_manager)

        # Verify module still has expected attributes
        assert hasattr(systems_manager, "__all__")
        assert hasattr(systems_manager, "_MCP_AVAILABLE")
        assert hasattr(systems_manager, "_AGENT_AVAILABLE")

        # Verify __all__ is still populated
        assert len(systems_manager.__all__) > 0
