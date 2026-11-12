# Changelog

All notable changes to `systems-manager` will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.2.11] - 2026-11-12

### Changed
- Every host operation is its own typed tool (`sm_service_start_service`, `sm_process_kill_process`, `sm_system_update`, ...); the `sm_*_operations` action routers and `sm_storage_health` are replaced by 80 per-operation tools. Destructive classification and policy gates follow each tool.
- The connector now declares its whole surface: tool-use contracts, links, data locations, business roles, operator and role prompts, and task skills. Ontology classes roll up to core classes.
- Require `scion-sdk>=0.9.0,<1.0.0`.

## [2.2.10] - 2026-11-06

### Fixed
- `sm_file_operations` `manage_file` offers `read`, `create`, `update`, `delete` (the actions the manager implements); `update` is now classified as a filesystem mutation and gated like the others, and `write`/`append`, which the manager rejected, are removed.
- Administrator-policy denials reach the caller as a tool error naming the gate instead of a masked internal error (CONN-SYSTEMS-MANAGER-CONNECTOR-IDENTITY-R004).

## [2.2.8] - 2026-10-30

### Changed
- Require `scion-sdk>=0.6.4,<0.7.0`; `uv.lock` relocked.

### Fixed
- Windows compatibility: the volume root is no longer hard-coded to `/`; `getloadavg` is `hasattr`-guarded; nvm (bash) and the POSIX elevation helper return a typed "Unsupported on this platform" result on Windows; Kubernetes node detection no longer shells out to `systemctl` off Linux; removed a stale `winget_bin` reference from the shared service restart path.

### Added
- `tests/test_windows_portability.py` and a Windows CI job (`.github/workflows/windows-ci.yml`) that runs the suite on `windows-latest`.

## [1.15.0] - 2026-05-22

### Added
- Initial CHANGELOG.md creation
- docs/concepts.md with CONCEPT ID registry

### Changed
- Standardized project structure per agent-packages ecosystem conventions
