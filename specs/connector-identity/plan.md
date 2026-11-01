# CONN-SYSTEMS-MANAGER-CONNECTOR-IDENTITY — Implementation plan

Governing spec: [spec.md](spec.md). Rows: [requirements.md](requirements.md).

## Summary

This plan states how `systems-manager` delivers the rows of `CONN-SYSTEMS-MANAGER-CONNECTOR-IDENTITY`. The live caller is the `systems-manager` console script. The owner is the `systems_manager` package. The rows reuse the `scion-sdk` helpers and add no second authority. The plan changes no runtime code.

## Technical Context

- **Language/Version**: Python >=3.12,<3.15
- **Primary Dependencies**: scion-sdk[mcp]>=0.6.5,<0.7.0; fastmcp; further pins in `pyproject.toml` (scion-sdk[mcp]>=0.6.5,<0.7.0, pydantic>=2.14.1, psutil>=7.2.2, distro>=1.9.0, requests>=2.34.2)
- **Storage**: N/A, the connector keeps no store of its own
- **Testing**: pytest; each row names the proving test as `path::name`
- **Target Platform**: Linux container and stdio or streamable HTTP MCP clients
- **Project Type**: connector
- **Performance Goals**: N/A, the vendor service sets the latency
- **Constraints**: vendor calls go through the SDK governed client; no connector-local transport
- **Scale/Scope**: 3 active row(s) in this spec

## Constitution Check

- Organization constitution 1.5.0, spec-first change: pass. Every behaviour is a row of this spec with a bound or planned test.
- Repository article R-I, connector scope: pass. The rows stay inside this connector's one external system and reuse the SDK for shared capabilities.

## Project Structure

- `pyproject.toml` (existing)
- `systems_manager/__init__.py` (existing)
- `tests/test_fleet_name.py` (existing)
- `systems_manager/os_provider.py` (existing)
- `tests/test_windows_portability.py` (existing)
- `systems_manager/mcp_server.py` (existing)
- `tests/test_destructive_confirmation_transports.py` (existing)

## Phase 0: Research

No unknowns. Every row names its code and test; the caller chain of each row was read from the code.

## Phase 1: Design

### Summary

This plan states how `systems-manager` delivers the rows of `CONN-SYSTEMS-MANAGER-CONNECTOR-IDENTITY`. The live caller is the `systems-manager` console script. The owner is the `systems_manager` package. The rows reuse the `scion-sdk` helpers and add no second authority. The plan changes no runtime code.

### Technical Context

- **Language/Version**: Python >=3.12,<3.15
- **Primary Dependencies**: scion-sdk[mcp]>=0.6.5,<0.7.0; fastmcp; further pins in `pyproject.toml` (scion-sdk[mcp]>=0.6.5,<0.7.0, pydantic>=2.14.1, psutil>=7.2.2, distro>=1.9.0, requests>=2.34.2)
- **Storage**: N/A, the connector keeps no store of its own
- **Testing**: pytest; each row names the proving test as `path::name`
- **Target Platform**: Linux container and stdio or streamable HTTP MCP clients
- **Project Type**: connector
- **Performance Goals**: N/A, the vendor service sets the latency
- **Constraints**: vendor calls go through the SDK governed client; no connector-local transport
- **Scale/Scope**: 3 active row(s) in this spec

### Constitution Check

- Organization constitution 1.5.0, spec-first change: pass. Every behaviour is a row of this spec with a bound or planned test.
- Repository article R-I, connector scope: pass. The rows stay inside this connector's one external system and reuse the SDK for shared capabilities.

### Project Structure

- `pyproject.toml` (existing)
- `systems_manager/__init__.py` (existing)
- `tests/test_fleet_name.py` (existing)
- `tests/test_windows_portability.py` (existing)
- `tests/test_destructive_confirmation_transports.py` (existing)
- `tests/test_mcp_security_policy.py` (existing)

### Phase 0: Research

No unknowns. Every row names its code and test; the caller chain of each row was read from the code.

### Phase 1: Design

### Summary

This plan states how `systems-manager` delivers the rows of `CONN-SYSTEMS-MANAGER-CONNECTOR-IDENTITY`. The live caller is the `systems-manager` console script. The owner is the `systems_manager` package. The rows reuse the `scion-sdk` helpers and add no second authority. The plan changes no runtime code.

### Technical Context

- **Language/Version**: Python >=3.12,<3.15
- **Primary Dependencies**: scion-sdk[mcp]>=0.6.5,<0.7.0; fastmcp; further pins in `pyproject.toml` (scion-sdk[mcp]>=0.6.5,<0.7.0, pydantic>=2.14.1, psutil>=7.2.2, distro>=1.9.0, requests>=2.34.2)
- **Storage**: N/A, the connector keeps no store of its own
- **Testing**: pytest; each row names the proving test as `path::name`
- **Target Platform**: Linux container and stdio or streamable HTTP MCP clients
- **Project Type**: connector
- **Performance Goals**: N/A, the vendor service sets the latency
- **Constraints**: vendor calls go through the SDK governed client; no connector-local transport
- **Scale/Scope**: 3 active row(s) in this spec

### Constitution Check

- Organization constitution 1.5.0, spec-first change: pass. Every behaviour is a row of this spec with a bound or planned test.
- Repository article R-I, connector scope: pass. The rows stay inside this connector's one external system and reuse the SDK for shared capabilities.

### Project Structure

- `pyproject.toml` (existing)
- `systems_manager/__init__.py` (existing)
- `tests/test_fleet_name.py` (existing)
- `tests/test_windows_portability.py` (existing)
- `tests/test_destructive_confirmation_transports.py` (existing)
- `tests/test_mcp_security_policy.py` (existing)

### Phase 0: Research

No unknowns. Every row names its code and test; the caller chain of each row was read from the code.

### Phase 1: Design

### Architecture

`pyproject.toml` declares the fleet name once. The manifest, fingerprints and ingest binding carry the same name.

### Phase 2: Task approach

`tasks.md` holds one task per row, producer first. Rows that depend on none run in parallel. A task is checked when its `Spec:` trailer is on the default branch.

### Complexity Tracking

None. The constitution check passed.

### Build contract

- `pre-commit run --all-files` runs ruff check, ruff format, the shared `connector-standard`, `spec`, `secrets` and `dependency-readiness` gates at the pinned shared revision.
- `uv run pytest tests` runs the proving tests; the shared complexity, duplication and KISS gates apply their org thresholds and this repository sets no local override.
- A change adds no scanner suppression and no duplicate implementation of an SDK helper.

### Production caller chain

- `CONN-SYSTEMS-MANAGER-CONNECTOR-IDENTITY-R001`: `systems-manager` in `pyproject.toml` runs `systems_manager.systems_manager:main`, which builds the server from the `scion_sdk.connector` entry point `systems_manager:connector` (`systems_manager/__init__.py:11`); `connector_name("systems_manager")` in the SDK resolves the same entry point name for the content pack, the manifest and the ingest binding.

### Cross-repo seams

None. The rows depend only on the published `scion-sdk` package, which the connector imports.

### Phase 2: Task approach

`tasks.md` holds one task per row, producer first. Rows that depend on none run in parallel. A task is checked when its `Spec:` trailer is on the default branch.

### Complexity Tracking

None. The constitution check passed.

### Build contract

- `pre-commit run --all-files` runs ruff check, ruff format, the shared `connector-standard`, `spec`, `secrets` and `dependency-readiness` gates at the pinned shared revision.
- `uv run pytest tests` runs the proving tests; the shared complexity, duplication and KISS gates apply their org thresholds and this repository sets no local override.
- A change adds no scanner suppression and no duplicate implementation of an SDK helper.

### Production caller chain

- `CONN-SYSTEMS-MANAGER-CONNECTOR-IDENTITY-R001`: `systems-manager` in `pyproject.toml` runs `systems_manager.systems_manager:main`, which builds the server from the `scion_sdk.connector` entry point `systems_manager:connector` (`systems_manager/__init__.py:11`); `connector_name("systems_manager")` in the SDK resolves the same entry point name for the content pack, the manifest and the ingest binding.

### Cross-repo seams

None. The rows depend only on the published `scion-sdk` package, which the connector imports.

## Phase 2: Task approach

`tasks.md` holds one task per row, producer first. Rows that depend on none run in parallel. A task is checked when its `Spec:` trailer is on the default branch.

## Complexity Tracking

None. The constitution check passed.

## Build contract

- `pre-commit run --all-files` runs ruff check, ruff format, the shared `connector-standard`, `spec`, `secrets` and `dependency-readiness` gates at the pinned shared revision.
- `uv run pytest tests` runs the proving tests; the shared complexity, duplication and KISS gates apply their org thresholds and this repository sets no local override.
- A change adds no scanner suppression and no duplicate implementation of an SDK helper.

## Production caller chain

- `CONN-SYSTEMS-MANAGER-CONNECTOR-IDENTITY-R001`: `systems-manager` in `pyproject.toml` runs `systems_manager.systems_manager:main`, which builds the server from the `scion_sdk.connector` entry point `systems_manager:connector` (`systems_manager/__init__.py:11`); `connector_name("systems_manager")` in the SDK resolves the same entry point name for the content pack, the manifest and the ingest binding.
- `CONN-SYSTEMS-MANAGER-CONNECTOR-IDENTITY-R002`: the package imports on every platform; each OS branch of `systems_manager/os_provider.py` and the managers selects by `platform.system`.
- `CONN-SYSTEMS-MANAGER-CONNECTOR-IDENTITY-R003`: a client calls a mutating `sm_*` tool of `systems_manager/mcp_server.py` on stdio or HTTP; the SDK refuses a client that cannot elicit and did not send `confirm=true`.

## Cross-repo seams

None. The rows depend only on the published `scion-sdk` package, which the connector imports.
