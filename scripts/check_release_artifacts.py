#!/usr/bin/env python3
"""Fail a release when tracked runtime state or secret containers are present."""

from __future__ import annotations

import subprocess
from pathlib import PurePosixPath

_MAX_TRACKED_FILES = 100_000
_FORBIDDEN_SUFFIXES = {
    ".db",
    ".key",
    ".p12",
    ".pem",
    ".pfx",
    ".sqlite",
    ".sqlite3",
    ".zip",
}
_FORBIDDEN_NAMES = {
    ".env",
    "chats",
    "cron_log.md",
    "memory.md",
    "user.md",
}
_ALLOWED_ENV_TEMPLATES = {".env.example", ".env.template"}


def _tracked_files() -> list[PurePosixPath]:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        check=True,
        capture_output=True,
        timeout=30,
    )
    if len(result.stdout) > 16 * 1024 * 1024:
        raise RuntimeError("Tracked-file inventory exceeds the release-gate limit")
    paths = [
        PurePosixPath(raw.decode("utf-8")) for raw in result.stdout.split(b"\0") if raw
    ]
    if len(paths) > _MAX_TRACKED_FILES:
        raise RuntimeError("Tracked-file count exceeds the release-gate limit")
    return paths


def _is_forbidden(path: PurePosixPath) -> bool:
    lowered = path.name.casefold()
    lowered_parts = {part.casefold() for part in path.parts}
    if (
        lowered in _FORBIDDEN_NAMES
        or (lowered.startswith(".env.") and lowered not in _ALLOWED_ENV_TEMPLATES)
        or "chats" in lowered_parts
        or path.suffix.casefold() in _FORBIDDEN_SUFFIXES
    ):
        return True
    return "agent_data" in path.parts and lowered.endswith((".db", ".sqlite"))


def main() -> int:
    forbidden = sorted(str(path) for path in _tracked_files() if _is_forbidden(path))
    if forbidden:
        print("Release blocked: tracked runtime or secret-bearing artifacts detected.")
        for path in forbidden:
            print(f"- {path}")
        return 1
    print("Release artifact gate passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
