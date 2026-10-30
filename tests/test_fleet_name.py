"""CONN-SYSTEMS-MANAGER-CONNECTOR-IDENTITY-R001: the connector is filed under its fleet name, systems-manager-mcp."""

from __future__ import annotations

import ast
import tomllib
from pathlib import Path

import pytest
from scion_sdk.connector_identity import connector_name

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "systems_manager"
FLEET = "systems-manager-mcp"


def _call_connectors(path: Path) -> list[str]:
    names = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Call) and getattr(
            node.func, "id", getattr(node.func, "attr", "")
        ) in {
            "IngestBinding",
            "ConnectorContent",
        }:
            names += [
                str(k.value.value)
                for k in node.keywords
                if k.arg == "connector" and isinstance(k.value, ast.Constant)
            ]
    return names


@pytest.mark.spec("CONN-SYSTEMS-MANAGER-CONNECTOR-IDENTITY-R001")
def test_connector_name_is_the_fleet_name() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert pyproject["project"]["entry-points"]["scion_sdk.connector"] == {
        FLEET: "systems_manager:connector"
    }
    assert connector_name("systems_manager") == FLEET
    for module in sorted(PACKAGE.glob("*.py")):
        assert all(name == FLEET for name in _call_connectors(module)), module.name
