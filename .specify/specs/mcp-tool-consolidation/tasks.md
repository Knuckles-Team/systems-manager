# SDD Checklist: MCP Tool Consolidation

Track the steps required to implement the tool consolidation.

- [x] Task 1: Refactor `systems_manager/agent_os_tools.py`
    - [x] 1.1: Define sub-action Literal choice models for each of the 6 collapsed tools.
    - [x] 1.2: Collapse identity tools into `sm_agent_identity_operations`.
    - [x] 1.3: Collapse policy tools into `sm_agent_policy_operations`.
    - [x] 1.4: Collapse specialist tools into `sm_agent_specialist_operations`.
    - [x] 1.5: Collapse scheduler tools into `sm_agent_scheduler_operations`.
    - [x] 1.6: Collapse watchdog tools into `sm_agent_watchdog_operations`.
    - [x] 1.7: Collapse maintenance tools into `sm_agent_maintenance_operations`.
- [x] Task 2: Update MCP registrations in `systems_manager/mcp_server.py`
- [x] Task 3: Create tests in `tests/test_collapsed_tools.py`
    - [x] 3.1: Test `sm_agent_identity_operations` actions.
    - [x] 3.2: Test `sm_agent_policy_operations` actions.
    - [x] 3.3: Test `sm_agent_specialist_operations` actions.
    - [x] 3.4: Test `sm_agent_scheduler_operations` actions.
    - [x] 3.5: Test `sm_agent_watchdog_operations` actions.
    - [x] 3.6: Test `sm_agent_maintenance_operations` actions.
- [x] Task 4: Verify test suite and code coverage
