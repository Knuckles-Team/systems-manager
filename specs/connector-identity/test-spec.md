# CONN-SYSTEMS-MANAGER-CONNECTOR-IDENTITY — Test specification

Governing spec: [spec.md](spec.md).

| Test ID | Requirement | Proving test | Expected observation |
|---|---|---|---|
| T-001 | `CONN-SYSTEMS-MANAGER-CONNECTOR-IDENTITY-R001` | `tests/test_fleet_name.py::test_connector_name_is_the_fleet_name` | Every connector name in the package is `systems-manager-mcp`. |
| T-002 | `CONN-SYSTEMS-MANAGER-CONNECTOR-IDENTITY-R002` | `tests/test_windows_portability.py::test_package_imports_no_posix_only_modules` | Every Windows branch passes under monkeypatched `platform.system` / `os.name`, and the Windows CI job runs the full suite. |
| T-003 | `CONN-SYSTEMS-MANAGER-CONNECTOR-IDENTITY-R003` | `tests/test_destructive_confirmation_transports.py::test_stdio_no_auth_mutation` | A non-eliciting client is refused with `confirm=true` named, then succeeds with `confirm=true`, on every transport. |

## Negative and boundary cases

Each proving test above includes the refusal or error case that its row names. A vendor outage or an unauthorised call must return the SDK typed error.

## Quality and release proof

Run `uv run pytest tests` and `pre-commit run --all-files` from the repository root. A planned test is added by the code change that lands the row.
