# CONN-SYSTEMS-MANAGER-CONNECTOR-IDENTITY — The connector is filed under its fleet name

Owner: systems-manager. Cross-repo IDs: `SCION-CONNECTOR-CONTROL-R071`, `PIPE-GATES-R010`.

## Purpose and user stories

The engine and arbora list a connector's tools and ingest under its fleet name. This connector's fleet name is `systems-manager-mcp`.

## Delivery mapping

Component: systems-manager connector

Code: ../../systems_manager/__init__.py

## Why a new spec

Searched `specs/` of `systems-manager` with `git grep` for the terms of this spec. No other spec of this repository owns the capability, so this spec owns it.

## User Scenarios & Testing

### User Story 1 - Fleet name (Priority: P1)

The fleet operator and the engine rely on this behaviour of `systems-manager`: `pyproject.toml` declares `systems-manager-mcp` as the single `scion_sdk.connector` entry point. It is proven independently of the other stories.

**Acceptance Scenarios**:

1. **Given** the `systems-manager` connector built from the default branch, **When** `tests/test_fleet_name.py::test_connector_name_is_the_fleet_name` runs, **Then** every connector name in the package is `systems-manager-mcp`.

### User Story 2 - Windows portability (Priority: P1)

The fleet operator and the engine rely on this behaviour of `systems-manager`: The package imports and runs on Windows with no POSIX-only module or API (`pwd`, `grp`, `fcntl`, `termios`, `resource`, `getloadavg`, `killpg`, `sudo`, `bash`, a hard-coded `/` volume root). It is proven independently of the other stories.

**Acceptance Scenarios**:

1. **Given** the `systems-manager` connector built from the default branch, **When** `tests/test_windows_portability.py::test_package_imports_no_posix_only_modules` runs, **Then** every Windows branch passes under monkeypatched `platform.system` / `os.name`, and the Windows CI job runs the full suite.

### User Story 3 - Mutations refuse cleanly and accept `confirm=true` (Priority: P1)

The fleet operator and the engine rely on this behaviour of `systems-manager`: Every mutating tool (`sm_system_operations`, `sm_service_operations`, `sm_process_operations`, `sm_file_operations` `manage_file`, `sm_cron_operations`, `sm_firewall_operations`, `sm_advanced_operations`, `manage_service`, `start_system_trace`, `stop_system_trace`) takes `confirm`, in addition to administrator policy, and decides through the SDK `ctx_confirm_destructive`. It is proven independently of the other stories.

**Acceptance Scenarios**:

1. **Given** the `systems-manager` connector built from the default branch, **When** `tests/test_destructive_confirmation_transports.py::test_stdio_no_auth_mutation` runs, **Then** a non-eliciting client is refused with `confirm=true` named, then succeeds with `confirm=true`, on every transport.

### Edge Cases

- The vendor service is unreachable or rejects the credential: the connector returns the SDK typed error and never a partial result.
- An argument outside the documented inputs is refused with the SDK typed refusal and causes no effect on the vendor service.

## Requirements

- **FR-001**: Fleet name. Rows: `CONN-SYSTEMS-MANAGER-CONNECTOR-IDENTITY-R001`.
- **FR-002**: Windows portability. Rows: `CONN-SYSTEMS-MANAGER-CONNECTOR-IDENTITY-R002`.
- **FR-003**: Mutations refuse cleanly and accept `confirm=true`. Rows: `CONN-SYSTEMS-MANAGER-CONNECTOR-IDENTITY-R003`.

## Success Criteria

- **SC-001**: Every connector name in the package is `systems-manager-mcp`. Rows: `CONN-SYSTEMS-MANAGER-CONNECTOR-IDENTITY-R001`.
- **SC-002**: Every Windows branch passes under monkeypatched `platform.system` / `os.name`, and the Windows CI job runs the full suite. Rows: `CONN-SYSTEMS-MANAGER-CONNECTOR-IDENTITY-R002`.
- **SC-003**: A non-eliciting client is refused with `confirm=true` named, then succeeds with `confirm=true`, on every transport. Rows: `CONN-SYSTEMS-MANAGER-CONNECTOR-IDENTITY-R003`.

## Assumptions

- The `systems-manager` package keeps the entry point and module layout named in the rows.
- The shared SDK supplies the transport, authentication, retry and certification helpers the rows reuse.

## Traceability

| Label | Rows | Design section | Test ID | Evidence |
|---|---|---|---|---|
| FR-001 | `CONN-SYSTEMS-MANAGER-CONNECTOR-IDENTITY-R001` | plan.md Production caller chain | T-001 | tests/test_fleet_name.py::test_connector_name_is_the_fleet_name |
| FR-002 | `CONN-SYSTEMS-MANAGER-CONNECTOR-IDENTITY-R002` | plan.md Production caller chain | T-002 | tests/test_windows_portability.py::test_package_imports_no_posix_only_modules |
| FR-003 | `CONN-SYSTEMS-MANAGER-CONNECTOR-IDENTITY-R003` | plan.md Production caller chain | T-003 | tests/test_destructive_confirmation_transports.py::test_stdio_no_auth_mutation |
