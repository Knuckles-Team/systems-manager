"""Tests for physical storage + BMC drive-fault health (CONCEPT:SM-OS.governance.sys-8, CONCEPT:SM-OS.governance.bay-bmc-flags-as).

A fake manager maps commands to canned output, so SMART parsing (megaraid
passthrough), BMC drive-fault parsing, and the SMART<->BMC correlation are
exercised without any hardware.
"""

from __future__ import annotations

from systems_manager import bmc_credentials, storage_health
from systems_manager.models import CommandResult

_HGST_INFO = """
Device Model:     HGST HTS545050A7E380
Serial Number:    140510TM85G3G800GS7S
User Capacity:    500,107,862,016 bytes [500 GB]
Rotation Rate:    5400 rpm
"""

_HGST_ATTRS = """
ID# ATTRIBUTE_NAME          FLAG     VALUE WORST THRESH TYPE      WHEN_FAILED RAW_VALUE
  5 Reallocated_Sector_Ct   0x0033   100   100   005    Pre-fail  -       0
  9 Power_On_Hours          0x0012   038   038   000    Old_age   -       27497
197 Current_Pending_Sector  0x0022   100   100   000    Old_age   -       0
198 Offline_Uncorrectable   0x0008   100   100   000    Old_age   -       0
199 UDMA_CRC_Error_Count    0x000a   200   200   000    Old_age   -       1
"""

_SEL = """
 5d | 04/12/2026 | Drive Slot / Bay #0xa2 | Drive Fault () | Deasserted
 7e | 06/03/2026 | Drive Slot / Bay #0xa2 | Drive Fault () | Asserted
 11 | 06/03/2026 | Drive Slot / Bay #0xa0 | Drive Fault () | Deasserted
"""


class _FakeManager:
    """Manager double: returns canned CommandResult keyed on the command string."""

    def __init__(self, host=None):
        self.host = host

    def run_command(
        self, cmd, elevated=False, *, capture_output=False, timeout_seconds=None
    ):
        s = " ".join(cmd)
        out = ""
        if s.startswith("lspci"):
            out = "05:00.0 RAID bus controller: Broadcom / LSI MegaRAID SAS 2008"
        elif s.startswith("lsblk"):
            out = "sda\nsdb\nloop0"
        elif "smartctl --scan-open" in s:
            out = ""
        elif "megaraid,2 -i" in s:
            out = _HGST_INFO
        elif "megaraid,2 -H" in s:
            out = "SMART overall-health self-assessment test result: PASSED"
        elif "megaraid,2 -A" in s:
            out = _HGST_ATTRS
        elif "smartctl" in s:  # any other megaraid index -> no device
            out = ""
        elif "sel elist" in s:
            out = _SEL
        elif "Drive Slot" in s:  # sdr type "Drive Slot"
            out = ""
        elif "perccli" in s or "storcli" in s:
            return CommandResult(success=False, stdout="", stderr="not found")
        return CommandResult(success=True, stdout=out, stderr="")


def test_smart_disks_megaraid_passthrough():
    disks = storage_health.smart_disks(_FakeManager())
    assert len(disks) == 1
    d = disks[0]
    assert d["disk_ref"].startswith("disk:")
    assert "serial" not in d
    assert "device" not in d
    assert "HGST" in d["model"]
    assert d["health_passed"] is True
    assert d["power_on_hours"] == 27497
    assert d["reallocated_sectors"] == 0
    assert d["transport"] == "megaraid,2"


def test_bmc_drive_faults_latest_state_wins():
    # Local in-band read uses the typed manager seam without credentials.
    faults = storage_health.bmc_drive_faults(_FakeManager())
    bays = {f["bay"] for f in faults}
    assert "0xa2" in bays  # last state Asserted
    assert "0xa0" not in bays  # last state Deasserted -> not a fault


def test_report_correlates_clean_media_as_link_fault():
    rep = storage_health.report(_FakeManager())
    assert rep["status"] == "fault"
    assert len(rep["faults"]) == 1
    f = rep["faults"][0]
    assert f["slot"] == 2
    assert f["disk"] is not None and f["disk"]["disk_ref"].startswith("disk:")
    assert "link/aging" in f["classification"]


def test_drive_health_summary_warnings():
    summary = storage_health.drive_health_summary(_FakeManager())
    assert summary["fault_count"] == 1
    assert any("0xa2" in w for w in summary["warnings"])


def test_no_controllers_no_megaraid_probe():
    mgr = _FakeManager()
    # Override lspci to report no RAID controller -> only --scan-open probed (empty)
    mgr.run_command = (
        lambda cmd, elevated=False, capture_output=False, timeout_seconds=None: (
            CommandResult(success=True, stdout="", stderr="")
        )
    )
    assert storage_health.smart_disks(mgr) == []


def test_get_bmc_credentials_requires_projected_secret(monkeypatch):
    monkeypatch.setattr(bmc_credentials, "setting", lambda _k, d=None: None)
    assert bmc_credentials.get_bmc_credentials() is None


def test_get_bmc_credentials_validates_projected_document(monkeypatch):
    material = (
        '{"host":"bmc.example.invalid","user":"operator","password":"runtime value"}'
    )
    monkeypatch.setattr(bmc_credentials, "setting", lambda _k, d=None: material)
    assert bmc_credentials.get_bmc_credentials() == {
        "host": "bmc.example.invalid",
        "user": "operator",
        "password": "runtime value",
    }

    material = '{"host":"bmc.example.invalid","user":"operator","password":"value","extra":"rejected"}'
    monkeypatch.setattr(bmc_credentials, "setting", lambda _k, d=None: material)
    assert bmc_credentials.get_bmc_credentials() is None


def test_probes_are_bounded_with_timeout():
    """Regression for the systems-manager MCP hang: ``system_health_check`` (the
    tool that reports host uptime + memory) folds in
    ``storage_health.drive_health_summary`` -> ``bmc_drive_faults`` -> ``_run``,
    which shells out to ``ipmitool``/``smartctl``. Every one of those probes must
    pass a bounded ``timeout`` through the manager seam so a stuck BMC/IPMI call
    can never block the health check indefinitely."""
    captured_timeouts: list[float | None] = []

    class _CapturingManager(_FakeManager):
        def run_command(
            self, cmd, elevated=False, *, capture_output=False, timeout_seconds=None
        ):
            captured_timeouts.append(timeout_seconds)
            return super().run_command(
                cmd,
                elevated=elevated,
                capture_output=capture_output,
                timeout_seconds=timeout_seconds,
            )

    storage_health.bmc_drive_faults(_CapturingManager())

    assert captured_timeouts, "expected at least one run_command call"
    assert all(t == storage_health._PROBE_TIMEOUT_SECONDS for t in captured_timeouts)
