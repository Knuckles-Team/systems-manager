"""Per-operation approval for host mutations, in addition to administrator policy.

The decision itself belongs to the SDK: it honours an explicit ``confirm=true``,
refuses (never errors) a client that did not advertise elicitation, asks an
eliciting client, and returns an input request on modern MCP. This module only
adapts the SDK answer to a tool result.
"""

from collections.abc import Mapping
from typing import Any

from fastmcp import Context
from mcp.types import InputRequiredResult
from scion_sdk.mcp.context import confirmation_refusal, ctx_confirm_destructive


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

    A missing context fails closed. The returned value is either the SDK input
    request (modern MCP) or a cancelled payload naming ``confirm=true`` when the
    client cannot elicit.
    """
    if not ctx:
        return {"success": False, "error": "Operation approval is required"}
    try:
        decision = await ctx_confirm_destructive(
            ctx,
            approval_text(action, detail),
            confirmation_arguments=arguments,
            explicit_confirm=confirm is True,
        )
    except Exception:
        return {"success": False, "error": "Operation approval is required"}
    if isinstance(decision, InputRequiredResult):
        return decision
    if decision is True:
        return None
    try:
        refusal = confirmation_refusal(ctx, action)
    except Exception:
        refusal = {"cancelled": True, "operation": action}
    return {"success": False, "error": "Operation approval is required", **refusal}
