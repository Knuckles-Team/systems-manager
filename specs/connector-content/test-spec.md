# CONN-SYSTEMS-MANAGER-CONNECTOR-CONTENT — Test specification

Governing spec: [spec.md](spec.md).

| Test ID | Requirement | Proving test | Expected observation |
|---|---|---|---|
| T-001 | `CONN-SYSTEMS-MANAGER-CONNECTOR-CONTENT-R001` | `tests/test_default_content_surfaces.py::test_default_content_surfaces` | `resources/list` includes `skill://` and `ontology://`; `prompts/list` includes each packaged prompt. |
| T-002 | `CONN-SYSTEMS-MANAGER-CONNECTOR-CONTENT-R002` | `tests/test_access_contracts.py::test_competency_contracts_certified` | Test: `tests/test_access_contracts.py::test_competency_contracts_certified` (L2) runs the connector ontology certification and validates each recording against its contract. |
| T-003 | `CONN-SYSTEMS-MANAGER-CONNECTOR-CONTENT-R003` | `systems_manager/mcp_server.py::sm_service_operations` | Test: `tests/test_service_parity_served.py::test_service_lifecycle_parity_by_platform` (L3) with a recorded command runner per platform. |
| T-004 | `CONN-SYSTEMS-MANAGER-CONNECTOR-CONTENT-R004` | `tests/test_workspace_tool_served.py::test_tool_reads_root_and_refuses_traversal` (planned) | Test: `tests/test_workspace_tool_served.py::test_tool_reads_root_and_refuses_traversal` (L3). |
| T-005 | `CONN-SYSTEMS-MANAGER-CONNECTOR-CONTENT-R005` | `tests/test_ontology_extends_core.py::test_pack_declares_no_core_term` | The served Turtle declares none of the listed core terms. |

## Negative and boundary cases

Each proving test above includes the refusal or error case that its row names. A vendor outage or an unauthorised call must return the SDK typed error.

## Quality and release proof

Run `uv run pytest tests` and `pre-commit run --all-files` from the repository root. A planned test is added by the code change that lands the row.

## Machine roll-up proofs

- `CONN-SYSTEMS-MANAGER-CONNECTOR-CONTENT-R006`: `tests/test_machine_rollup.py::test_pack_class_reaches_the_core_machine` (planned; the owning change adds the test)
- `CONN-SYSTEMS-MANAGER-CONNECTOR-CONTENT-R006.1`: `tests/test_machine_rollup.py::test_hardware_node_rolls_up_to_machine_and_uuid_observes` (planned; the owning change adds the test)
- `CONN-SYSTEMS-MANAGER-CONNECTOR-CONTENT-R006.2`: `tests/test_machine_rollup.py::test_roll_up_is_wired_into_the_pack_and_ingest` (planned; the owning change adds the test)
- `CONN-SYSTEMS-MANAGER-CONNECTOR-CONTENT-R006.3`: `tests/test_machine_rollup.py::test_pack_class_reaches_the_core_machine` (planned; the owning change adds the test)
