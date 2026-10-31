# CONN-SYSTEMS-MANAGER-CONNECTOR-IDENTITY — Requirements

Governing spec: [spec.md](spec.md).

Each row is one requirement. A row names the file it touches and the test that proves it. The generator sets each row's state in `status.json`.

| ID | Requirement | Acceptance |
|---|---|---|
| `CONN-SYSTEMS-MANAGER-CONNECTOR-IDENTITY-R001` | **Fleet name.** `pyproject.toml` declares `systems-manager-mcp` as the single `scion_sdk.connector` entry point. The content pack, the manifest `connector`, the fingerprints and the ingest binding all carry `systems-manager-mcp`. Proving test: `tests/test_fleet_name.py::test_connector_name_is_the_fleet_name`. | Every connector name in the package is `systems-manager-mcp`. |
| `CONN-SYSTEMS-MANAGER-CONNECTOR-IDENTITY-R002` | **Windows portability.** The package imports and runs on Windows with no POSIX-only module or API (`pwd`, `grp`, `fcntl`, `termios`, `resource`, `getloadavg`, `killpg`, `sudo`, `bash`, a hard-coded `/` volume root). Windows hosts use their own implementations (winget, PowerShell, `schtasks`, `shutdown.exe`); where an operation has no Windows meaning (nvm bash bootstrap, the POSIX elevation helper, Kubernetes node detection) it returns a typed `Unsupported on this platform` result and never raises. Proving test: `tests/test_windows_portability.py`. | Every Windows branch passes under monkeypatched `platform.system` / `os.name`, and the Windows CI job runs the full suite. |
