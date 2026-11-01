"""Mutations refuse cleanly and accept ``confirm=true`` on real transports.

The real MCP server runs as a subprocess three ways (no-auth stdio, no-auth
streamable HTTP on 127.0.0.1, JWT streamable HTTP against a local JWKS) and a
real fastmcp client calls ``sm_file_operations`` ``manage_file`` ``create`` on
each, with and without client elicitation.

The mutation is harmless by construction: it writes one small file inside a
scratch directory under pytest's tmp path, so nothing outside the sandbox
changes. Administrator policy is enabled only in the subprocess environment.
"""

from __future__ import annotations

import base64
import json
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastmcp import Client
from fastmcp.client.transports import StdioTransport, StreamableHttpTransport
from fastmcp.server.auth.providers.jwt import RSAKeyPair

ISSUER = "https://idp.example.invalid/realms/homelab"
AUDIENCE = "agent-services"
CALL_TIMEOUT = 90
pytestmark = pytest.mark.spec("CONN-SYSTEMS-MANAGER-CONNECTOR-IDENTITY-R003")


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _jwks(keys: RSAKeyPair) -> dict[str, Any]:
    from cryptography.hazmat.primitives import serialization

    public = serialization.load_pem_public_key(keys.public_key.encode())
    numbers = public.public_numbers()  # type: ignore[union-attr]

    def b64(value: int) -> str:
        raw = value.to_bytes((value.bit_length() + 7) // 8, "big")
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()

    return {
        "keys": [
            {
                "kty": "RSA",
                "kid": "test-key",
                "use": "sig",
                "alg": "RS256",
                "n": b64(numbers.n),
                "e": b64(numbers.e),
            }
        ]
    }


def _serve_jwks(document: dict[str, Any]) -> tuple[HTTPServer, str]:
    body = json.dumps(document).encode()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802 - http.server API
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_args: Any) -> None:
            return

    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_address[1]}/jwks"


class _World:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.keys = RSAKeyPair.generate()
        self.jwks_server, self.jwks_uri = _serve_jwks(_jwks(self.keys))

    def sandbox(self, name: str) -> tuple[dict[str, str], Path]:
        home = self.root / name / "home"
        home.mkdir(parents=True)
        work = self.root / name / "work"
        work.mkdir(parents=True)
        env = {
            key: value
            for key, value in os.environ.items()
            if not key.startswith(("SYSTEMS_MANAGER_", "AUTH_", "FASTMCP_", "MCP_"))
        }
        env.update(
            HOME=str(home),
            XDG_CONFIG_HOME=str(self.root / name / "config"),
            SYSTEMS_MANAGER_ALLOW_HOST_MUTATIONS="true",
            SYSTEMS_MANAGER_ALLOW_FILESYSTEM_MUTATIONS="true",
            SYSTEMS_MANAGER_FILESYSTEM_ROOT=str(work.resolve()),
            SYSTEMS_MANAGER_PSEUDONYMIZATION_KEY="test-key-" * 4,
            MCP_FLEET_REGISTRATION="false",
            PYTHONUNBUFFERED="1",
        )
        return env, work

    def token(self) -> str:
        return self.keys.create_token(
            subject="arbora-service-account-id",
            issuer=ISSUER,
            audience=AUDIENCE,
            additional_claims={"azp": "arbora", "client_id": "arbora"},
            kid="test-key",
        )


@pytest.fixture(scope="module")
def world(tmp_path_factory: pytest.TempPathFactory) -> Iterator[_World]:
    built = _World(tmp_path_factory.mktemp("confirm"))
    yield built
    built.jwks_server.shutdown()


def _executable() -> str:
    found = Path(sys.executable).parent / "systems-manager-mcp"
    return str(found) if found.exists() else shutil.which("systems-manager-mcp") or ""


class _HttpServer:
    def __init__(self, argv: list[str], env: dict[str, str], port: int) -> None:
        self.url = f"http://127.0.0.1:{port}/mcp"
        self.log_path = Path(env["HOME"]).parent / f"server-{port}.log"
        self.log = self.log_path.open("w+", encoding="utf-8", errors="replace")
        self.proc = subprocess.Popen(
            [_executable(), *argv, "--port", str(port)],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=self.log,
            text=True,
        )
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            if self.proc.poll() is not None:
                raise AssertionError(f"server exited: {self._read_log()}")
            try:
                httpx.get(f"http://127.0.0.1:{port}/health", timeout=1)
                return
            except httpx.HTTPError:
                time.sleep(0.2)
        raise AssertionError("server did not start")

    def _read_log(self) -> str:
        if not self.log.closed:
            self.log.flush()
        return self.log_path.read_text(encoding="utf-8", errors="replace")

    def stop(self) -> None:
        self.proc.terminate()
        try:
            self.proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.proc.wait()
        self.log.close()
        print(f"--- server stderr ---\n{self._read_log()[-6000:]}")


async def _accept(message: str, response_type: Any, params: Any, context: Any) -> Any:
    return response_type(confirmed=True) if response_type else None


def _write_args(target: Path, **extra: Any) -> dict[str, Any]:
    return {
        "action": "manage_file",
        "file_action": "create",
        "filepath": "created.txt",
        "content": "written\n",
        **extra,
    }


async def _destructive_flow(
    open_client: Any, work: Path, *, elicits: bool, label: str
) -> None:
    """A file write over a real transport: refused cleanly, then confirmed."""
    target = work / "created.txt"
    kwargs: dict[str, Any] = {"timeout": CALL_TIMEOUT}
    if elicits:
        kwargs["elicitation_handler"] = _accept
    async with open_client(**kwargs) as client:
        if elicits:
            done = await client.call_tool(
                "sm_file_operations", _write_args(target), raise_on_error=False
            )
            assert not done.is_error, f"{label}: {done.content}"
            assert target.read_text() == "written\n"
            return
        refused = await client.call_tool(
            "sm_file_operations", _write_args(target), raise_on_error=False
        )
        assert not refused.is_error, f"{label}: {refused.content}"
        assert refused.structured_content["cancelled"] is True
        assert "confirm=true" in refused.structured_content["reason"]
        assert not target.exists(), "an unconfirmed mutation must not change anything"
        confirmed = await client.call_tool(
            "sm_file_operations",
            _write_args(target, confirm=True),
            raise_on_error=False,
        )
        assert not confirmed.is_error, f"{label}: {confirmed.content}"
        assert target.read_text() == "written\n"


@pytest.mark.parametrize("elicits", [False, True])
async def test_stdio_no_auth_mutation(world: _World, elicits: bool) -> None:
    env, work = world.sandbox(f"stdio-{elicits}")

    def open_client(**kwargs: Any) -> Client[Any]:
        transport = StdioTransport(
            command=_executable(), args=["--transport", "stdio"], env=env
        )
        return Client(transport, **kwargs)

    await _destructive_flow(open_client, work, elicits=elicits, label="stdio")


@pytest.mark.parametrize("elicits", [False, True])
async def test_http_no_auth_localhost_mutation(world: _World, elicits: bool) -> None:
    env, work = world.sandbox(f"http-{elicits}")
    port = _free_port()
    server = _HttpServer(
        [
            "--transport",
            "streamable-http",
            "--auth-type",
            "none",
            "--host",
            "127.0.0.1",
            "--allowed-hosts",
            f"127.0.0.1:{port},localhost:{port}",
        ],
        env,
        port,
    )
    try:

        def open_client(**kwargs: Any) -> Client[Any]:
            return Client(StreamableHttpTransport(server.url), **kwargs)

        await _destructive_flow(open_client, work, elicits=elicits, label="http")
    finally:
        server.stop()


@pytest.mark.parametrize("elicits", [False, True])
async def test_http_jwt_mutation(world: _World, elicits: bool) -> None:
    env, work = world.sandbox(f"jwt-{elicits}")
    port = _free_port()
    server = _HttpServer(
        [
            "--transport",
            "streamable-http",
            "--auth-type",
            "jwt",
            "--host",
            "127.0.0.1",
            "--token-issuer",
            ISSUER,
            "--token-audience",
            AUDIENCE,
            "--token-jwks-uri",
            world.jwks_uri,
            "--allowed-hosts",
            f"127.0.0.1:{port},localhost:{port}",
        ],
        env,
        port,
    )
    try:

        def open_client(**kwargs: Any) -> Client[Any]:
            return Client(
                StreamableHttpTransport(server.url, auth=world.token()), **kwargs
            )

        await _destructive_flow(open_client, work, elicits=elicits, label="jwt")
    finally:
        server.stop()
