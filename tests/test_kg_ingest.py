"""Native epistemic-graph typed-node ingestion — Wire-First coverage.

Exercises the real ``ingest_entities`` / ``ingest_host_inventory`` seam with a fake engine
client (no engine required), asserting the txn add_node/commit + edge calls and the host
telemetry → :HardwareNode / :NetworkInterface / :DiskVolume mapping.
CONCEPT:AU-KG.ingest.enterprise-source-extractor.
"""

from __future__ import annotations

from systems_manager.kg_ingest import ingest_entities, ingest_host_inventory


class _FakeTxn:
    def __init__(self):
        self.nodes = {}
        self.committed = False

    def begin(self, graph=None):
        self.graph = graph
        return "txn-1"

    def add_node(self, txn, node_id, props):
        self.nodes[node_id] = props

    def commit(self, txn):
        self.committed = True
        return True


class _FakeEdges:
    def __init__(self):
        self.edges = []

    def add(self, src, dst, props):
        self.edges.append((src, dst, props))


class _FakeClient:
    def __init__(self):
        self.txn = _FakeTxn()
        self.edges = _FakeEdges()


def test_ingest_entities_writes_nodes_and_edges():
    c = _FakeClient()
    res = ingest_entities(
        [
            {"id": "a", "type": "HardwareNode", "name": "rw710"},
            {"id": "b", "type": "NetworkInterface"},
        ],
        [{"source": "a", "target": "b", "type": "hasInterface"}],
        client=c,
        graph="__commons__",
    )
    assert res == {"nodes": 2, "edges": 1}
    assert c.txn.committed is True
    assert set(c.txn.nodes) == {"a", "b"}
    # provenance is stamped
    assert c.txn.nodes["a"]["source"] == "systems-manager"
    assert c.txn.nodes["a"]["domain"] == "systems"
    assert c.edges.edges == [("a", "b", {"type": "hasInterface"})]


def test_ingest_host_inventory_maps_node_nics_and_disks():
    c = _FakeClient()
    report = {
        "host": "rw710",
        "os": {
            "system": "Linux",
            "release": "6.0.0",
            "version": "#1 SMP",
            "machine": "x86_64",
            "processor": "AMD",
        },
        "hardware": {"cpu_count": 16, "memory": {"total": 34359738368}},
        "interfaces": {
            "eth0": {
                "is_up": True,
                "speed": 1000,
                "mtu": 1500,
                "addresses": [
                    {"family": "AddressFamily.AF_INET", "address": "10.0.0.13"},
                    {
                        "family": "AddressFamily.AF_PACKET",
                        "address": "aa:bb:cc:dd:ee:ff",
                    },
                ],
            }
        },
        "disks": [
            {
                "device": "/dev/sda1",
                "mountpoint": "/",
                "fstype": "ext4",
                "total": 500107862016,
                "used": 100000000000,
                "free": 400107862016,
                "percent": 20.0,
            }
        ],
    }
    res = ingest_host_inventory(report, client=c, graph="__commons__")
    assert res == {"nodes": 3, "edges": 2}

    host = c.txn.nodes["systems:host:rw710"]
    assert host["type"] == "HardwareNode"
    assert host["osVersion"] == "Linux 6.0.0 #1 SMP"
    assert host["machineArch"] == "x86_64"
    assert host["cpuCount"] == 16
    assert host["memoryTotal"] == 34359738368
    assert host["externalToolId"] == "rw710"

    nic = c.txn.nodes["systems:nic:rw710:eth0"]
    assert nic["type"] == "NetworkInterface"
    assert nic["ipAddress"] == "10.0.0.13"
    assert nic["macAddress"] == "aa:bb:cc:dd:ee:ff"
    assert nic["linkSpeed"] == 1000
    assert nic["isUp"] is True

    disk = c.txn.nodes["systems:disk:rw710:/dev/sda1"]
    assert disk["type"] == "DiskVolume"
    assert disk["mountpoint"] == "/"
    assert disk["fstype"] == "ext4"
    assert disk["capacityBytes"] == 500107862016
    assert disk["percentUsed"] == 20.0

    assert (
        "systems:host:rw710",
        "systems:nic:rw710:eth0",
        {"type": "hasInterface"},
    ) in c.edges.edges
    assert (
        "systems:host:rw710",
        "systems:disk:rw710:/dev/sda1",
        {"type": "hasVolume"},
    ) in c.edges.edges


def test_ingest_host_inventory_defaults_to_localhost():
    c = _FakeClient()
    res = ingest_host_inventory({"host": None}, client=c, graph="__commons__")
    assert res == {"nodes": 1, "edges": 0}
    assert "systems:host:localhost" in c.txn.nodes


def test_ingest_noops_without_engine():
    # No injected client + no reachable engine -> clean no-op.
    assert ingest_entities([{"id": "a", "type": "HardwareNode"}]) is None


def test_ingest_empty_is_noop():
    assert ingest_entities([], client=_FakeClient()) is None
    # A non-dict report is a clean no-op (never raises).
    assert ingest_host_inventory("not-a-dict", client=_FakeClient()) is None
