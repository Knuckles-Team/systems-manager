"""Runtime BMC/iDRAC credential retrieval from OpenBao (CONCEPT:SM-OS.governance.bay-bmc-flags-as).

The BMC out-of-band path reads its credential from the standardized OpenBao KV
layout — ``apps/idrac`` — at call time, using the service's own ``OPENBAO_TOKEN``.
The secret never transits config files, logs, or a chat transcript. Returns
``None`` when OpenBao is unreachable or the secret/keys are absent, so callers
degrade cleanly to in-band-only operation.
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from typing import Any

from agent_utilities.core.config import setting

_log = logging.getLogger("SystemsManager.bmc_credentials")

# Standardized KV v2 layout: mount ``apps``, one path per service.
_DEFAULT_PATH = "idrac"
_DEFAULT_MOUNT = "apps"

# Candidate key names inside the secret (mirror the names used in the .env).
_PW_KEYS = ("root_password", "password", "ipmi_password", "bmc_password")
_USER_KEYS = ("root_user", "username", "user", "ipmi_user", "bmc_user")
_HOST_KEYS = ("host", "address", "ip", "hostname")


def _read_kv(url: str, token: str, path: str, mount: str) -> dict[str, Any] | None:
    endpoint = f"{url.rstrip('/')}/v1/{mount}/data/{path}"
    req = urllib.request.Request(endpoint, headers={"X-Vault-Token": token})
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:  # noqa: S310 (internal URL)
            body = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError) as e:
        _log.debug("OpenBao read %s failed: %s", endpoint, e)
        return None
    data = body.get("data", {}).get("data")
    return data if isinstance(data, dict) else None


def _first(d: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    for k in keys:
        v = d.get(k)
        if isinstance(v, str) and v:
            return v
    return None


def get_bmc_credentials(
    host: str | None = None, *, path: str = _DEFAULT_PATH, mount: str = _DEFAULT_MOUNT
) -> dict[str, str] | None:
    """Return ``{host, user, password}`` for out-of-band BMC access, or ``None``.

    Reads ``OPENBAO_URL`` (default ``http://openbao.arpa``) + ``OPENBAO_TOKEN`` at
    call time and fetches the ``apps/<path>`` KV v2 secret. ``host`` (the BMC IP)
    supplied by the caller overrides any value stored in the secret.
    """
    token = setting("OPENBAO_TOKEN")
    if not token:
        _log.debug("OPENBAO_TOKEN not set; cannot fetch BMC credential.")
        return None
    url = setting("OPENBAO_URL", "http://openbao.arpa")
    data = _read_kv(url, token, path, mount)
    if not data:
        return None
    password = _first(data, _PW_KEYS)
    if not password:
        return None
    return {
        "host": host or _first(data, _HOST_KEYS) or "",
        "user": _first(data, _USER_KEYS) or "root",
        "password": password,
    }
