---
name: systems-manager-development
skill_type: skill
description: >-
  Develop, test, and release the systems-manager Python connector. Covers the
  cross-platform systems manager, governed FastMCP server, connector source
  declarations, packaged skills and ontology, documentation, and the repository's
  shared delivery gates. Use before changing a provider tool, MCP boundary,
  connector content, or release metadata.
domain: development
license: MIT
tags: [systems-manager, python, mcp, fastmcp, connector, host-operations, development, gates]
metadata:
  author: Knuckles-Team
  version: '0.1.0'
---

# systems-manager development

`systems-manager` is a Python connector that exposes governed host inspection and
host-lifecycle operations through the Scion SDK. Keep the provider's
runtime boundary narrow: package operations, service/process/network/disk
inspection, storage health, managed-file policy, and typed host telemetry belong
here; durable graph storage, Arbora admission, and deployment credentials belong
to their owning systems.

## Repository map and real entry points

- `systems_manager/mcp_server.py` creates the `systems-manager` FastMCP server,
  registers the OS and storage tool surfaces, enforces policy and approval gates,
  and exposes the `systems-manager-mcp` console script.
- `systems_manager/systems_manager.py` owns the cross-platform manager classes,
  platform detection, validated host operations, and the `systems-manager` CLI.
  `systems_manager/__main__.py` delegates `python -m systems_manager` to that CLI.
- `systems_manager/os_provider.py` contains the cross-platform provider seam;
  `systems_manager/os_provider_tools.py` registers process, network, snapshot,
  service, trace, and kernel-module tools.
- `systems_manager/storage_health.py` and `systems_manager/storage_tools.py`
  implement the read-only SMART, RAID, BMC drive-health, and storage tool seam.
- `systems_manager/connector_sources.py` declares the live connector source and
  schema mappings. `systems_manager/ontology/` carries the data-only ontology,
  mappings, shapes, fixtures, and migration manifest.
- `systems_manager/skills/` contains packaged skills. The operations skill is at
  `systems_manager/skills/systems-manager-operations/SKILL.md`; this development
  skill is packaged beside it. `agent_data/` and `prompts/` are also package data.
- `tests/` contains the unit and MCP contract tests. In particular,
  `tests/test_default_content_surfaces.py` verifies that packaged skills,
  ontology, and prompts remain discoverable through the server.

There is no `systems_manager/agent_server.py` in the current source tree. Do not
document or invoke that stale path; the MCP server entry point is
`systems_manager.mcp_server:mcp_server`.

## Route and inspect before editing

1. Read the workspace boundary and this repository's `AGENTS.md`, then search the
   owning spec with `git grep -n "<term>" -- specs`.
2. Reuse the existing tool registration, policy middleware, provider seam, and
   package-data path before adding a module or compatibility alias.
3. Keep host mutations, sensitive reads, network probes, managed-file writes, and
   BMC credentials behind their existing environment gates and per-operation
   approval. Tests must mock platform commands and never update a live host.
4. For connector content, update `connector_sources.py` or the data-only
   `ontology/` assets through their current SDK contracts. Never put endpoints,
   credentials, hostnames, local paths, or deployment identities in package data.

## Rapid delivery: the 5-minute contract

Specs are already designed. Deliver one small, reviewable slice and keep every
claim tied to a real source path and command.

**Extend first**

- Find the owning row before changing behavior and cite its ID in the commit
  `Spec:` trailer. Never hand-edit generated `specs/*/status.json`.
- Bind a behavior change to an existing test or add a focused test under `tests/`
  with the literal spec marker. The package-content contract belongs in
  `tests/test_default_content_surfaces.py`.
- Keep one implementation of each capability. Do not reintroduce raw shell,
  arbitrary command, compatibility agent-server, or ungoverned credential paths.

**Five-minute delivery**

- Start from a real worktree based on immutable `origin/main`; keep the change
  surgical, and never use `git stash`, force-push, or broad staging.
- Run targeted checks first, then the configured commit and push gates. A missing
  dependency or skipped check is an evidence gap, not a pass.
- Put `Spec:` and `Co-Authored-By:` on consecutive lines in the final paragraph
  of every commit message so the shared trailer gate can read both.

## Development and verification commands

Use a Python 3.12–3.14 environment and the committed `uv.lock`:

```bash
uv sync --locked
uv run python -m systems_manager --help
uv run systems-manager-mcp --help
uv run pytest -q tests/test_default_content_surfaces.py tests/test_mcp_server.py
uv run ruff check systems_manager tests
uv run black --check systems_manager tests
uv run mkdocs build --strict
pre-commit run --all-files
```

The MCP process is `uv run systems-manager-mcp` (or
`uv run python -m systems_manager.mcp_server`) and defaults to stdio. Network
transports require the configured authentication and TLS boundary. The CLI is
`uv run systems-manager`; its supported flags are defined by
`_systems_manager_parser()` in `systems_manager/systems_manager.py`.

For a focused change, run the smallest relevant test module and a package import
smoke check. The full test suite and hosted release workflow remain CI-owned. Do
not replace a targeted check with a live package install, system update, native
build, or a broad environment.

## Connector content and Pages delivery

The repository's canonical Pages caller is `.github/workflows/pages.yml`. It
calls the shared `pages_pipeline.yml@main` workflow with `content_source: docs`,
`spec_dashboard_enabled: true`, and `.config/spec-dashboard.json`. The dashboard
configuration reads the repository-owned `specs/*/status.json` files, and the
workflow trigger includes documentation, specs, the dashboard configuration, and
the caller itself. Keep one Pages publisher; a second `mkdocs gh-deploy` workflow
can race the shared publisher and must be removed or reconciled.

The canonical pre-commit aggregate comes from
`Knuckles-Team/pipelines` at `rev: main` and includes `connector-standard`,
`secrets`, `spec`, `tests-fast`, and `dependency-readiness`. The `spec` and
`tests-fast` hooks run at pre-push. Do not replace this aggregate with marker-only
local checks or a YAML declaration that cannot be validated with
`pre-commit validate-config`.

## Safety and release discipline

- Preserve `mcp_server.py`'s fail-closed tool classification, bounded blocking
  operations, mutation serialization, filesystem boundary, and explicit approval.
- Keep the `systems-manager-mcp` source declaration and ontology package data
  importable without starting a host operation. Do not disclose local paths or
  credentials in traces, docs, fixtures, or errors.
- When packaged behavior or a skill changes, bump the release with the registered
  `.bumpversion.cfg` files, refresh `uv.lock`, and verify the version mirrors and
  lockfile together before review. Never hand-edit one version mirror.
- Review the exact candidate head and its hosted checks before merging. After a
  merge, verify the Pages run is for that exact main SHA and that the public
  `/spec-delivery/` page is reachable before calling the delivery complete.
