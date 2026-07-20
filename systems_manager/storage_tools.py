"""MCP tools for physical storage + BMC drive-fault health (CONCEPT:SM-OS.governance.sys-8, CONCEPT:SM-OS.governance.bay-bmc-flags-as).

Thin transport over :mod:`systems_manager.storage_health`. Runs against the local
host. Out-of-band BMC access reads credentials from the configured secret provider at runtime
when ``{'oob':true}`` is passed. Secrets are never accepted as tool arguments.
"""

from __future__ import annotations

from typing import Any

from agent_utilities.mcp.concurrency import run_blocking
from fastmcp import Context, FastMCP
from pydantic import Field

from systems_manager import storage_health
from systems_manager.bmc_credentials import get_bmc_credentials
from systems_manager.systems_manager import detect_and_create_manager


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
        out_of_band: bool = Field(
            default=False,
            description="Resolve BMC credentials from the configured secret provider.",
        ),
        bmc_host: str | None = Field(
            default=None,
            description="Optional configured BMC host override; never a credential.",
        ),
        ctx: Context | None = Field(default=None, description="MCP context"),
    ) -> Any:
        """Physical disk + BMC drive-fault health: SMART (incl. megaraid passthrough),
        BMC/IPMI drive-slot faults, and RAID physical-disk state — correlated so a
        BMC-flagged disk with clean SMART media reads as a link/aging fault, not media
        wear (CONCEPT:SM-OS.governance.sys-8/SYS-1.5)."""
        try:
            manager = detect_and_create_manager()
        except Exception:  # noqa: BLE001
            return {"success": False, "error": "Operation failed"}
        target = get_bmc_credentials(host=bmc_host) if out_of_band else None

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
