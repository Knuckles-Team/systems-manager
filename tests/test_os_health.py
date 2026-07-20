"""OS-health producer coverage for the required shared kernels and privacy boundary."""

from __future__ import annotations

import pytest

import systems_manager.os_health as oh


class _Usage:
    def __init__(self, percent: float) -> None:
        self.percent = percent


class _Partition:
    def __init__(self, mountpoint: str) -> None:
        self.mountpoint = mountpoint


class _FakeRunner:
    def __init__(self, which: dict | None = None, outputs: dict | None = None) -> None:
        self._which = which or {}
        self._outputs = outputs or {}

    def which(self, name: str) -> str | None:
        return self._which.get(name)

    def run(self, argv: list[str], *, check: bool = True) -> str:
        return self._outputs.get(argv[0], "")


def _boom(*_args, **_kwargs):
    raise OSError("simulated read failure")


def test_collect_os_signals_reads_injected_seam(monkeypatch):
    monkeypatch.setattr(oh.psutil, "disk_partitions", lambda all=False: [])
    monkeypatch.setattr(oh.psutil, "disk_usage", lambda path: _Usage(percent=42.0))
    monkeypatch.setattr(oh.psutil, "cpu_count", lambda: 4)
    monkeypatch.setattr(oh.os, "getloadavg", lambda: (2.0, 1.5, 1.0))
    monkeypatch.setattr(oh.psutil, "virtual_memory", lambda: _Usage(percent=55.0))
    monkeypatch.setattr(oh.psutil, "cpu_percent", lambda **_kwargs: 33.0)
    monkeypatch.setattr(oh.psutil, "boot_time", lambda: oh.time.time() - 86400 * 2)
    runner = _FakeRunner(
        which={"apt": "/usr/bin/apt", "journalctl": "/usr/bin/journalctl"},
        outputs={
            "apt": "Listing...\npkg1/stable 1.0\npkg2/stable 2.0\n",
            "journalctl": "err1\nerr2\nerr3\n",
        },
    )

    signals = oh.collect_os_signals(runner=runner)

    assert signals["disk_pct"] == 42.0
    assert signals["load_per_core"] == 0.5
    assert signals["pending_updates"] == 2.0
    assert signals["log_error_rate"] == round(3 / 15, 3)
    assert signals["uptime_days"] == 2.0


def test_collect_os_signals_worst_partition_wins(monkeypatch):
    monkeypatch.setattr(
        oh.psutil,
        "disk_partitions",
        lambda all=False: [_Partition("/"), _Partition("/data")],
    )
    usages = {"/": _Usage(percent=20.0), "/data": _Usage(percent=91.0)}
    monkeypatch.setattr(oh.psutil, "disk_usage", lambda path: usages[path])

    assert oh.collect_os_signals(runner=_FakeRunner())["disk_pct"] == 91.0


def test_collect_os_signals_skips_unreadable(monkeypatch):
    monkeypatch.setattr(oh.psutil, "disk_partitions", _boom)
    monkeypatch.setattr(oh.psutil, "disk_usage", _boom)
    monkeypatch.setattr(oh.os, "getloadavg", _boom)
    monkeypatch.setattr(oh.psutil, "virtual_memory", _boom)
    monkeypatch.setattr(oh.psutil, "cpu_percent", _boom)
    monkeypatch.setattr(oh.psutil, "boot_time", _boom)

    assert oh.collect_os_signals(runner=_FakeRunner()) == {}


class _FakeBuffer:
    instances = 0

    def __init__(self, **_kwargs) -> None:
        _FakeBuffer.instances += 1
        self.calls = 0

    def add(self, value, **_kwargs):
        self.calls += 1
        if self.calls < 3:
            return None
        return {
            "min": value,
            "max": value,
            "avg": value,
            "avg_control": None,
            "samples": self.calls,
            "window_s": 3600,
        }


def test_sample_and_ingest_distills_and_uses_opaque_ref(monkeypatch):
    oh._BUFFERS.clear()
    _FakeBuffer.instances = 0
    monkeypatch.setattr(oh, "HealthTrendBuffer", _FakeBuffer)
    monkeypatch.setattr(
        oh, "collect_os_signals", lambda host=None, **kw: {"disk_pct": 50.0}
    )
    ingested: list[dict] = []
    monkeypatch.setattr(
        oh,
        "ingest_health_trend",
        lambda **kw: ingested.append(kw) or {"nodes": 1, "edges": 1},
    )

    for _ in range(3):
        result = oh.sample_and_ingest(node_ref="deployment-node")

    expected_ref = oh._host_ref("deployment-node")
    assert len(ingested) == 1
    assert ingested[0]["entity_id"] == f"systems:host:{expected_ref}"
    assert ingested[0]["host"] == expected_ref
    assert _FakeBuffer.instances == 1
    assert result["node_ref"] == expected_ref
    assert "deployment-node" not in repr(result)


def test_sample_and_ingest_disabled_by_config(monkeypatch):
    monkeypatch.setenv("SYSTEMS_MANAGER_HEALTH_INGEST", "false")
    monkeypatch.setattr(
        oh, "collect_os_signals", lambda host=None, **kw: {"disk_pct": 50.0}
    )
    called = []
    monkeypatch.setattr(oh, "ingest_health_trend", lambda **kw: called.append(kw))

    result = oh.sample_and_ingest(node_ref="deployment-node")

    assert result["ingested"] is False
    assert called == []
    assert "deployment-node" not in repr(result)


def test_run_os_derivation_uses_only_opaque_refs(monkeypatch):
    source_ref = "deployment-node"
    opaque_ref = oh._host_ref(source_ref)
    trends = [{"avg": value} for value in (10, 20, 30, 40, 50, 60)]

    monkeypatch.setattr(
        oh,
        "read_health_trends",
        lambda entity_id, signal, days=14: (
            trends
            if entity_id == f"systems:host:{opaque_ref}" and signal == "disk_pct"
            else []
        ),
    )
    monkeypatch.setattr(
        oh,
        "compute_baseline",
        lambda values, **kwargs: (
            {"p50": 30.0, "p95": 45.0} if len(values) >= 6 else None
        ),
    )
    monkeypatch.setattr(
        oh,
        "detect_anomaly",
        lambda recent, baseline, **kwargs: (
            {
                "kind": "above-baseline",
                "zscore": 9.9,
                "observed": recent[-1]["avg"],
                "expected": baseline["p50"],
            }
            if baseline and recent
            else None
        ),
    )
    monkeypatch.setattr(oh, "correlate", lambda anomalies, total, **kwargs: anomalies)
    monkeypatch.setattr(oh, "ingest_health_baseline", lambda *args, **kwargs: None)
    monkeypatch.setattr(oh, "ingest_health_anomaly", lambda *args, **kwargs: None)
    notifications: list[str] = []
    monkeypatch.setattr(oh, "_notify", notifications.append)

    result = oh.run_os_derivation([source_ref])

    assert result["nodes"] == 1
    assert result["results"][opaque_ref]["disk_pct"]["trends"] == 6
    assert source_ref not in repr(result)
    assert notifications and opaque_ref in notifications[0]


@pytest.mark.parametrize(
    "url",
    [
        "http://notify.example.invalid/hook",
        "https://user:secret@notify.example.invalid/hook",
        "https://notify.example.invalid/hook?token=secret",
    ],
)
def test_notification_url_rejects_unsafe_boundaries(url):
    with pytest.raises(ValueError):
        oh._validated_notify_url(url)
