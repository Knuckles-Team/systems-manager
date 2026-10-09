"""Governed, privacy-preserving host telemetry ingestion coverage.

Exercises the real ``ingest_entities``/``ingest_host_inventory`` seam against a fake
``agent_connector_sdk.ingest`` transport (no engine required). The real SDK request
builder still runs underneath systems-manager's own node/relationship allow-list, so
both layers of validation are exercised.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from agent_connector_sdk.ingest import KnowledgeIngest
from epistemic_graph.generated.source_ingestion import SourceIngestionRequest

import systems_manager.kg_ingest as kg


class _FakeTransport:
    """Records every submitted request; no epistemic-graph engine required."""

    def __init__(self) -> None:
        self.requests: list[SourceIngestionRequest] = []

    async def source_status(self, _connector: str, _stream: str) -> Any:
        return SimpleNamespace(accepted_checkpoint=None)

    async def submit(self, request: SourceIngestionRequest) -> Any:
        self.requests.append(request)
        return SimpleNamespace(
            affected_count=len(request.records),
            relationship_count=len(request.relationships),
        )

    async def store_blob(self, _data: bytes) -> str:
        raise AssertionError("systems-manager host telemetry carries no media")


@pytest.fixture
def ingest() -> tuple[KnowledgeIngest, _FakeTransport]:
    transport = _FakeTransport()
    return KnowledgeIngest(transport, loop=None), transport


async def test_ingest_entities_uses_canonical_native_boundary(ingest):
    service, transport = ingest
    result = await kg.ingest_entities(
        [
            {"id": "systems:host:host:example", "node_type": "HardwareNode"},
            {"id": "systems:nic:interface:example", "node_type": "NetworkInterface"},
        ],
        [
            {
                "source": "systems:host:host:example",
                "target": "systems:nic:interface:example",
                "relationship": "hasInterface",
            }
        ],
        ingest=service,
    )

    assert result == {"nodes": 2, "edges": 1}
    request = transport.requests[0]
    record_ids = {record.record_id for record in request.records}
    assert record_ids == {
        "systems:host:host:example",
        "systems:nic:interface:example",
    }
    assert request.relationships[0].relation_reference.endswith(
        "resources/HardwareNode/relations/hasInterface"
    )


async def test_ingest_host_inventory_maps_only_opaque_identifiers(ingest):
    service, transport = ingest
    report = {
        "host": "deployment-local-name",
        "os": {
            "system": "Linux",
            "release": "6.0.0",
            "version": "generic-build",
            "machine": "x86_64",
            "processor": "generic-processor",
        },
        "hardware": {"cpu_count": 16, "memory": {"total": 34359738368}},
        "interfaces": [
            {
                "interface_ref": "interface:source-ref",
                "is_up": True,
                "speed": 1000,
                "mtu": 1500,
                "address_families": ["AddressFamily.AF_INET"],
            }
        ],
        "disks": [
            {
                "disk_ref": "disk:source-ref",
                "fstype": "ext4",
                "total": 500107862016,
                "used": 100000000000,
                "free": 400107862016,
                "percent": 20.0,
            }
        ],
    }

    result = await kg.ingest_host_inventory(report, ingest=service)

    assert result == {"nodes": 3, "edges": 2}
    request = transport.requests[0]
    host = next(
        r for r in request.records if r.mapping_reference.endswith("HardwareNode")
    )
    nic = next(
        r for r in request.records if r.mapping_reference.endswith("NetworkInterface")
    )
    disk = next(
        r for r in request.records if r.mapping_reference.endswith("DiskVolume")
    )
    assert host.payload["externalToolId"].startswith("host:")
    assert nic.payload["externalToolId"].startswith("interface:")
    assert disk.payload["externalToolId"].startswith("disk:")
    assert all(rel.relation_reference for rel in request.relationships)

    rendered = repr(request)
    for sensitive in (
        "deployment-local-name",
        "hostname",
        "ipAddress",
        "macAddress",
        "mountpoint",
    ):
        assert sensitive not in rendered


async def test_ingest_host_inventory_defaults_to_opaque_local_ref(ingest):
    service, transport = ingest
    result = await kg.ingest_host_inventory({"host": None}, ingest=service)

    assert result == {"nodes": 1, "edges": 0}
    host = transport.requests[0].records[0]
    assert host.record_id.startswith("systems:host:host:")
    assert "localhost" not in repr(host)


async def test_empty_projection_is_an_explicit_zero_write(ingest):
    service, transport = ingest
    assert await kg.ingest_entities([], ingest=service) == {"nodes": 0, "edges": 0}
    assert transport.requests == []
    with pytest.raises(ValueError, match="report must be an object"):
        await kg.ingest_host_inventory("not-a-dict", ingest=service)


async def test_native_boundary_rejects_unclassified_content(ingest):
    service, transport = ingest
    with pytest.raises(ValueError, match="invalid node"):
        await kg.ingest_entities(
            [
                {
                    "id": "systems:host:opaque",
                    "node_type": "HardwareNode",
                    "hostname": "must-not-persist",
                }
            ],
            ingest=service,
        )
    assert transport.requests == []
