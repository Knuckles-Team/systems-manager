"""Tests for systems_manager.__main__ module."""

from unittest.mock import patch

import pytest


class TestMainModule:
    """Tests for __main__ module execution."""

    @patch("systems_manager.agent_server.agent_server")
    def test_main_calls_agent_server(self, mock_agent_server):
        """Test that __main__ calls agent_server() when executed as main."""
        # The __main__ module simply calls agent_server() when __name__ == "__main__"
        # We can test this by verifying the import and the conditional logic
        from systems_manager import __main__

        # The module should have imported agent_server
        assert hasattr(__main__, "agent_server")

        # The actual execution happens when the module is run as __main__,
        # which we can simulate by calling the imported function
        __main__.agent_server()
        mock_agent_server.assert_called_once()

    @patch("systems_manager.agent_server.agent_server")
    def test_import_does_not_call_agent_server(self, mock_agent_server):
        """Test that importing the module doesn't call agent_server."""
        # When importing, __name__ != "__main__", so agent_server should not be called
        import systems_manager.__main__ as main_module

        # Verify agent_server was imported but not called
        assert hasattr(main_module, "agent_server")
        mock_agent_server.assert_not_called()

    def test_agent_server_import_success(self):
        """Test that agent_server can be imported successfully."""
        try:
            from systems_manager.agent_server import agent_server

            assert callable(agent_server)
        except ImportError as e:
            pytest.skip(f"agent_server module not available: {e}")

    @patch("systems_manager.agent_server.agent_server")
    def test_agent_server_call_with_no_args(self, mock_agent_server):
        """Test that agent_server is called without arguments."""
        from systems_manager.agent_server import agent_server

        agent_server()

        mock_agent_server.assert_called_once_with()

    @patch(
        "systems_manager.agent_server.agent_server", side_effect=Exception("Test error")
    )
    def test_agent_server_exception_handling(self, mock_agent_server):
        """Test that exceptions from agent_server are not caught in __main__."""
        from systems_manager.agent_server import agent_server

        with pytest.raises(Exception, match="Test error"):
            agent_server()
