# Code Enhancement: systems-manager

> Automated code enhancement review for systems-manager. Covers 17 analysis domains.

## User Stories

- As a **developer**, I want to **address Project Analysis findings (grade: C, score: 74)**, so that **improve project project analysis from C to at least B (80+)**.
- As a **developer**, I want to **address Codebase Optimization findings (grade: F, score: 56)**, so that **improve project codebase optimization from F to at least B (80+)**.
- As a **developer**, I want to **address Architecture & Design Patterns findings (grade: D, score: 65)**, so that **improve project architecture & design patterns from D to at least B (80+)**.
- As a **developer**, I want to **address Concept Traceability findings (grade: F, score: 25)**, so that **improve project concept traceability from F to at least B (80+)**.
- As a **developer**, I want to **address Linting & Formatting findings (grade: F, score: 0)**, so that **improve project linting & formatting from F to at least B (80+)**.
- As a **developer**, I want to **address Changelog Audit findings (grade: C, score: 75)**, so that **improve project changelog audit from C to at least B (80+)**.
- As a **developer**, I want to **address Pytest Quality findings (grade: D, score: 64)**, so that **improve project pytest quality from D to at least B (80+)**.

## Functional Requirements

- **FR-001**: 4 functions exceed 200 lines (actionable refactoring targets): register_system_tools (818L), register_system_management_tools (396L), register_os_provider_tools (268L), register_service_tools (240L)
- **FR-002**: Monolithic: mcp_server.py (2989L) — 5 functions with high complexity (worst: register_system_tools at 818L, CC=62); Low cohesion: 20 distinct concepts in one file
- **FR-003**: Monolithic: systems_manager.py (2885L) — 9 functions with high complexity (worst: systems_manager at 140L, CC=21); Low cohesion: 16 distinct concepts in one file
- **FR-004**: Needs attention: agent_os_tools.py (735L) — Low cohesion: 14 distinct concepts in one file
- **FR-005**: 14 functions with nesting depth >4
- **FR-006**: 17 potential doc-test drift items
- **FR-007**: README.md missing sections: installation
- **FR-008**: README missing: Has a Table of Contents
- **FR-009**: README missing: References /docs directory material
- **FR-010**: SRP: 7 modules exceed 500 lines (god modules)
- **FR-011**: SRP: 8 classes have >15 methods
- **FR-012**: No discernible layer architecture (no domain/service/adapter separation)
- **FR-013**: Low dependency injection ratio: 9%
- **FR-014**: Low traceability ratio: 0% concepts fully traced
- **FR-015**: 8 orphaned concepts (only in one source)
- **FR-016**: 359 test functions missing concept markers
- **FR-017**: 218 significant functions (>10 lines) missing concept markers in docstrings
- **FR-018**: Total lint findings: 326 (high/error: 324, medium/warning: 2, low: 0)
- **FR-019**: 1 hook(s) may be outdated: ruff-pre-commit
- **FR-020**: 124 test execution error(s)
- **FR-021**: 1 rogue/throwaway scripts detected (fix_*, validate_*, patch_*, etc.): scripts/validate_a2a_agent.py
- **FR-022**: CHANGELOG.md is missing — create one following Keep a Changelog format
- **FR-023**: CHANGELOG.md is missing
- **FR-024**: 4 test files exceed 500 lines — split into focused modules
- **FR-025**: 4 test files have >30 tests — too dense
- **FR-026**: Test directory lacks subdirectory organization (consider unit/, integration/, e2e/)
- **FR-027**: No @pytest.mark.parametrize usage — consider data-driven tests
- **FR-028**: 4 tests have no assertions
- **FR-029**: 252 tests use weak assertions (assert result is not None, assert True, etc.)
- **FR-030**: Undocumented env vars: ENABLE_OTEL, EUNOMIA_REMOTE_URL, LLM_API_KEY, LLM_BASE_URL, OAUTH_BASE_URL, OAUTH_UPSTREAM_AUTH_ENDPOINT, OAUTH_UPSTREAM_CLIENT_ID, OAUTH_UPSTREAM_CLIENT_SECRET, OAUTH_UPSTREAM_TOKEN_ENDPOINT, OSPROVIDERTOOL
- **FR-031**: 29 Python env vars not in .env.example: AGENT_OSTOOL, AGENT_POLICIES_PATH, CRONTOOL, DISKTOOL, FILESYSTEMTOOL

## Success Criteria

- Overall GPA: 2.53 → 3.0
- Domains at B or above: 10 → 17
- Actionable findings: 31 → 0
