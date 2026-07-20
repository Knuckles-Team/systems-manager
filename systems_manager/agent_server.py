#!/usr/bin/env python3
import logging
import sys
import warnings
from pathlib import Path
from urllib.parse import urlsplit

from agent_utilities.agent.factory import create_agent_parser
from agent_utilities.core.config import setting
from agent_utilities.core.workspace import initialize_workspace
from agent_utilities.prompting.builder import (
    build_system_prompt_from_workspace,
    load_identity,
)
from agent_utilities.server import create_agent_server

__version__ = "1.36.0"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


def _enabled(name: str) -> bool:
    return str(setting(name, "")).strip().casefold() in {"1", "true", "yes", "on"}


def _validated_runtime_url(value: str | None, *, label: str) -> str | None:
    if not value:
        return value
    if len(value) > 2_048:
        raise ValueError(f"{label} is too long")
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
        raise ValueError(f"{label} must be credential-free HTTPS or loopback HTTP")
    return value


def _explicit_runtime_path(
    value: str | None,
    *,
    label: str,
    directory: bool = False,
) -> Path | None:
    """Resolve an explicitly configured runtime path."""
    selected = value.strip() if isinstance(value, str) else value
    if not selected:
        return None
    if "\x00" in str(selected) or len(str(selected)) > 4_096:
        raise ValueError(f"{label} is malformed")
    candidate = Path(str(selected)).expanduser()

    resolved = candidate.resolve(strict=True)
    if directory:
        if not resolved.is_dir():
            raise ValueError(f"{label} must be an existing directory")
    elif not resolved.is_file():
        raise ValueError(f"{label} must be an existing regular file")
    return resolved


def _validate_remote_agent_boundary(host: str, *, debug: bool) -> None:
    """Require the real agent authentication boundary on non-loopback listeners."""
    loopback = host.strip().casefold() in {"127.0.0.1", "::1", "localhost"}
    if loopback:
        return

    jwt_auth = all(
        str(setting(name, "")).strip()
        for name in ("AUTH_JWT_JWKS_URI", "AUTH_JWT_ISSUER", "AUTH_JWT_AUDIENCE")
    )
    direct_tls = all(
        str(setting(name, "")).strip()
        for name in ("SERVER_TLS_CERTFILE", "SERVER_TLS_KEYFILE")
    )
    proxy_tls = _enabled("SERVER_TLS_TERMINATED") and bool(
        str(setting("SERVER_TRUSTED_PROXY_CIDRS", "")).strip()
    )
    remote_serving_enabled = str(
        setting("SYSTEMS_MANAGER_ALLOW_REMOTE_AGENT_SERVER", "")
    ).strip().casefold() in {"1", "true", "yes", "on"}
    if not remote_serving_enabled or not (direct_tls or proxy_tls) or not jwt_auth:
        raise PermissionError(
            "Remote agent serving requires configured TLS, trusted-proxy policy, "
            "and JWT authentication"
        )
    if debug:
        raise PermissionError("Debug mode is not permitted on a remote listener")


def agent_server():
    warnings.filterwarnings("ignore", message=".*urllib3.*or chardet.*")
    warnings.filterwarnings("ignore", category=DeprecationWarning, module="fastmcp")

    parser = create_agent_parser()
    args = parser.parse_args()
    if bool(getattr(args, "insecure", False)):
        raise PermissionError("TLS verification cannot be disabled")

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.debug("Debug mode enabled")

    host = str(args.host or "").strip().casefold()
    _validate_remote_agent_boundary(host, debug=bool(args.debug))

    mcp_url = _validated_runtime_url(args.mcp_url, label="MCP URL")
    base_url = _validated_runtime_url(args.base_url, label="model base URL")
    otel_endpoint = (
        _validated_runtime_url(args.otel_endpoint, label="telemetry endpoint")
        if args.otel
        else args.otel_endpoint
    )
    mcp_config = _explicit_runtime_path(
        args.mcp_config,
        label="MCP configuration",
    )
    custom_skills_directory = _explicit_runtime_path(
        args.custom_skills_directory,
        label="custom skills directory",
        directory=True,
    )
    workspace_value = getattr(args, "workspace", None) or setting("WORKSPACE_PATH")
    workspace = _explicit_runtime_path(
        workspace_value,
        label="agent workspace",
        directory=True,
    )
    if workspace is not None:
        from agent_utilities.core import workspace as workspace_module

        workspace_module.WORKSPACE_DIR = str(workspace)
    initialize_workspace()
    meta = load_identity()
    agent_name = setting("DEFAULT_AGENT_NAME", meta.get("name", "Systems Manager"))
    system_prompt = setting(
        "AGENT_SYSTEM_PROMPT",
        meta.get("content") or build_system_prompt_from_workspace(),
    )
    print(f"systems-manager agent v{__version__}", file=sys.stderr)

    custom_headers: dict[str, str] | None = None
    if mcp_url:
        parsed_mcp_url = urlsplit(mcp_url)
        if parsed_mcp_url.hostname not in {"127.0.0.1", "::1", "localhost"}:
            from agent_utilities.mcp.client_credentials import child_auth_header

            custom_headers = child_auth_header(None)
            if not custom_headers:
                raise PermissionError(
                    "Remote MCP connections require an explicit outbound service identity"
                )

    create_agent_server(
        mcp_url=mcp_url,
        mcp_config=str(mcp_config) if mcp_config else None,
        host=args.host,
        port=args.port,
        provider=args.provider,
        model_id=args.model_id,
        router_model=args.model_id,
        agent_model=args.model_id,
        base_url=base_url,
        api_key=args.api_key,
        custom_skills_directory=(
            str(custom_skills_directory) if custom_skills_directory else None
        ),
        enable_web_ui=args.web,
        enable_terminal_ui=bool(getattr(args, "terminal", False)),
        enable_web_logs=bool(getattr(args, "web_logs", False)),
        name=agent_name,
        system_prompt=system_prompt,
        workspace=str(workspace) if workspace else None,
        custom_headers=custom_headers,
        enable_otel=args.otel,
        otel_endpoint=otel_endpoint,
        otel_headers=args.otel_headers,
        otel_public_key=args.otel_public_key,
        otel_secret_key=args.otel_secret_key,
        otel_protocol=args.otel_protocol,
        debug=args.debug,
    )


if __name__ == "__main__":
    agent_server()
