"""Per-operation approval for host mutations, in addition to administrator policy.

The decision itself belongs to the SDK's one destructive guard. This module only
builds the approval text and fails closed without a context.
"""

from collections.abc import Mapping
from typing import Any

from fastmcp import Context
from scion_sdk.mcp.destructive import guard_destructive


def approval_text(action: str, detail: str | None = None) -> str:
    safe_action = " ".join(str(action).split())[:128]
    safe_detail = " ".join(str(detail or "").split())[:512]
    if not safe_action:
        raise ValueError("Mutation approval action is required")
    lines = ["SYSTEMS MANAGER MUTATION APPROVAL", f"Action: {safe_action}"]
    if safe_detail:
        lines.append(f"Target: {safe_detail}")
    lines.append("Approve this one operation?")
    return "\n".join(lines)


async def require_approval(
    ctx: Context | None,
    action: str,
    detail: str | None = None,
    *,
    arguments: Mapping[str, Any] | None = None,
    confirm: bool = False,
) -> Any | None:
    """Return ``None`` when the operation may proceed, else the tool result.

    The decision is the SDK's one destructive guard: a live confirmation, the
    per-call ``confirm`` argument, or the operator's ``SCION_ALLOW_DESTRUCTIVE``
    setting. A missing context fails closed.
    """
    if not ctx:
        return {"success": False, "error": "Operation approval is required"}
    try:
        refused = await guard_destructive(
            ctx,
            approval_text(action, detail),
            arguments,
            confirm=confirm is True,
        )
    except Exception:
        return {"success": False, "error": "Operation approval is required"}
    if isinstance(refused, dict):
        return {"success": False, "error": "Operation approval is required", **refused}
    return refused
