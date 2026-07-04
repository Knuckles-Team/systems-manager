"""MCP tools for physical storage + BMC drive-fault health (CONCEPT:SM-OS.governance.sys-8, CONCEPT:SM-OS.governance.bay-bmc-flags-as).

Thin transport over :mod:`systems_manager.storage_health`. Runs against the local
host or any inventory ``host`` (remote-over-SSH via the manager seam). Out-of-band
BMC access reads the iDRAC credential from OpenBao at runtime when ``{'oob':true}``
is passed (or an explicit ``{'host','user','password'}`` target).
"""

from __future__ import annotations

import json
from typing import Any

from agent_utilities.mcp_utilities import run_blocking
from fastmcp import Context, FastMCP
from pydantic import Field

from systems_manager import storage_health
from systems_manager.bmc_credentials import get_bmc_credentials
from systems_manager.systems_manager import detect_and_create_manager


def _target_from_params(params: dict[str, Any]) -> dict[str, Any] | None:
    if params.get("host") and params.get("password"):
        return {
            "host": params["host"],
            "user": params.get("user", "root"),
            "password": params["password"],
        }
    if params.get("oob"):
        return get_bmc_credentials(host=params.get("host"))
    return None


def register_storage_health_tools(mcp: FastMCP) -> None:
    """Register the storage-health tool (CONCEPT:SM-OS.governance.sys-8)."""

    @mcp.tool(
        annotations={
            "title": "Storage Health",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
        tags={"storage_health", "observability"},
    )
    async def sm_storage_health(
        action: str = Field(
            default="report", description="report | smart | faults | raid"
        ),
        host: str | None = Field(
            default=None,
            description="Inventory host key for a REMOTE target (defaults to local).",
        ),
        params_json: str = Field(
            default="{}",
            description="Optional JSON for out-of-band BMC: {'oob':true} reads the "
            "iDRAC credential from OpenBao apps/idrac, or pass an explicit "
            "{'host','user','password'} target.",
        ),
        ctx: Context | None = Field(default=None, description="MCP context"),
    ) -> Any:
        """Physical disk + BMC drive-fault health: SMART (incl. megaraid passthrough),
        BMC/IPMI drive-slot faults, and RAID physical-disk state — correlated so a
        BMC-flagged disk with clean SMART media reads as a link/aging fault, not media
        wear (CONCEPT:SM-OS.governance.sys-8/SYS-1.5)."""
        try:
            params = json.loads(params_json or "{}")
        except Exception as e:  # noqa: BLE001
            return {"success": False, "error": f"Invalid params_json: {e}"}
        try:
            manager = detect_and_create_manager(host=host)
        except Exception as e:  # noqa: BLE001
            return {"success": False, "error": str(e)}
        target = _target_from_params(params)

        if action == "smart":
            return await run_blocking(
                lambda: {"success": True, "disks": storage_health.smart_disks(manager)}
            )
        if action == "faults":
            return await run_blocking(
                lambda: {
                    "success": True,
                    "faults": storage_health.bmc_drive_faults(manager, target=target),
                }
            )
        if action == "raid":
            return await run_blocking(
                lambda: {
                    "success": True,
                    "raid_physical_disks": storage_health.raid_pd_state(
                        manager, target=target
                    ),
                }
            )
        if action == "report":
            return await run_blocking(
                lambda: storage_health.report(manager, target=target)
            )
        return {"success": False, "error": f"Unknown action: {action}"}
