# CONN-SYSTEMS-MANAGER-CONNECTOR-CONTENT — The connector serves its packaged content

Owner: systems-manager. Cross-repo IDs: `SCION-CONNECTOR-CONTROL-R071`, `SCION-CONNECTOR-CONTROL-R073`.

## Purpose and user stories

The `systems-manager-mcp` server serves its packaged skills, prompts and ontology to any client, with no wiring of its own.

## Delivery mapping

Component: systems-manager connector

Code: ../../systems_manager/__init__.py

## Why a new spec

Searched `specs/` of `systems-manager` with `git grep` for the terms of this spec. No other spec of this repository owns the capability, so this spec owns it.

## User Scenarios & Testing

### User Story 1 - Default content (Priority: P1)

The fleet operator and the engine rely on this behaviour of `systems-manager`: `pyproject.toml` declares `systems-manager-mcp` as the single `scion_sdk.connector` entry point. It is proven independently of the other stories.

**Acceptance Scenarios**:

1. **Given** the `systems-manager` connector built from the default branch, **When** `tests/test_default_content_surfaces.py::test_default_content_surfaces` runs, **Then** `resources/list` includes `skill://` and `ontology://`; `prompts/list` includes each packaged prompt.

### User Story 2 - Declare access contracts for the competency reads of systems-manager (Priority: P1)

The fleet operator and the engine rely on this behaviour of `systems-manager`: Subsystem: connector `systems-manager`. It is proven independently of the other stories.

**Acceptance Scenarios**:

1. **Given** the `systems-manager` connector built from the default branch, **When** `tests/test_access_contracts.py::test_competency_contracts_certified` runs, **Then** test: `tests/test_access_contracts.py::test_competency_contracts_certified` (L2) runs the connector ontology certification and validates each recording against its contract.

### User Story 3 - Prove service lifecycle parity across Linux, Windows and macOS (Priority: P1)

The fleet operator and the engine rely on this behaviour of `systems-manager`: Caller: `tools/call` → `systems_manager/mcp_server.py::sm_service_operations` → `systems_manager/os_provider.py::manage_service` and `query_system_logs`. It is proven independently of the other stories.

**Acceptance Scenarios**:

1. **Given** the `systems-manager` connector built from the default branch, **When** `systems_manager/mcp_server.py::sm_service_operations` runs, **Then** test: `tests/test_service_parity_served.py::test_service_lifecycle_parity_by_platform` (L3) with a recorded command runner per platform.

### User Story 4 - Register the workspace reader (Priority: P2)

The fleet operator and the engine rely on this behaviour of `systems-manager`: Subsystem: connector. It is proven independently of the other stories.

**Acceptance Scenarios**:

1. **Given** the `systems-manager` connector built from the default branch, **When** `tests/test_workspace_tool_served.py::test_tool_reads_root_and_refuses_traversal` runs, **Then** test: `tests/test_workspace_tool_served.py::test_tool_reads_root_and_refuses_traversal` (L3).

### Edge Cases

- The vendor service is unreachable or rejects the credential: the connector returns the SDK typed error and never a partial result.
- An argument outside the documented inputs is refused with the SDK typed refusal and causes no effect on the vendor service.

## Requirements

- **FR-001**: Default content. Rows: `CONN-SYSTEMS-MANAGER-CONNECTOR-CONTENT-R001`.
- **FR-002**: Declare access contracts for the competency reads of systems-manager. Rows: `CONN-SYSTEMS-MANAGER-CONNECTOR-CONTENT-R002`.
- **FR-003**: Prove service lifecycle parity across Linux, Windows and macOS. Rows: `CONN-SYSTEMS-MANAGER-CONNECTOR-CONTENT-R003`.
- **FR-004**: Register the workspace reader. Rows: `CONN-SYSTEMS-MANAGER-CONNECTOR-CONTENT-R004`.

## Success Criteria

- **SC-001**: `resources/list` includes `skill://` and `ontology://`; `prompts/list` includes each packaged prompt. Rows: `CONN-SYSTEMS-MANAGER-CONNECTOR-CONTENT-R001`.
- **SC-002**: Test: `tests/test_access_contracts.py::test_competency_contracts_certified` (L2) runs the connector ontology certification and validates each recording against its contract. Rows: `CONN-SYSTEMS-MANAGER-CONNECTOR-CONTENT-R002`.
- **SC-003**: Test: `tests/test_service_parity_served.py::test_service_lifecycle_parity_by_platform` (L3) with a recorded command runner per platform. Rows: `CONN-SYSTEMS-MANAGER-CONNECTOR-CONTENT-R003`.
- **SC-004**: Test: `tests/test_workspace_tool_served.py::test_tool_reads_root_and_refuses_traversal` (L3). Rows: `CONN-SYSTEMS-MANAGER-CONNECTOR-CONTENT-R004`.

## Assumptions

- The `systems-manager` package keeps the entry point and module layout named in the rows.
- The shared SDK supplies the transport, authentication, retry and certification helpers the rows reuse.

## Traceability

| Label | Rows | Design section | Test ID | Evidence |
|---|---|---|---|---|
| FR-001 | `CONN-SYSTEMS-MANAGER-CONNECTOR-CONTENT-R001` | plan.md Production caller chain | T-001 | tests/test_default_content_surfaces.py::test_default_content_surfaces |
| FR-002 | `CONN-SYSTEMS-MANAGER-CONNECTOR-CONTENT-R002` | plan.md Production caller chain | T-002 | tests/test_access_contracts.py::test_competency_contracts_certified |
| FR-003 | `CONN-SYSTEMS-MANAGER-CONNECTOR-CONTENT-R003` | plan.md Production caller chain | T-003 | systems_manager/mcp_server.py::sm_service_operations |
| FR-004 | `CONN-SYSTEMS-MANAGER-CONNECTOR-CONTENT-R004` | plan.md Production caller chain | T-004 | tests/test_workspace_tool_served.py::test_tool_reads_root_and_refuses_traversal |
