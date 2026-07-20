"""Resolve one AgentConfig-projected BMC credential document at runtime.

The checked-in MCP catalog contains only a runtime secret reference. AgentConfig
materializes the referenced JSON for the child process; this module neither knows nor
configures a particular secret-store vendor.
"""

from __future__ import annotations

import json
import re

from agent_utilities.core.config import setting

_HOST = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,252}\Z")


def _bounded_text(value: object, *, maximum: int) -> str | None:
    if not isinstance(value, str) or not value or len(value) > maximum:
        return None
    if any(ord(character) < 32 or character.isspace() for character in value):
        return None
    return value


def _bounded_secret(value: object, *, maximum: int) -> str | None:
    if not isinstance(value, str) or not value or len(value) > maximum:
        return None
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        return None
    return value


def get_bmc_credentials(host: str | None = None) -> dict[str, str] | None:
    """Return validated ``host``/``user``/``password`` runtime material.

    ``SYSTEMS_MANAGER_BMC_CREDENTIALS`` must be projected from an AgentConfig secret
    reference and contain one JSON object. Invalid or incomplete material fails closed
    without logging its value or origin.
    """

    raw = setting("SYSTEMS_MANAGER_BMC_CREDENTIALS")
    if not isinstance(raw, str) or not raw or len(raw.encode("utf-8")) > 8_192:
        return None
    try:
        document = json.loads(raw)
    except (TypeError, ValueError):
        return None
    if not isinstance(document, dict) or set(document) != {"host", "user", "password"}:
        return None

    selected_host = _bounded_text(host or document.get("host"), maximum=253)
    user = _bounded_text(document.get("user"), maximum=128)
    password = _bounded_secret(document.get("password"), maximum=1_024)
    if (
        selected_host is None
        or _HOST.fullmatch(selected_host) is None
        or user is None
        or password is None
    ):
        return None
    return {"host": selected_host, "user": user, "password": password}
