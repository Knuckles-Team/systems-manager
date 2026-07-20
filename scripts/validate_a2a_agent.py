#!/usr/bin/env python3
import asyncio
import json
import os
import re
import uuid
from dataclasses import dataclass
from urllib.parse import urlsplit

import httpx

A2A_URL = os.environ.get("A2A_URL", "http://127.0.0.1:9016/a2a/")
_MAX_RESPONSE_BYTES = 1024 * 1024
_MAX_POLL_ATTEMPTS = 60


def _validated_endpoint(value: str) -> str:
    if len(value) > 2_048:
        raise ValueError("A2A endpoint is too long")
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
        raise ValueError("A2A endpoint must be credential-free HTTPS or loopback HTTP")
    return value


@dataclass(frozen=True)
class _BoundedResponse:
    status_code: int
    data: dict | None

    def json(self) -> dict:
        if self.data is None:
            raise json.JSONDecodeError("Invalid JSON", "", 0)
        return self.data


async def _post_json(
    client: httpx.AsyncClient,
    url: str,
    payload: dict,
) -> _BoundedResponse:
    async with client.stream(
        "POST",
        url,
        json=payload,
        headers={"Content-Type": "application/json"},
    ) as response:
        declared = response.headers.get("content-length")
        if declared and int(declared) > _MAX_RESPONSE_BYTES:
            raise ValueError("A2A response exceeds the size limit")
        body = bytearray()
        async for chunk in response.aiter_bytes():
            if len(body) + len(chunk) > _MAX_RESPONSE_BYTES:
                raise ValueError("A2A response exceeds the size limit")
            body.extend(chunk)
    try:
        data = json.loads(body) if body else None
    except (UnicodeDecodeError, json.JSONDecodeError):
        data = None
    return _BoundedResponse(
        response.status_code, data if isinstance(data, dict) else None
    )


async def main():
    print("Validating the configured A2A agent...")

    questions = [
        os.environ.get("A2A_VALIDATION_QUERY", "Describe your available capabilities.")
    ]
    if any(len(question.encode("utf-8")) > 16_384 for question in questions):
        raise ValueError("Validation query exceeds the size limit")
    url = _validated_endpoint(A2A_URL)

    async with httpx.AsyncClient(
        timeout=httpx.Timeout(30.0, connect=10.0),
        follow_redirects=False,
        limits=httpx.Limits(max_connections=2, max_keepalive_connections=1),
    ) as client:
        for q in questions:
            print("\nSubmitting the configured validation query.")
            print("--- Sending Request ---")

            payload = {
                "jsonrpc": "2.0",
                "method": "message/send",
                "params": {
                    "message": {
                        "kind": "message",
                        "role": "user",
                        "parts": [{"kind": "text", "text": q}],
                        "messageId": str(uuid.uuid4()),
                    }
                },
                "id": 1,
            }

            try:
                print("Trying the configured endpoint with JSON-RPC (message/send)...")
                resp = await _post_json(client, url, payload)

                print(f"Status Code: {resp.status_code}")
                if resp.status_code == 200:
                    try:
                        data = resp.json()
                        print("JSON response received.")

                        if "result" in data and "id" in data["result"]:
                            task_id = str(data["result"]["id"])
                            if not re.fullmatch(r"[A-Za-z0-9_.:-]{1,256}", task_id):
                                raise ValueError("A2A task identifier is invalid")
                            print("\nTask submitted; polling for result...")

                            for _attempt in range(_MAX_POLL_ATTEMPTS):
                                await asyncio.sleep(2)
                                poll_payload = {
                                    "jsonrpc": "2.0",
                                    "method": "tasks/get",
                                    "params": {"id": task_id},
                                    "id": 2,
                                }
                                poll_resp = await _post_json(client, url, poll_payload)
                                if poll_resp.status_code == 200:
                                    poll_data = poll_resp.json()
                                    if "result" in poll_data:
                                        state = str(
                                            poll_data["result"]["status"]["state"]
                                        )
                                        if not re.fullmatch(
                                            r"[A-Za-z0-9_.:-]{1,64}", state
                                        ):
                                            state = "unknown"
                                        print(f"Task State: {state}")
                                        if state not in [
                                            "submitted",
                                            "running",
                                            "working",
                                        ]:
                                            print(
                                                f"\nTask Finished with state: {state}"
                                            )

                                            if "history" in poll_data["result"]:
                                                history = poll_data["result"]["history"]
                                                if history:
                                                    last_msg = None
                                                    for msg in reversed(history):
                                                        if msg.get("role") != "user":
                                                            last_msg = msg
                                                            break

                                                    if last_msg and "parts" in last_msg:
                                                        print(
                                                            "\n--- Agent Response ---"
                                                        )
                                                        for part in last_msg["parts"]:
                                                            if "text" in part:
                                                                print(
                                                                    "Agent response content omitted."
                                                                )
                                                            elif "content" in part:
                                                                print(
                                                                    "Agent response content omitted."
                                                                )
                                                    elif last_msg:
                                                        print(
                                                            "Final response received without structured parts."
                                                        )
                                                    else:
                                                        print(
                                                            "\n--- No Agent Response Found in History ---"
                                                        )

                                            print(
                                                "Validation result received; body omitted."
                                            )
                                            break
                                    else:
                                        print("Starting polling error key check...")
                                        if "error" in poll_data:
                                            code = poll_data["error"].get("code")
                                            safe_code = (
                                                str(code)
                                                if isinstance(code, int)
                                                else "unknown"
                                            )
                                            print(
                                                f"Polling JSON-RPC error code: {safe_code}"
                                            )
                                        break
                                else:
                                    print(f"Polling Failed: {poll_resp.status_code}")
                                    print(
                                        f"Polling failed with HTTP {poll_resp.status_code}."
                                    )
                                    break
                            else:
                                print(
                                    "Polling stopped at the configured attempt limit."
                                )

                        if "error" in data:
                            code = data["error"].get("code")
                            safe_code = (
                                str(code) if isinstance(code, int) else "unknown"
                            )
                            print(f"JSON-RPC error code: {safe_code}")
                    except json.JSONDecodeError:
                        print(f"Response body omitted (HTTP {resp.status_code}).")
                else:
                    print(f"Error: {resp.status_code}")
                    print(f"Response body omitted (HTTP {resp.status_code}).")

            except (httpx.RequestError, KeyError, TypeError, ValueError) as e:
                print(f"Operation failed: {type(e).__name__}")


if __name__ == "__main__":
    asyncio.run(main())
