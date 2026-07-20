"""Tests for the package CLI entry point."""

from unittest.mock import Mock

import systems_manager.__main__ as main_module


def test_package_main_delegates_to_core_cli(monkeypatch):
    cli = Mock()
    monkeypatch.setattr(main_module, "main", cli)

    main_module.main()

    cli.assert_called_once_with()
