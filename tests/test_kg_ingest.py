"""Governed, privacy-preserving host telemetry ingestion coverage."""

from __future__ import annotations

import pytest

import systems_manager.kg_ingest as kg


def _capture_native(monkeypatch):
    captured: dict = {}

    def ingest(entities, relationships, **kwargs):
        captured.update(
            entities=entities,
            relationships=relationships,
            kwargs=kwargs,
        )
        return {"nodes": len(entities), "edges": len(relationships or [])}

    monkeypatch.setattr(kg, "_native_ingest", ingest)
    return captured


def test_ingest_entities_uses_canonical_native_boundary(monkeypatch):
    captured = _capture_native(monkeypatch)
    result = kg.ingest_entities(
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
    )

    assert result == {"nodes": 2, "edges": 1}
    assert captured["kwargs"]["source"] == "systems-manager"
    assert captured["kwargs"]["domain"] == "systems"
    assert captured["entities"][0]["node_type"] == "HardwareNode"
    assert captured["relationships"][0]["relationship"] == "hasInterface"


def test_ingest_host_inventory_maps_only_opaque_identifiers(monkeypatch):
    captured = _capture_native(monkeypatch)
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

    result = kg.ingest_host_inventory(report)

    assert result == {"nodes": 3, "edges": 2}
    entities = captured["entities"]
    relationships = captured["relationships"]
    host = next(entity for entity in entities if entity["node_type"] == "HardwareNode")
    nic = next(
        entity for entity in entities if entity["node_type"] == "NetworkInterface"
    )
    disk = next(entity for entity in entities if entity["node_type"] == "DiskVolume")
    assert host["externalToolId"].startswith("host:")
    assert nic["externalToolId"].startswith("interface:")
    assert disk["externalToolId"].startswith("disk:")
    assert all("relationship" in relationship for relationship in relationships)

    rendered = repr(captured)
    for sensitive in (
        "deployment-local-name",
        "hostname",
        "ipAddress",
        "macAddress",
        "mountpoint",
    ):
        assert sensitive not in rendered


def test_ingest_host_inventory_defaults_to_opaque_local_ref(monkeypatch):
    captured = _capture_native(monkeypatch)
    result = kg.ingest_host_inventory({"host": None})

    assert result == {"nodes": 1, "edges": 0}
    host = captured["entities"][0]
    assert host["id"].startswith("systems:host:host:")
    assert "localhost" not in repr(host)


def test_empty_projection_is_an_explicit_zero_write(monkeypatch):
    captured = _capture_native(monkeypatch)
    assert kg.ingest_entities([]) == {"nodes": 0, "edges": 0}
    assert captured == {}
    with pytest.raises(ValueError, match="report must be an object"):
        kg.ingest_host_inventory("not-a-dict")


def test_native_boundary_rejects_unclassified_content(monkeypatch):
    captured = _capture_native(monkeypatch)
    with pytest.raises(ValueError, match="invalid node"):
        kg.ingest_entities(
            [
                {
                    "id": "systems:host:opaque",
                    "node_type": "HardwareNode",
                    "hostname": "must-not-persist",
                }
            ]
        )
    assert captured == {}
