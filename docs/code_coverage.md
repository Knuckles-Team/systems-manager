# Validation

Coverage percentages and statement counts are release artifacts, not durable
documentation. Generate them from the exact source revision under review; do
not copy old metrics into this page.

## Release checks

The current contract is validated by focused suites for:

- strict action discovery and intent routing;
- default-deny security middleware and bounded approval;
- Linux and Windows provider behavior;
- managed-root path confinement, symlink rejection, scan budgets, and
  privacy-safe result paths;
- repository allowlists and SHA-256-verified local packages;
- BMC credential projection and storage-health correlation;
- opaque knowledge-graph projection and native ingestion;
- current Agent OS public authorities;
- remote authentication and TLS startup invariants; and
- skill metadata and direct GraphOS-compatible tool invocation.

Run tests in bounded groups on constrained WSL or CI workers so each Python
process releases its imported server state before the next group. The CI
pipeline remains the authority for the exact test count and coverage result.

```bash
pytest -q tests/test_mcp_routing.py tests/test_mcp_security_policy.py
pytest -q tests/test_security_boundaries.py tests/test_storage_health.py
pytest -q tests/test_linux_managers.py tests/test_windows_manager.py
```

For a coverage artifact, use the repository's pinned test environment:

```bash
pytest --cov=systems_manager --cov-report=term-missing
```

Also run `ruff`, `black --check`, `mkdocs build --strict`, the skill validator,
the release-artifact gate, and the security sanitizer before publication.
