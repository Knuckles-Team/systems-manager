# Changelog

All notable changes to `systems-manager` will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.2.8] - 2026-10-30

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
