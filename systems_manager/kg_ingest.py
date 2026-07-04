"""Native epistemic-graph ingestion for host telemetry (typed graph nodes).

CONCEPT:AU-KG.ingest.enterprise-source-extractor. The package natively pushes the
infrastructure state it discovers over its manager seam into the epistemic-graph knowledge
graph as **typed OWL nodes** (``:HardwareNode``, ``:NetworkInterface``, ``:DiskVolume``) +
containment links, using the lightweight engine client (``GraphComputeEngine()._client`` +
``txn``) — the same fast client the blob ``MediaStore`` uses, NOT the heavy in-process
ingestion engine.

Everything is dependency-/engine-guarded: with no agent-utilities KG stack or no reachable
engine, every entry point **no-ops** (returns ``None``), so the connector keeps working with
zero KG infrastructure. The shared primitive
``agent_utilities.knowledge_graph.memory.native_ingest`` is preferred when present; when it
is not yet installed a self-contained txn fallback writes the same nodes/edges. Nodes carry
the shared provenance (``domain``/``source``) and match the classes federated by
``systems_manager.ontology``.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("systems_manager.kg")

_SOURCE = "systems-manager"
_DOMAIN = "systems"


def _client() -> tuple[Any | None, str]:
    """Return ``(engine_client, graph_name)`` or ``(None, "")`` when unavailable."""
    try:
        from agent_utilities.knowledge_graph.core.graph_compute import (
            GraphComputeEngine,
        )
    except Exception as e:  # noqa: BLE001 — KG stack absent
        logger.debug("KG ingest unavailable (import): %s", e)
        return None, ""
    try:
        engine = GraphComputeEngine()
        client = getattr(engine, "_client", None)
        if client is None:
            return None, ""
        graph = getattr(engine, "graph_name", None) or "__commons__"
        return client, graph
    except Exception as e:  # noqa: BLE001 — engine unreachable
        logger.debug("KG ingest: engine unreachable: %s", e)
        return None, ""


def ingest_entities(
    entities: list[dict[str, Any]],
    relationships: list[dict[str, Any]] | None = None,
    *,
    source: str = _SOURCE,
    domain: str = _DOMAIN,
    client: Any | None = None,
    graph: str | None = None,
) -> dict[str, int] | None:
    """Write typed nodes (+ edges) into epistemic-graph via the fast engine client.

    Prefers the shared ``native_ingest`` primitive; falls back to a self-contained txn
    when it is not installed. ``entities``: ``[{"id":..., "type":..., ...props}]``.
    ``relationships``: ``[{"source":id, "target":id, "type":rel}]``. Returns
    ``{"nodes":n, "edges":m}`` or ``None`` (no engine / failure; never raises).
    ``client``/``graph`` may be injected (tests); otherwise resolved on demand.
    """
    entities = [e for e in (entities or []) if e.get("id")]
    if not entities:
        return None

    # Preferred path: the shared fleet primitive (when installed and no injected client).
    if client is None:
        try:
            from agent_utilities.knowledge_graph.memory.native_ingest import (
                ingest_entities as _shared_ingest,
            )

            return _shared_ingest(entities, relationships, source=source, domain=domain)
        except Exception as e:  # noqa: BLE001 — primitive absent -> local fallback
            logger.debug("native_ingest primitive unavailable: %s", e)

    # Self-contained fallback (also the injected-client test path).
    if client is None:
        client, graph = _client()
    if client is None:
        return None
    graph = graph or "__commons__"

    try:
        txn = client.txn.begin(graph=graph)
        for ent in entities:
            props = {k: v for k, v in ent.items() if k != "id" and v is not None}
            props.setdefault("source", source)
            props.setdefault("domain", domain)
            client.txn.add_node(txn, ent["id"], props)
        committed = client.txn.commit(txn)
    except Exception as e:  # noqa: BLE001 — engine/txn failure is non-fatal
        logger.warning("KG ingest: txn failed: %s", e)
        return None
    if not committed:
        logger.warning("KG ingest: txn not committed (conflict)")
        return None

    edges = 0
    for rel in relationships or []:
        try:
            client.edges.add(
                rel["source"], rel["target"], {"type": rel.get("type", "RELATED")}
            )
            edges += 1
        except Exception as e:  # noqa: BLE001 — pure edge link, best-effort
            logger.debug("KG ingest: edge skipped: %s", e)

    logger.info("KG ingest: wrote %d nodes, %d edges", len(entities), edges)
    return {"nodes": len(entities), "edges": edges}


def _host_slug(host: str | None) -> str:
    """Normalize an inventory host / target to a stable node-id slug."""
    return (host or "localhost").strip() or "localhost"


def _interface_entities(
    host_id: str, host_slug: str, interfaces: Any
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Map ``list_network_interfaces`` output → :NetworkInterface nodes + :hasInterface."""
    entities: list[dict[str, Any]] = []
    rels: list[dict[str, Any]] = []
    if not isinstance(interfaces, dict):
        return entities, rels
    for name, info in interfaces.items():
        info = info if isinstance(info, dict) else {}
        ips: list[str] = []
        mac: str | None = None
        for addr in info.get("addresses") or []:
            if not isinstance(addr, dict):
                continue
            family = str(addr.get("family") or "")
            value = addr.get("address")
            if not value:
                continue
            if "AF_PACKET" in family or "AF_LINK" in family:
                mac = value
            elif "AF_INET" in family:
                ips.append(value)
        nic_id = f"systems:nic:{host_slug}:{name}"
        entities.append(
            {
                "id": nic_id,
                "type": "NetworkInterface",
                "name": name,
                "ipAddress": ", ".join(ips) if ips else None,
                "macAddress": mac,
                "linkSpeed": info.get("speed"),
                "isUp": info.get("is_up"),
                "mtu": info.get("mtu"),
                "externalToolId": f"{host_slug}:{name}",
            }
        )
        rels.append({"source": host_id, "target": nic_id, "type": "hasInterface"})
    return entities, rels


def _disk_entities(
    host_id: str, host_slug: str, disks: Any
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Map ``list_disks`` output → :DiskVolume nodes + :hasVolume links."""
    entities: list[dict[str, Any]] = []
    rels: list[dict[str, Any]] = []
    if not isinstance(disks, list):
        return entities, rels
    for disk in disks:
        if not isinstance(disk, dict):
            continue
        device = disk.get("device") or disk.get("mountpoint")
        if not device:
            continue
        vol_id = f"systems:disk:{host_slug}:{device}"
        entities.append(
            {
                "id": vol_id,
                "type": "DiskVolume",
                "name": device,
                "mountpoint": disk.get("mountpoint"),
                "fstype": disk.get("fstype"),
                "capacityBytes": disk.get("total"),
                "usedBytes": disk.get("used"),
                "freeBytes": disk.get("free"),
                "percentUsed": disk.get("percent"),
                "externalToolId": f"{host_slug}:{device}",
            }
        )
        rels.append({"source": host_id, "target": vol_id, "type": "hasVolume"})
    return entities, rels


def ingest_host_inventory(
    report: dict[str, Any],
    *,
    client: Any | None = None,
    graph: str | None = None,
) -> dict[str, int] | None:
    """Map a host-telemetry report → :HardwareNode + :NetworkInterface + :DiskVolume.

    ``report`` shape (all keys optional besides being a dict)::

        {
          "host": "rw710" | None,          # inventory alias / target host (None -> localhost)
          "os": {system, release, version, machine, processor, ...},  # get_os_statistics
          "hardware": {cpu_count, memory: {total, ...}, ...},          # get_hardware_statistics
          "interfaces": {iface: {is_up, speed, mtu, addresses:[...]}}, # list_network_interfaces
          "disks": [{device, mountpoint, fstype, total, used, free, percent}],  # list_disks
        }

    Returns ``{"nodes":n, "edges":m}`` or ``None`` (no engine / empty).
    """
    if not isinstance(report, dict):
        return None
    host_slug = _host_slug(report.get("host"))
    host_id = f"systems:host:{host_slug}"

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
            "type": "HardwareNode",
            "name": host_slug,
            "hostname": report.get("hostname") or host_slug,
            "osVersion": os_version,
            "machineArch": os_info.get("machine"),
            "processor": os_info.get("processor"),
            "cpuCount": hw_info.get("cpu_count"),
            "memoryTotal": mem.get("total"),
            "externalToolId": host_slug,
        }
    ]
    relationships: list[dict[str, Any]] = []

    nic_ents, nic_rels = _interface_entities(
        host_id, host_slug, report.get("interfaces")
    )
    disk_ents, disk_rels = _disk_entities(host_id, host_slug, report.get("disks"))
    entities.extend(nic_ents)
    entities.extend(disk_ents)
    relationships.extend(nic_rels)
    relationships.extend(disk_rels)

    return ingest_entities(entities, relationships, client=client, graph=graph)
