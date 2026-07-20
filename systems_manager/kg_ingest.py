"""Native epistemic-graph ingestion for host telemetry (typed graph nodes).

CONCEPT:AU-KG.ingest.enterprise-source-extractor. The package natively pushes the
infrastructure state it discovers over its manager seam into the epistemic-graph knowledge
graph as **typed OWL nodes** (``:HardwareNode``, ``:NetworkInterface``, ``:DiskVolume``) +
containment links through the shared governed ChangeEnvelope ingestion boundary. There is
one write path: connectors never access raw engine transactions and ingestion failures are
explicit. Nodes carry shared provenance (``domain``/``source``) and match the classes
federated by ``systems_manager.ontology``.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import socket
from typing import Any

from agent_utilities.core.config import setting

logger = logging.getLogger("systems_manager.kg")

_SOURCE = "systems-manager"
_DOMAIN = "systems"
_ENTITY_FIELDS = {
    "HardwareNode": frozenset(
        {
            "id",
            "node_type",
            "osVersion",
            "machineArch",
            "processor",
            "cpuCount",
            "memoryTotal",
            "externalToolId",
        }
    ),
    "NetworkInterface": frozenset(
        {
            "id",
            "node_type",
            "linkSpeed",
            "isUp",
            "mtu",
            "addressFamilyCount",
            "externalToolId",
        }
    ),
    "DiskVolume": frozenset(
        {
            "id",
            "node_type",
            "fstype",
            "capacityBytes",
            "usedBytes",
            "freeBytes",
            "percentUsed",
            "externalToolId",
        }
    ),
}
_RELATIONSHIPS = frozenset({"hasInterface", "hasVolume"})


def _native_ingest(*args: Any, **kwargs: Any) -> dict[str, int]:
    """Resolve the governed engine boundary only for an authorized write."""

    from agent_utilities.knowledge_graph.memory.native_ingest import ingest_entities

    return ingest_entities(*args, **kwargs)


def ingest_entities(
    entities: list[dict[str, Any]],
    relationships: list[dict[str, Any]] | None = None,
    *,
    source: str = _SOURCE,
    domain: str = _DOMAIN,
    client: Any | None = None,
    graph: str | None = None,
) -> dict[str, int]:
    """Write typed nodes and edges through the governed native ingestion boundary.

    ``entities`` use canonical ``node_type`` and relationships use canonical
    ``relationship``. ``client`` and ``graph`` are accepted only for the shared
    boundary's authorized test seam; production graph authority comes from the session.
    """
    sanitized: list[dict[str, Any]] = []
    node_ids: set[str] = set()
    for entity in entities or []:
        if not isinstance(entity, dict):
            raise ValueError("Systems Manager projection contains an invalid node")
        node_type = entity.get("node_type")
        node_id = entity.get("id")
        allowed = _ENTITY_FIELDS.get(node_type)
        if (
            allowed is None
            or not isinstance(node_id, str)
            or not node_id.startswith("systems:")
            or set(entity) - allowed
        ):
            raise ValueError("Systems Manager projection contains an invalid node")
        if node_id not in node_ids:
            node_ids.add(node_id)
            sanitized.append(dict(entity))
    entities = sanitized
    if not entities:
        return {"nodes": 0, "edges": 0}
    sanitized_relationships: list[dict[str, Any]] = []
    for relationship in relationships or []:
        if not isinstance(relationship, dict) or set(relationship) != {
            "source",
            "target",
            "relationship",
        }:
            raise ValueError(
                "Systems Manager projection contains an invalid relationship"
            )
        relationship_source = relationship.get("source")
        relationship_target = relationship.get("target")
        kind = relationship.get("relationship")
        if (
            not isinstance(relationship_source, str)
            or not isinstance(relationship_target, str)
            or not isinstance(kind, str)
            or relationship_source not in node_ids
            or relationship_target not in node_ids
            or kind not in _RELATIONSHIPS
        ):
            raise ValueError(
                "Systems Manager projection contains an invalid relationship"
            )
        sanitized_relationships.append(dict(relationship))
    return _native_ingest(
        entities,
        sanitized_relationships,
        source=source,
        domain=domain,
        client=client,
        graph=graph,
    )


def _opaque_ref(namespace: str, value: str) -> str:
    configured = setting("SYSTEMS_MANAGER_PSEUDONYMIZATION_KEY", "")
    key = str(configured or "").encode()
    if len(key) < 32:
        raise RuntimeError(
            "Systems Manager ingestion requires a deployment pseudonymization key"
        )
    digest = hmac.new(
        key,
        f"systems-manager\x00{namespace}\x00{value}".encode(),
        hashlib.sha256,
    ).hexdigest()
    return f"{namespace}:{digest}"


def _host_ref(host: str | None) -> str:
    """Return a stable opaque host reference without persisting a local name."""
    configured = setting("SYSTEMS_MANAGER_NODE_REF")
    value = host or (configured if isinstance(configured, str) else None)
    value = value or socket.gethostname() or "local"
    return _opaque_ref("host", value)


def _interface_entities(
    host_id: str, host_ref: str, interfaces: Any
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Map ``list_network_interfaces`` output → :NetworkInterface nodes + :hasInterface."""
    entities: list[dict[str, Any]] = []
    rels: list[dict[str, Any]] = []
    if not isinstance(interfaces, list):
        return entities, rels
    for info in interfaces:
        info = info if isinstance(info, dict) else {}
        source_ref = info.get("interface_ref")
        if not isinstance(source_ref, str) or not source_ref:
            continue
        interface_ref = _opaque_ref("interface", source_ref)
        nic_id = f"systems:nic:{host_ref}:{interface_ref}"
        entities.append(
            {
                "id": nic_id,
                "node_type": "NetworkInterface",
                "linkSpeed": info.get("speed"),
                "isUp": info.get("is_up"),
                "mtu": info.get("mtu"),
                "addressFamilyCount": len(info.get("address_families") or []),
                "externalToolId": interface_ref,
            }
        )
        rels.append(
            {"source": host_id, "target": nic_id, "relationship": "hasInterface"}
        )
    return entities, rels


def _disk_entities(
    host_id: str, host_ref: str, disks: Any
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Map ``list_disks`` output → :DiskVolume nodes + :hasVolume links."""
    entities: list[dict[str, Any]] = []
    rels: list[dict[str, Any]] = []
    if not isinstance(disks, list):
        return entities, rels
    for disk in disks:
        if not isinstance(disk, dict):
            continue
        source_ref = disk.get("disk_ref")
        if not isinstance(source_ref, str) or not source_ref:
            continue
        disk_ref = _opaque_ref("disk", source_ref)
        vol_id = f"systems:disk:{host_ref}:{disk_ref}"
        entities.append(
            {
                "id": vol_id,
                "node_type": "DiskVolume",
                "fstype": disk.get("fstype"),
                "capacityBytes": disk.get("total"),
                "usedBytes": disk.get("used"),
                "freeBytes": disk.get("free"),
                "percentUsed": disk.get("percent"),
                "externalToolId": disk_ref,
            }
        )
        rels.append({"source": host_id, "target": vol_id, "relationship": "hasVolume"})
    return entities, rels


def ingest_host_inventory(
    report: dict[str, Any],
    *,
    client: Any | None = None,
    graph: str | None = None,
) -> dict[str, int]:
    """Map a host-telemetry report → :HardwareNode + :NetworkInterface + :DiskVolume.

    ``report`` shape (all keys optional besides being a dict)::

        {
          "host": "opaque-deployment-ref" | None,
          "os": {system, release, version, machine, processor, ...},  # get_os_statistics
          "hardware": {cpu_count, memory: {total, ...}, ...},          # get_hardware_statistics
          "interfaces": [{interface_ref, is_up, speed, mtu, address_families}],
          "disks": [{disk_ref, fstype, total, used, free, percent}],
        }

    Host, interface, and disk identifiers are one-way opaque references. Hostnames,
    addresses, hardware addresses, usernames, and filesystem paths are not persisted.
    Returns explicit committed node and edge counts.
    """
    if not isinstance(report, dict):
        raise ValueError("Systems Manager host report must be an object")
    host_ref = _host_ref(report.get("host"))
    host_id = f"systems:host:{host_ref}"

    os_info = report.get("os") if isinstance(report.get("os"), dict) else {}
    hw_info = report.get("hardware") if isinstance(report.get("hardware"), dict) else {}
    mem = hw_info.get("memory") if isinstance(hw_info.get("memory"), dict) else {}
    os_parts = [
        os_info.get("system"),
        os_info.get("release"),
        os_info.get("version"),
    ]
    os_version = " ".join(str(p) for p in os_parts if p) or None

    entities: list[dict[str, Any]] = [
        {
            "id": host_id,
            "node_type": "HardwareNode",
            "osVersion": os_version,
            "machineArch": os_info.get("machine"),
            "processor": os_info.get("processor"),
            "cpuCount": hw_info.get("cpu_count"),
            "memoryTotal": mem.get("total"),
            "externalToolId": host_ref,
        }
    ]
    relationships: list[dict[str, Any]] = []

    nic_ents, nic_rels = _interface_entities(
        host_id, host_ref, report.get("interfaces")
    )
    disk_ents, disk_rels = _disk_entities(host_id, host_ref, report.get("disks"))
    entities.extend(nic_ents)
    entities.extend(disk_ents)
    relationships.extend(nic_rels)
    relationships.extend(disk_rels)

    return ingest_entities(entities, relationships, client=client, graph=graph)
