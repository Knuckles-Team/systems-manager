# Code Enhancement: systems-manager

> Automated code enhancement review for systems-manager. Covers 17 analysis domains.

## User Stories

- As a **developer**, I want to **address Project Analysis findings (grade: C, score: 74)**, so that **improve project project analysis from C to at least B (80+)**.
- As a **developer**, I want to **address Codebase Optimization findings (grade: D, score: 67)**, so that **improve project codebase optimization from D to at least B (80+)**.
- As a **developer**, I want to **address Test Coverage findings (grade: C, score: 75)**, so that **improve project test coverage from C to at least B (80+)**.
- As a **developer**, I want to **address Architecture & Design Patterns findings (grade: C, score: 70)**, so that **improve project architecture & design patterns from C to at least B (80+)**.
- As a **developer**, I want to **address Concept Traceability findings (grade: F, score: 25)**, so that **improve project concept traceability from F to at least B (80+)**.
- As a **developer**, I want to **address Test Execution findings (grade: F, score: 25)**, so that **improve project test execution from F to at least B (80+)**.
- As a **developer**, I want to **address Version Sync Analysis findings (grade: D, score: 60)**, so that **improve project version sync analysis from D to at least B (80+)**.
- As a **developer**, I want to **address Changelog Audit findings (grade: C, score: 75)**, so that **improve project changelog audit from C to at least B (80+)**.
- As a **developer**, I want to **address Pytest Quality findings (grade: D, score: 63)**, so that **improve project pytest quality from D to at least B (80+)**.
- As a **developer**, I want to **address Environment Variables findings (grade: D, score: 60)**, so that **improve project environment variables from D to at least B (80+)**.
- As a **developer**, I want to **address analyze_xdg_kg findings (grade: F, score: 0)**, so that **improve project analyze_xdg_kg from F to at least B (80+)**.

## Functional Requirements

- **FR-001**: Minor update: pytest-xdist 3.6.0 (constraint — not installed) -> 3.8.0
- **FR-002**: Minor update: agent-utilities 0.2.40 (installed) -> 0.16.0
- **FR-003**: Minor update: psutil 7.1.0 (installed) -> 7.2.2
- **FR-004**: 2 functions exceed 200 lines (actionable refactoring targets): get_mcp_instance (398L), register_os_provider_tools (266L)
- **FR-005**: Monolithic: systems_manager.py (2898L) — 9 functions with high complexity (worst: systems_manager at 140L, CC=21); Low cohesion: 16 distinct concepts in one file
- **FR-006**: Needs attention: agent_os_tools.py (599L) — Low cohesion: 15 distinct concepts in one file
- **FR-007**: 23 functions with nesting depth >4
- **FR-008**: Test suite lacks intent diversity (only one type)
- **FR-009**: 12 potential doc-test drift items
- **FR-010**: README.md missing sections: usage|quick start
- **FR-011**: 2 broken internal links in README.md
- **FR-012**: README missing: Has a Table of Contents
- **FR-013**: README missing: Has usage examples with code blocks
- **FR-014**: SRP: 5 modules exceed 500 lines (god modules)
- **FR-015**: SRP: 2 classes have >15 methods
- **FR-016**: No discernible layer architecture (no domain/service/adapter separation)
- **FR-017**: Low traceability ratio: 0% concepts fully traced
- **FR-018**: 18 orphaned concepts (only in one source)
- **FR-019**: 90 test functions missing concept markers
- **FR-020**: 138 significant functions (>10 lines) missing concept markers in docstrings
- **FR-021**: Total lint findings: 0 (high/error: 0, medium/warning: 0, low: 0)
- **FR-022**: 1 hook(s) may be outdated: ruff-pre-commit
- **FR-023**: 1 rogue/throwaway scripts detected (fix_*, validate_*, patch_*, etc.): scripts/validate_a2a_agent.py
- **FR-024**: Found 2 file(s) with version '1.15.0' that are NOT tracked in .bumpversion.cfg:
- **FR-025**:   - specify_reports/systems-manager/code_enhancement_report.md
- **FR-026**:   - specify_reports/systems-manager/results_static.json
- **FR-027**: CHANGELOG.md exists but could not be parsed — check format compliance
- **FR-028**: No changelog entries within the last 30 days
- **FR-029**: keepachangelog not installed — pip install 'universal-skills[code-enhancer]'
- **FR-030**: 3 test files exceed 500 lines — split into focused modules
- **FR-031**: Test directory lacks subdirectory organization (consider unit/, integration/, e2e/)
- **FR-032**: Low fixture usage: only 19% of tests use fixtures
- **FR-033**: 1 tests have no assertions
- **FR-034**: 24 tests use weak assertions (assert result is not None, assert True, etc.)
- **FR-035**: 34 tests have >5 assertions — consider splitting (single responsibility)
- **FR-036**: 5 tests have excessive mocking (>5 mocks) — test behavior, not implementation
- **FR-037**: 1 tests exceed 100 lines — likely doing too much per test
- **FR-038**: Only 29% of env vars documented in README.md
- **FR-039**: Undocumented env vars: AGENT_POLICIES_PATH, AUTH_TYPE, EUNOMIA_POLICY_FILE, EUNOMIA_TYPE, MAINTENANCE_PRIORITY, MAINTENANCE_TOKEN_BUDGET, MAX_CONCURRENT_AGENTS, MCP_CONFIG_PATH, OTEL_EXPORTER_OTLP_ENDPOINT, OTEL_EXPORTER_OTLP_PROTOCOL
- **FR-040**: 8 Python env vars not in .env.example: AGENT_POLICIES_PATH, MAINTENANCE_PRIORITY, MAINTENANCE_TOKEN_BUDGET, MAX_CONCURRENT_AGENTS, MCP_CONFIG_PATH
- **FR-041**: Analysis error: No module named 'agent_utilities.knowledge_graph'

## Success Criteria

- Overall GPA: 2.06 → 3.0
- Domains at B or above: 6 → 17
- Actionable findings: 41 → 0
