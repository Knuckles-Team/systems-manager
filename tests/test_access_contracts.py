"""The host access contract binds fields returned by the served tool."""

import asyncio
import json
from pathlib import Path
from unittest.mock import patch

import pytest
from fastmcp import Client
from scion_sdk.access_contract import parse_access_contracts

from systems_manager.mcp_server import get_mcp_instance

ROOT = Path(__file__).resolve().parents[1]


class _FixtureManager:
    def get_host_record(self):
        return json.loads((ROOT / "tests/recordings/host.json").read_text())


@pytest.mark.spec("CONN-SYSTEMS-MANAGER-CONNECTOR-CONTENT-R002")
def test_competency_contracts_certified(monkeypatch):
    monkeypatch.setenv("SYSTEMS_MANAGER_ALLOW_SENSITIVE_READS", "true")
    text = (ROOT / "systems_manager/ontology/access_contracts.ttl").read_text()
    (contract,) = parse_access_contracts(text)
    recording = json.loads((ROOT / "tests/recordings/host.json").read_text())
    assert contract.operation == "sm_system_get_host_record"
    assert contract.key_field == "host_id"
    assert {field for _, field in contract.predicates} == {
        "pendingUpdates",
        "uptimeSeconds",
    }

    async def call():
        _, mcp, _ = get_mcp_instance()
        with patch(
            "systems_manager.mcp_server.detect_and_create_manager",
            return_value=_FixtureManager(),
        ):
            async with Client(mcp) as client:
                return await client.call_tool(
                    contract.operation, {}, raise_on_error=False
                )

    result = asyncio.run(call())
    assert not result.is_error
    record = json.loads(result.content[0].text)
    assert record == recording
    assert contract.key_field in record
    assert all(field in record for _, field in contract.predicates)
    assert "hostname" not in json.dumps(record).lower()
