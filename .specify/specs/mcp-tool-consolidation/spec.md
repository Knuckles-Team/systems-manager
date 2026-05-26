# Specification: MCP Tool Consolidation

This specification defines the migration of the 22 standalone Agent OS tools in `systems-manager` into 6 unified, cohesive action-based tools.

## User Stories

*   **As an AI Agent**, I want a **compact, cohesive set of tools** so that **I can interact with Systems Manager without being overwhelmed by a large number of granular tools**, resulting in lower context token usage and higher selection accuracy.
*   **As a Developer**, I want to **refactor monolithic/god modules into highly cohesive operations** so that **the codebase maintains a clean, professional architecture that scores high on static quality scans**.

## Functional Requirements

- **FR-ID-001**: Consolidate `issue_agent_identity`, `verify_agent_identity`, `revoke_agent_identity`, and `list_agent_identities` into `sm_agent_identity_operations`.
- **FR-PO-002**: Consolidate `list_agent_policies`, `get_agent_policy`, `update_agent_policy`, and `reload_policies` into `sm_agent_policy_operations`.
- **FR-SP-003**: Consolidate `install_specialist`, `uninstall_specialist`, `list_specialists`, and `search_specialists` into `sm_agent_specialist_operations`.
- **FR-SC-004**: Consolidate `get_scheduler_stats`, `list_agent_processes`, `preempt_process`, and `reset_agent_quota` into `sm_agent_scheduler_operations`.
- **FR-WD-005**: Consolidate `check_file_change`, `list_active_watchers`, and `drain_pending_triggers` into `sm_agent_watchdog_operations`.
- **FR-MT-006**: Consolidate `list_maintenance_tasks`, `run_maintenance_now`, `schedule_maintenance`, and `get_maintenance_log` into `sm_agent_maintenance_operations`.

## Success Criteria

- Preserve 100% feature parity with old tools.
- Implement robust unit/integration tests covering all 6 collapsed tools and their respective literal actions.
- Achieve 100% test success rate.
