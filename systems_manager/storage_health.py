"""Physical storage + BMC drive-fault health (CONCEPT:SYS-1.4, SYS-1.5).

Extends systems-manager beyond filesystem usage into PHYSICAL disk health:

- **SMART** for every drive, including RAID controllers via the ``megaraid``
  passthrough (a single-disk VD hides its member behind the controller, so a
  plain ``smartctl /dev/sdX`` reads the array, not the disk).
- **BMC / IPMI drive-slot faults** — the controller's own "Drive Fault" sensor
  and System Event Log, which catch a disk that intermittently drops offline
  even when its SMART media is still clean.
- **RAID physical-disk state** via an in-band PERC/LSI CLI when present.

The three are **correlated** (CONCEPT:SYS-1.5): a bay the BMC flags as faulted
whose SMART media is clean is reported as a link/aging fault (reseat / replace),
not media wear — exactly the failure mode a plain ``smartctl PASSED`` misses.

Everything runs through the systems-manager manager seam (``manager.run_command``),
so it works against the LOCAL host or any inventory REMOTE host. BMC out-of-band
access (``target={host,user,password}``) is reused from the ``fan-manager`` IPMI
wrapper when available, with the credential read from OpenBao at runtime
(:mod:`systems_manager.bmc_credentials`); it degrades to a direct ``ipmitool``
shell-out through the manager otherwise.
"""

from __future__ import annotations

import logging
import re
from typing import Any

_log = logging.getLogger("SystemsManager.storage_health")

Target = dict[str, Any] | None

_INT_RE = re.compile(r"(-?\d[\d,]*)")
# Dell drive-bay IPMI sensors are numbered from a 0xa0 base: 0xaN ≈ physical slot N.
_BAY_BASE = 0xA0


def _run(
    manager: Any, cmd: list[str], *, elevated: bool = True
) -> tuple[bool, str, str]:
    """Run a command through the manager seam; return ``(ok, stdout, stderr)``."""
    try:
        res = manager.run_command(cmd, elevated=elevated)
    except Exception as e:  # noqa: BLE001 — surface as a failed result, never raise
        return False, "", str(e)
    out = (res.get("stdout") if hasattr(res, "get") else None) or ""
    err = (res.get("stderr") if hasattr(res, "get") else None) or ""
    ok = res.get("success") if hasattr(res, "get") else None
    if ok is None:
        ok = not err
    return bool(ok), out, err


def detect_raid_controllers(manager: Any) -> list[str]:
    """List storage/RAID controllers visible to the host (``lspci``)."""
    ok, out, _ = _run(manager, ["lspci"], elevated=False)
    if not ok:
        return []
    pat = re.compile(r"raid|megaraid|\blsi\b|sas\d|smart array|perc", re.I)
    return [ln.strip() for ln in out.splitlines() if pat.search(ln)]


def _to_int(s: str | None) -> int | None:
    if not s:
        return None
    m = _INT_RE.search(s)
    return int(m.group(1).replace(",", "")) if m else None


def _parse_smart(info: str, attrs: str, health: str) -> dict[str, Any]:
    def grab(text: str, label: str) -> str | None:
        m = re.search(rf"{label}\s*:\s*(.+)", text, re.I)
        return m.group(1).strip() if m else None

    def attr(name: str) -> int | None:
        m = re.search(rf"{name}.*?(\d[\d,]*)\s*$", attrs, re.M)
        return _to_int(m.group(1)) if m else None

    health_ok: bool | None = None
    if health:
        if re.search(r"PASSED|OK", health, re.I):
            health_ok = True
        elif re.search(r"FAIL", health, re.I):
            health_ok = False

    return {
        "model": grab(info, "Device Model")
        or grab(info, "Product")
        or grab(info, "Model Number"),
        "serial": grab(info, "Serial Number") or grab(info, "Serial number"),
        "capacity": grab(info, "User Capacity") or grab(info, "Total NVM Capacity"),
        "rotation": grab(info, "Rotation Rate"),
        "health_passed": health_ok,
        "power_on_hours": attr("Power_On_Hours"),
        "reallocated_sectors": attr("Reallocated_Sector_Ct"),
        "current_pending": attr("Current_Pending_Sector"),
        "offline_uncorrectable": attr("Offline_Uncorrectable"),
        "udma_crc_errors": attr("UDMA_CRC_Error_Count"),
        "predicted_fail": health_ok is False
        or bool(re.search(r"FAILING_NOW|In_the_past", attrs)),
    }


def _smart_one(
    manager: Any, dev: str, dtype: str | None = None
) -> dict[str, Any] | None:
    base = ["smartctl"]
    if dtype:
        base += ["-d", dtype]
    _, info, _ = _run(manager, base + ["-i", dev])
    if not re.search(
        r"Serial Number|Serial number|Product:|Device Model|Model Number", info
    ):
        return None
    _, health, _ = _run(manager, base + ["-H", dev])
    _, attrs, _ = _run(manager, base + ["-A", dev])
    d = _parse_smart(info, attrs, health)
    d["device"] = dev
    d["transport"] = dtype or "auto"
    return d


def smart_disks(manager: Any) -> list[dict[str, Any]]:
    """Enumerate physical disks + SMART, including RAID megaraid passthrough."""
    found: dict[str, dict[str, Any]] = {}
    probe: list[tuple[str, str | None]] = []

    _, scan, _ = _run(manager, ["smartctl", "--scan-open"])
    for ln in scan.splitlines():
        m = re.match(r"(\S+)\s+-d\s+(\S+)", ln)
        if m:
            probe.append((m.group(1), m.group(2)))

    if detect_raid_controllers(manager):
        _, lsblk, _ = _run(manager, ["lsblk", "-dn", "-o", "NAME"], elevated=False)
        blocks = [
            "/dev/" + n.strip()
            for n in lsblk.splitlines()
            if n.strip() and not n.strip().startswith(("loop", "sr", "zram"))
        ]
        if blocks:
            probe += [(blocks[0], f"megaraid,{i}") for i in range(24)]

    for dev, dtype in probe:
        d = _smart_one(manager, dev, None if dtype == "auto" else dtype)
        if d:
            found[d.get("serial") or f"{dev}:{dtype}"] = d
    return list(found.values())


_DRIVE_FAULT_RE = re.compile(
    r"Drive Slot.*?#?\s*(0x[0-9a-fA-F]+|\d+).*?(Asserted|Deasserted)", re.I
)


def _ipmi_via_fanmanager(target: Target) -> str | None:
    """Reuse the fan-manager IPMI wrapper (don't reimplement) when importable."""
    try:
        from fan_manager import ipmi as fm_ipmi
    except Exception:  # noqa: BLE001 — optional cross-package capability
        return None
    sel = fm_ipmi.sel("elist", target=target)
    sensors = fm_ipmi.sensors("type", sensor_type="Drive Slot", target=target)
    return f"{sel.get('response') or ''}\n{sensors.get('response') or ''}"


def bmc_drive_faults(manager: Any, target: Target = None) -> list[dict[str, Any]]:
    """Return asserted BMC drive-slot faults ``[{bay, state, source}]``."""
    remote = getattr(manager, "host", None)
    text: str | None = None
    # Prefer the fan-manager wrapper where it can run in the right place:
    #  - OOB target -> dials the BMC over LAN from wherever we are
    #  - local host -> in-band against /dev/ipmi0
    if target is not None or remote is None:
        text = _ipmi_via_fanmanager(target)
    if text is None:
        # Fallback: shell ipmitool through the manager (in-band on the target host
        # when remote, or OOB lanplus) — reused, not a second wrapper.
        args = ["ipmitool"]
        if target and target.get("host"):
            args += [
                "-I",
                "lanplus",
                "-H",
                target["host"],
                "-U",
                target.get("user", "root"),
                "-P",
                target.get("password", ""),
            ]
        _, sel, _ = _run(manager, args + ["sel", "elist"], elevated=target is None)
        _, sensors, _ = _run(
            manager, args + ["sdr", "type", "Drive Slot"], elevated=target is None
        )
        text = f"{sel}\n{sensors}"

    state: dict[str, str] = {}
    for ln in text.splitlines():
        m = _DRIVE_FAULT_RE.search(ln)
        if m:
            state[m.group(1).lower()] = m.group(
                2
            ).lower()  # latest wins (chronological)
    return [
        {"bay": bay, "state": "fault", "source": "bmc"}
        for bay, st in state.items()
        if st == "asserted"
    ]


def raid_pd_state(manager: Any, target: Target = None) -> list[dict[str, Any]]:
    """Physical-disk state from an in-band PERC/LSI CLI, or ``[]`` if none present."""
    for cli in ("perccli64", "perccli", "storcli64", "storcli"):
        ok, out, _ = _run(manager, [cli, "/call/eall/sall", "show"])
        if ok and "EID" in out:
            pds = []
            for ln in out.splitlines():
                m = re.match(r"\s*(\d+:\d+)\s+\d+\s+(\w+)", ln)
                if m:
                    pds.append({"slot": m.group(1), "state": m.group(2)})
            return pds
    return []


def _bay_to_slot(bay: str) -> int | None:
    try:
        v = int(bay, 16) if bay.lower().startswith("0x") else int(bay)
    except ValueError:
        return None
    return v - _BAY_BASE if v >= _BAY_BASE else v


def report(manager: Any, target: Target = None) -> dict[str, Any]:
    """Combined, correlated physical-storage health report (CONCEPT:SYS-1.4)."""
    disks = smart_disks(manager)
    faults = bmc_drive_faults(manager, target=target)
    raid = raid_pd_state(manager, target=target)

    correlated = []
    for f in faults:
        slot = _bay_to_slot(f["bay"])
        disk = next(
            (d for d in disks if d.get("transport") == f"megaraid,{slot}"), None
        )
        if disk is None:
            classification = "drive fault (no SMART match — disk may be offline)"
        elif (
            disk.get("predicted_fail")
            or (disk.get("reallocated_sectors") or 0) > 0
            or (disk.get("current_pending") or 0) > 0
        ):
            classification = "media failure (SMART defects present)"
        else:
            classification = "link/aging fault (SMART media clean — reseat or replace)"
        correlated.append(
            {**f, "slot": slot, "disk": disk, "classification": classification}
        )

    return {
        "success": True,
        "status": "fault" if correlated else "healthy",
        "controllers": detect_raid_controllers(manager),
        "disks": disks,
        "bmc_drive_faults": faults,
        "raid_physical_disks": raid,
        "faults": correlated,
        "summary": (
            f"{len(correlated)} drive fault(s) across {len(disks)} disk(s)"
            if correlated
            else f"No drive faults; {len(disks)} disk(s) healthy"
        ),
    }


def drive_health_summary(manager: Any) -> dict[str, Any]:
    """Lightweight BMC drive-fault signal for ``system_health_check`` (CONCEPT:SYS-1.5)."""
    try:
        faults = bmc_drive_faults(manager)
    except Exception as e:  # noqa: BLE001
        return {"warnings": [], "faults": [], "error": str(e)}
    return {
        "warnings": [f"DRIVE FAULT: bay #{f['bay']}" for f in faults],
        "faults": faults,
        "fault_count": len(faults),
    }
