"""Tests for the OS-layer health producer (``systems_manager.os_health``) — Phase B
of the unified infra-intelligence plan (``reports/unified-infra-intelligence-plan.md``).

Mirrors ``fan_manager/tests/test_kg_control.py``'s shape: pure sampling via an
injected seam, the distill-not-per-sample buffer, an end-to-end derivation pass
against a fake KG, and the guarded-import no-op path. Because ``os_health`` never
reimplements the shared kernels (it only *consumes*
``agent_utilities.observability.health``/``health_ingest``), the shared symbols
are monkeypatched directly onto the module for deterministic, environment-
independent coverage of the orchestration (not the kernel maths, which is
agent-utilities' own test surface).
"""

from __future__ import annotations

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


# --- collect_os_signals ------------------------------------------------------ #
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
    assert signals["mem_pct"] == 55.0
    assert signals["cpu_pct"] == 33.0
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
    runner = _FakeRunner()
    signals = oh.collect_os_signals(runner=runner)
    assert signals["disk_pct"] == 91.0


def test_collect_os_signals_skips_unreadable(monkeypatch):
    monkeypatch.setattr(oh.psutil, "disk_partitions", _boom)
    monkeypatch.setattr(oh.psutil, "disk_usage", _boom)
    monkeypatch.setattr(oh.os, "getloadavg", _boom)
    monkeypatch.setattr(oh.psutil, "virtual_memory", _boom)
    monkeypatch.setattr(oh.psutil, "cpu_percent", _boom)
    monkeypatch.setattr(oh.psutil, "boot_time", _boom)
    runner = _FakeRunner()  # which() returns None for every tool -> apt/journalctl skip
    assert oh.collect_os_signals(runner=runner) == {}


def test_collect_os_signals_never_raises_without_runner_tools(monkeypatch):
    # No apt/journalctl on PATH -> those two signals are simply absent, not an error.
    monkeypatch.setattr(oh.psutil, "disk_partitions", lambda all=False: [])
    monkeypatch.setattr(oh.psutil, "disk_usage", lambda path: _Usage(percent=1.0))
    signals = oh.collect_os_signals(runner=_FakeRunner())
    assert "pending_updates" not in signals
    assert "log_error_rate" not in signals


# --- distill-to-trend buffer: one trend per window, never per sample --------- #
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


def test_sample_and_ingest_distills_not_per_sample(monkeypatch):
    oh._BUFFERS.clear()
    _FakeBuffer.instances = 0
    monkeypatch.setattr(oh, "_HAS_SHARED_HEALTH", True)
    monkeypatch.setattr(oh, "HealthTrendBuffer", _FakeBuffer, raising=False)
    monkeypatch.setattr(
        oh, "collect_os_signals", lambda host=None, **kw: {"disk_pct": 50.0}
    )
    ingested: list[dict] = []
    monkeypatch.setattr(
        oh,
        "ingest_health_trend",
        lambda **kw: ingested.append(kw) or {"nodes": 1, "edges": 1},
        raising=False,
    )

    for _ in range(3):
        result = oh.sample_and_ingest(host="h1")

    # only the 3rd pass crossed the buffer's window -> exactly one :HealthTrend write
    assert len(ingested) == 1
    assert ingested[0]["signal"] == "disk_pct"
    assert ingested[0]["entity_id"] == "systems:host:h1"
    assert ingested[0]["layer"] == "os"
    # the buffer is created ONCE per (host, signal) and reused across passes
    assert _FakeBuffer.instances == 1
    assert result["ingested"] is True
    assert result["flushed"][0]["signal"] == "disk_pct"


def test_sample_and_ingest_disabled_by_env(monkeypatch):
    monkeypatch.setenv("SYSTEMS_MANAGER_HEALTH_INGEST", "false")
    monkeypatch.setattr(oh, "_HAS_SHARED_HEALTH", True)
    monkeypatch.setattr(
        oh, "collect_os_signals", lambda host=None, **kw: {"disk_pct": 50.0}
    )
    called = []
    monkeypatch.setattr(
        oh, "ingest_health_trend", lambda **kw: called.append(kw), raising=False
    )
    result = oh.sample_and_ingest(host="h1")
    assert result["ingested"] is False
    assert result["signals"] == {"disk_pct": 50.0}
    assert called == []


# --- guarded-import no-op path (shared kernels absent) ----------------------- #
def test_module_imports_cleanly_regardless_of_shared_health():
    # The guarded import must never raise, whether or not the shared kernels are
    # installed; _HAS_SHARED_HEALTH just reports which path is active.
    assert isinstance(oh._HAS_SHARED_HEALTH, bool)


def test_sample_and_ingest_noop_when_shared_health_absent(monkeypatch):
    monkeypatch.setattr(oh, "_HAS_SHARED_HEALTH", False)
    monkeypatch.setattr(
        oh, "collect_os_signals", lambda host=None, **kw: {"disk_pct": 10.0}
    )
    result = oh.sample_and_ingest(host="h1")
    assert result["ingested"] is False
    assert result["signals"] == {"disk_pct": 10.0}
    assert result["reason"] == "shared health kernels unavailable"


def test_run_os_derivation_noop_when_shared_health_absent(monkeypatch):
    monkeypatch.setattr(oh, "_HAS_SHARED_HEALTH", False)
    assert oh.run_os_derivation(["h1"]) == {"hosts": 0, "results": {}}


# --- run_os_derivation: end-to-end against a fake KG -------------------------- #
def test_run_os_derivation_end_to_end(monkeypatch):
    monkeypatch.setattr(oh, "_HAS_SHARED_HEALTH", True)

    h1_disk_trends = [{"avg": v} for v in (10, 20, 30, 40, 50, 60)]

    def fake_read_health_trends(entity_id, signal, *, days=14):
        host = entity_id.rsplit(":", 1)[-1]
        if host == "h1" and signal == "disk_pct":
            return h1_disk_trends
        return []

    def fake_compute_baseline(trends, *, value_key, min_windows=6, **_kwargs):
        if len(trends) < min_windows:
            return None
        return {
            "p50": 30.0,
            "p95": 45.0,
            "min_env": 10.0,
            "max_env": 60.0,
            "avg_control": None,
            "inertia": None,
            "windows": len(trends),
        }

    def fake_detect_anomaly(recent, baseline, *, value_key, **_kw):
        if not baseline or not recent:
            return None
        observed = recent[-1][value_key]
        if observed > baseline["p95"]:
            return {
                "kind": "above-baseline",
                "zscore": 9.9,
                "observed": observed,
                "expected": baseline["p50"],
            }
        return None

    correlate_calls = []

    def fake_correlate(anomalies, total, **_kwargs):
        correlate_calls.append((dict(anomalies), total))
        return anomalies

    baselines_written: list[tuple] = []
    anomalies_written: list[tuple] = []
    notified: list[str] = []

    monkeypatch.setattr(oh, "read_health_trends", fake_read_health_trends, raising=False)
    monkeypatch.setattr(oh, "compute_baseline", fake_compute_baseline, raising=False)
    monkeypatch.setattr(oh, "detect_anomaly", fake_detect_anomaly, raising=False)
    monkeypatch.setattr(oh, "correlate", fake_correlate, raising=False)
    monkeypatch.setattr(
        oh,
        "ingest_health_baseline",
        lambda eid, sig, b, **kw: baselines_written.append((eid, sig, b)),
        raising=False,
    )
    monkeypatch.setattr(
        oh,
        "ingest_health_anomaly",
        lambda eid, sig, a, **kw: anomalies_written.append((eid, sig, a)),
        raising=False,
    )
    monkeypatch.setattr(oh, "_notify", lambda msg: notified.append(msg))

    out = oh.run_os_derivation(["h1", "empty"], days=14)

    assert out["hosts"] == 2
    h1_disk = out["results"]["h1"]["disk_pct"]
    assert h1_disk["trends"] == 6
    assert h1_disk["baseline"]["p95"] == 45.0
    assert h1_disk["anomaly"]["kind"] == "above-baseline"

    empty_disk = out["results"]["empty"]["disk_pct"]
    assert empty_disk["trends"] == 0
    assert empty_disk["baseline"] is None
    assert empty_disk["anomaly"] is None

    # baseline/anomaly writes only happen where there was real history
    assert ("systems:host:h1", "disk_pct", h1_disk["baseline"]) in baselines_written
    assert not any(eid == "systems:host:empty" for eid, _, _ in baselines_written)
    assert ("systems:host:h1", "disk_pct", h1_disk["anomaly"]) in anomalies_written

    # correlate ran once per signal (report-only — never touched a host)
    assert len(correlate_calls) == len(oh.OS_SIGNALS)
    assert any(msg for msg in notified if "h1" in msg and "disk_pct" in msg)
