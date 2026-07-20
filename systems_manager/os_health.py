"""OS-layer health producer — Phase B of the unified infra-intelligence plan
(``reports/unified-infra-intelligence-plan.md``). Samples each host's OS health
signals (disk/load/mem/CPU/pending-updates/log-error-rate/uptime), distills them
to lightweight per-window trends, learns per-host baselines, and flags anomalies —
the OS-layer twin of ``fan_manager.kg_control`` (the hardware/thermal reference
implementation) generalized via the shared fleet primitive.

CONCEPT:SM-OS.observability.os-health-producer. This module is a thin **producer**:
it emits named numeric signals into the shared kernels
(:mod:`agent_utilities.observability.health` / ``health_ingest``) and gets
trend/baseline/anomaly for free — no bespoke statistics live here. Sampling reuses
existing systems-manager telemetry code (``psutil`` the same way
``systems_manager.systems_manager.list_disks``/``system_health_check`` do) and a
``CommandRunner`` seam mirroring ``fan_manager.fan_manager.CommandRunner`` for the
two shell-outs (``apt``, ``journalctl``) so both are injectable/testable.

The shared ``agent_utilities.observability.health*`` kernels are the required runtime
contract and the only statistics implementation.

**Report-only by design.** This producer only observes and writes typed KG nodes;
it never mutates a host (no remediation, no config changes) — see the plan's
"report-only → approved → closed-loop" staging.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import socket
import subprocess
import time
from typing import Any, Protocol, runtime_checkable
from urllib.parse import urlsplit

import psutil
from agent_utilities.core.config import setting
from agent_utilities.core.http_client import create_http_client
from agent_utilities.core.transport_security import resolve_configured_tls_profile
from agent_utilities.observability.health import (
    HealthTrendBuffer,
    compute_baseline,
    correlate,
    detect_anomaly,
)
from agent_utilities.observability.health_ingest import (
    ingest_health_anomaly,
    ingest_health_baseline,
    ingest_health_trend,
    read_health_trends,
)

from systems_manager.kg_ingest import _opaque_ref

logger = logging.getLogger("systems_manager.os_health")

# The named OS signals this producer samples (CONCEPT:SM-OS.observability.os-health-producer).
OS_SIGNALS: tuple[str, ...] = (
    "disk_pct",
    "load_per_core",
    "mem_pct",
    "cpu_pct",
    "pending_updates",
    "log_error_rate",
    "uptime_days",
)

# Recent-window size (minutes) for the journald error-rate signal.
_LOG_ERROR_WINDOW_MIN = 15


# --------------------------------------------------------------------------- #
# command-runner seam (mirrors fan_manager.fan_manager.CommandRunner)          #
# --------------------------------------------------------------------------- #
@runtime_checkable
class CommandRunner(Protocol):
    """Seam for resolving and executing the local ``apt``/``journalctl`` binaries.

    Injecting this runner lets callers and tests substitute the shell-out without
    globally monkeypatching :mod:`subprocess`, matching the DI seam
    ``fan_manager.fan_manager.CommandRunner`` uses for hardware tools.
    """

    def which(self, name: str) -> str | None:
        """Resolve an executable on ``PATH`` (``None`` if absent)."""
        ...

    def run(self, argv: list[str], *, check: bool = True) -> str:
        """Run a fixed argv with ``shell=False`` and return captured stdout."""
        ...


class SubprocessCommandRunner:
    """Default :class:`CommandRunner` backed by ``shutil.which``/``subprocess.run``."""

    def which(self, name: str) -> str | None:
        return shutil.which(name)

    def run(self, argv: list[str], *, check: bool = True) -> str:
        # Fixed argv, shell=False: no user input reaches the command line.
        completed = subprocess.run(  # nosec B603 - fixed argv, no shell, no user input
            argv,
            capture_output=True,
            text=True,
            check=check,
        )
        return completed.stdout


_DEFAULT_RUNNER: CommandRunner = SubprocessCommandRunner()


def _host_ref(value: str | None) -> str:
    """Create a stable opaque node reference without persisting a hostname."""
    configured = setting("SYSTEMS_MANAGER_NODE_REF")
    raw = value or (configured if isinstance(configured, str) else None)
    raw = raw or socket.gethostname() or "local"
    return _opaque_ref("host", raw)


# --------------------------------------------------------------------------- #
# sampling — reuses systems-manager's existing psutil/apt/journalctl patterns  #
# --------------------------------------------------------------------------- #
def _worst_disk_pct() -> float | None:
    """Worst (highest) percent-used across mounted partitions — mirrors the
    ``psutil.disk_partitions``/``disk_usage`` loop in
    ``systems_manager.systems_manager.SystemsManagerBase.list_disks``."""
    worst: float | None = None
    try:
        partitions = psutil.disk_partitions(all=False)
    except Exception as e:  # noqa: BLE001 — sampling is best-effort
        logger.debug("disk_pct: disk_partitions failed: %s", e)
        partitions = []
    for part in partitions:
        try:
            usage = psutil.disk_usage(part.mountpoint)
        except Exception as exc:  # noqa: BLE001 — best-effort mount sampling
            logger.debug(
                "disk_pct: mount sample failed for %s: %s",
                part.mountpoint,
                type(exc).__name__,
            )
            continue
        if worst is None or usage.percent > worst:
            worst = float(usage.percent)
    if worst is not None:
        return worst
    try:
        return float(psutil.disk_usage("/").percent)
    except Exception as e:  # noqa: BLE001
        logger.debug("disk_pct unavailable: %s", e)
        return None


def _count_pending_updates(runner: CommandRunner) -> int | None:
    """Count of upgradable apt packages (``apt list --upgradable``)."""
    if runner.which("apt") is None:
        return None
    try:
        out = runner.run(["apt", "list", "--upgradable"], check=False)
    except Exception as e:  # noqa: BLE001 — sampling is best-effort
        logger.debug("pending_updates unavailable: %s", e)
        return None
    lines = [
        ln
        for ln in out.splitlines()
        if ln.strip() and "/" in ln and not ln.startswith("Listing...")
    ]
    return len(lines)


def _log_error_rate(runner: CommandRunner) -> float | None:
    """journald error-level entries per minute over the last
    :data:`_LOG_ERROR_WINDOW_MIN` minutes."""
    if runner.which("journalctl") is None:
        return None
    try:
        out = runner.run(
            [
                "journalctl",
                "-p",
                "err",
                "--since",
                f"-{_LOG_ERROR_WINDOW_MIN}min",
                "--no-pager",
                "-o",
                "cat",
            ],
            check=False,
        )
    except Exception as e:  # noqa: BLE001 — sampling is best-effort
        logger.debug("log_error_rate unavailable: %s", e)
        return None
    lines = [ln for ln in out.splitlines() if ln.strip()]
    return round(len(lines) / _LOG_ERROR_WINDOW_MIN, 3)


def collect_os_signals(
    host: str | None = None, *, runner: CommandRunner | None = None
) -> dict[str, float]:
    """Sample the LOCAL host's current OS health signals (CONCEPT:SM-OS.observability.os-health-producer).

    ``host`` is a label only (systems-manager runs this producer per-node, e.g. as
    a DaemonSet — there is no remote sampling here). Each signal is skipped (not
    raised) when it can't be read, so a partial environment still yields a partial
    reading rather than an empty one. Signals: ``disk_pct`` (worst mounted
    partition), ``load_per_core`` (1-min loadavg ÷ CPU count), ``mem_pct``,
    ``cpu_pct``, ``pending_updates`` (apt), ``log_error_rate`` (journald errors/min),
    ``uptime_days``.
    """
    del host  # sampling is always local; kept for a stable/explicit call signature
    runner = runner or _DEFAULT_RUNNER
    signals: dict[str, float] = {}

    disk_pct = _worst_disk_pct()
    if disk_pct is not None:
        signals["disk_pct"] = disk_pct

    try:
        cpu_count = psutil.cpu_count() or 1
        load1 = os.getloadavg()[0]
        signals["load_per_core"] = round(load1 / cpu_count, 3)
    except Exception as e:  # noqa: BLE001 — sampling is best-effort
        logger.debug("load_per_core unavailable: %s", e)

    try:
        signals["mem_pct"] = float(psutil.virtual_memory().percent)
    except Exception as e:  # noqa: BLE001
        logger.debug("mem_pct unavailable: %s", e)

    try:
        signals["cpu_pct"] = float(psutil.cpu_percent(interval=0.5))
    except Exception as e:  # noqa: BLE001
        logger.debug("cpu_pct unavailable: %s", e)

    pending = _count_pending_updates(runner)
    if pending is not None:
        signals["pending_updates"] = float(pending)

    error_rate = _log_error_rate(runner)
    if error_rate is not None:
        signals["log_error_rate"] = error_rate

    try:
        signals["uptime_days"] = round((time.time() - psutil.boot_time()) / 86400.0, 3)
    except Exception as e:  # noqa: BLE001
        logger.debug("uptime_days unavailable: %s", e)

    return signals


# --------------------------------------------------------------------------- #
# distill-to-trend — one HealthTrendBuffer per (host, signal); bounded writes  #
# --------------------------------------------------------------------------- #
_BUFFERS: dict[tuple[str, str], Any] = {}


def _buffer_for(node_ref: str, signal: str) -> Any:
    """Return the node/signal rolling :class:`HealthTrendBuffer`."""
    key = (node_ref, signal)
    buf = _BUFFERS.get(key)
    if buf is None:
        window_s = int(setting("SYSTEMS_MANAGER_HEALTH_AGGREGATE_S", 3600))
        buf = HealthTrendBuffer(window_s=window_s)
        _BUFFERS[key] = buf
    return buf


def _health_ingest_enabled() -> bool:
    return str(
        setting("SYSTEMS_MANAGER_HEALTH_INGEST", "true")
    ).strip().lower() not in {
        "0",
        "false",
        "no",
    }


def sample_and_ingest(
    node_ref: str | None = None, *, runner: CommandRunner | None = None
) -> dict[str, Any]:
    """One collection pass: collect → feed the per-signal trend buffers → ingest
    any flushed trends (CONCEPT:SM-OS.observability.os-health-producer).

    Idempotent and best-effort: a disabled toggle
    (``SYSTEMS_MANAGER_HEALTH_INGEST=false``) collects signals without writing.
    Bounded by design: a ``:HealthTrend`` node is written only when a buffer's
    aggregate window elapses, never per sample.
    """
    opaque_ref = _host_ref(node_ref)
    signals = collect_os_signals(opaque_ref, runner=runner)
    if not _health_ingest_enabled():
        return {
            "node_ref": opaque_ref,
            "signals": signals,
            "ingested": False,
            "flushed": [],
        }

    entity_id = f"systems:host:{opaque_ref}"
    flushed: list[dict[str, Any]] = []
    for signal, value in signals.items():
        buf = _buffer_for(opaque_ref, signal)
        trend = buf.add(value)
        if trend is None:
            continue
        result = ingest_health_trend(
            entity_id=entity_id,
            entity_type="Host",
            layer="os",
            signal=signal,
            trend=trend,
            host=opaque_ref,
        )
        flushed.append({"signal": signal, "trend": trend, "ingested": bool(result)})
        logger.info(
            "OS-health trend[%s]: %s avg=%s min=%s max=%s over %d samples",
            opaque_ref,
            signal,
            trend.get("avg"),
            trend.get("min"),
            trend.get("max"),
            trend.get("samples") or 0,
        )
    return {
        "node_ref": opaque_ref,
        "signals": signals,
        "ingested": True,
        "flushed": flushed,
    }


# --------------------------------------------------------------------------- #
# orchestration — one report-only derivation pass over opaque graph nodes      #
# --------------------------------------------------------------------------- #
def _node_refs_from_config() -> list[str]:
    raw = setting("SYSTEMS_MANAGER_NODE_REFS")
    if not isinstance(raw, str):
        return []
    return [value.strip() for value in raw.split(",") if value.strip()]


def _validated_notify_url(value: str) -> str:
    parsed = urlsplit(value)
    loopback = parsed.hostname in {"127.0.0.1", "::1", "localhost"}
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or (parsed.scheme != "https" and not loopback)
    ):
        raise ValueError(
            "Notification URL must be credential-free HTTPS or loopback HTTP"
        )
    return value


def _notify(message: str) -> None:
    """Best-effort push to the intelligent alert router
    (``SYSTEMS_MANAGER_NOTIFY_URL``), mirroring ``fan_manager.kg_control._notify``."""
    raw_url = setting("SYSTEMS_MANAGER_NOTIFY_URL")
    logger.info(message)
    if not isinstance(raw_url, str) or not raw_url:
        return
    tls_profile = None
    try:
        url = _validated_notify_url(raw_url)
        tls_profile = resolve_configured_tls_profile("systems-manager-notify")
        with create_http_client(
            timeout=5,
            **tls_profile.httpx_kwargs(),
        ) as client:
            response = client.post(
                url,
                json={"source": "systems-manager-health", "message": message},
            )
            response.raise_for_status()
    except Exception:  # noqa: BLE001 — notification is best-effort
        logger.debug("Configured notification delivery failed")
    finally:
        if tls_profile is not None:
            tls_profile.cleanup()


def run_os_derivation(
    node_refs: list[str] | None = None, *, days: int = 14
) -> dict[str, Any]:
    """One learn→flag pass over configured opaque node references.

    For each host×signal: reads recent ``:HealthTrend`` history, learns a
    ``:HealthBaseline``, and checks the recent tail for a ``:HealthAnomaly`` off
    that baseline. Anomalies simultaneous across a majority of hosts for the same
    signal are collapsed into one ``systemic`` OS-level cause (e.g. every host's
    disk filling together points at a shared root cause, not N independent
    faults). **Report-only** — no remediation, no host mutation; only writes
    typed KG nodes and a best-effort notification. Raw hostnames and inventory
    aliases are one-way transformed before graph reads, writes, logs, or responses.
    """
    source_refs = node_refs or _node_refs_from_config() or [None]
    opaque_refs = [_host_ref(value) for value in source_refs]
    results: dict[str, dict[str, Any]] = {node_ref: {} for node_ref in opaque_refs}
    anomalies_by_signal: dict[str, dict[str, dict[str, Any] | None]] = {
        signal: {} for signal in OS_SIGNALS
    }

    for node_ref in opaque_refs:
        entity_id = f"systems:host:{node_ref}"
        for signal in OS_SIGNALS:
            trends = read_health_trends(entity_id, signal, days=days) or []
            baseline = compute_baseline(trends, value_key="avg", peak_key="max")
            anomaly = detect_anomaly(trends[-3:], baseline, value_key="avg")
            anomalies_by_signal[signal][node_ref] = anomaly
            results[node_ref][signal] = {
                "trends": len(trends),
                "baseline": baseline,
                "anomaly": anomaly,
            }

    for _signal, anomalies in anomalies_by_signal.items():
        correlate(
            anomalies,
            len(opaque_refs),
            kind="above-baseline",
            systemic_kind="systemic",
        )

    for node_ref in opaque_refs:
        entity_id = f"systems:host:{node_ref}"
        seen_signals = 0
        for signal in OS_SIGNALS:
            data = results[node_ref][signal]
            baseline = data["baseline"]
            if baseline:
                ingest_health_baseline(entity_id, signal, baseline, entity_type="Host")
            anomaly = anomalies_by_signal[signal][node_ref]
            data["anomaly"] = anomaly
            if data["trends"]:
                seen_signals += 1
            if anomaly:
                ingest_health_anomaly(entity_id, signal, anomaly, entity_type="Host")
                _notify(
                    f"[systems-manager-health] {node_ref}: {signal} {anomaly['kind']} — "
                    f"observed={anomaly['observed']} expected={anomaly['expected']} "
                    f"(z={anomaly['zscore']})"
                )
        logger.info(
            "%s: %d/%d signals with history, %d anomal%s",
            node_ref,
            seen_signals,
            len(OS_SIGNALS),
            sum(1 for s in OS_SIGNALS if anomalies_by_signal[s][node_ref]),
            (
                "y"
                if sum(1 for s in OS_SIGNALS if anomalies_by_signal[s][node_ref]) == 1
                else "ies"
            ),
        )

    return {"nodes": len(opaque_refs), "results": results}


# --------------------------------------------------------------------------- #
# CLI entry points                                                              #
# --------------------------------------------------------------------------- #
def main_sample() -> None:
    """CLI (``systems-manager-health``): one collect+ingest pass; prints a JSON summary."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    summary = sample_and_ingest()
    print(json.dumps(summary, default=str, indent=2))


def main_derive() -> None:
    """CLI (``systems-manager-health-derive``): one derivation pass; prints a JSON summary."""
    import argparse

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    p = argparse.ArgumentParser(
        description="systems-manager OS-health derivation pass."
    )
    p.add_argument(
        "--days", type=int, default=14, help="trend lookback window (default 14)"
    )
    p.add_argument(
        "--node-refs",
        default="",
        help="comma-separated deployment node references",
    )
    args = p.parse_args()
    node_refs = [
        value.strip() for value in args.node_refs.split(",") if value.strip()
    ] or None
    summary = run_os_derivation(node_refs, days=args.days)
    print(json.dumps(summary, default=str, indent=2))


def main() -> None:
    """CLI: ``python -m systems_manager.os_health {sample|derive} [options]``
    (mirrors ``fan_manager.kg_control.main``); defaults to ``sample``."""
    import argparse

    p = argparse.ArgumentParser(description="systems-manager OS-health producer.")
    sub = p.add_subparsers(dest="command")
    sub.add_parser("sample", help="one collect+ingest pass (default)")
    derive_p = sub.add_parser(
        "derive", help="learn baselines + flag anomalies (report-only)"
    )
    derive_p.add_argument("--days", type=int, default=14)
    derive_p.add_argument(
        "--node-refs",
        default="",
        help="comma-separated deployment node references",
    )
    args = p.parse_args()

    if args.command == "derive":
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )
        node_refs = [
            value.strip() for value in args.node_refs.split(",") if value.strip()
        ] or None
        summary = run_os_derivation(node_refs, days=args.days)
    else:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )
        summary = sample_and_ingest()
    print(json.dumps(summary, default=str, indent=2))


if __name__ == "__main__":
    main()
