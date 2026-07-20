# AGENTS.md

> Claude Code loads this file via `CLAUDE.md` (`@AGENTS.md` import) — the two stay
> in sync. Edit **this** file, not `CLAUDE.md`.

## Tech Stack & Architecture
- Language/Version: Python 3.11–3.14
- Core Libraries: `agent-utilities`, `fastmcp`, `pydantic-ai`, `psutil`, `distro`
- Key principles: Functional patterns, Pydantic for data validation, asynchronous tool execution.
- Architecture:
    - `mcp_server.py`: Main MCP server entry point and tool registration.
    - `agent.py`: Pydantic AI agent definition and logic.
    - `storage_health.py`: Physical-disk + BMC drive-fault health (CONCEPT:SM-OS.governance.sys-8/1.5)
      — SMART (incl. RAID `megaraid` passthrough), BMC/IPMI drive-slot faults, RAID PD
      state, correlated; runs over the manager seam (local or remote host).
    - `bmc_credentials.py`: consumes an exact runtime credential projection resolved by
      AgentConfig from an external secret reference.
    - `skills/`: Directory containing modular agent skills (if applicable).

### Architecture Diagram
```mermaid
graph TD
    User([User/A2A]) --> Server[A2A Server / FastAPI]
    Server --> Agent[Pydantic AI Agent]
    Agent --> MCP[MCP Server / FastMCP]
    MCP --> Client[API Client / Wrapper]
    MCP --> Storage[sm_storage_health — SM-OS.governance.sys-8/1.5]
    Storage --> Mgr[manager.run_command — local or remote]
    Storage --> SMART([smartctl / megaraid])
    Storage --> BMC([fan-manager IPMI / ipmitool])
    Storage -.OOB credential projection.-> Config([AgentConfig secret reference])
    Client --> ExternalAPI([External Service API])
```

### Workflow Diagram
```mermaid
sequenceDiagram
    participant U as User
    participant S as Server
    participant A as Agent
    participant M as MCP Tools
    participant SM as Systems Manager
    participant PM as Package Manager
    participant SYS as System APIs

    U->>S: Request
    S->>A: Process Query
    A->>M: Invoke Tool
    M->>SM: Execute System Operation
    SM->>PM: Package Management
    SM->>SYS: System APIs
    PM-->>SM: Package Result
    SYS-->>SM: System Result
    SM-->>M: Operation Result
    M-->>A: Tool Result
    A-->>S: Final Response
    S-->>U: Output
```

## Commands (run these exactly)
# Installation
pip install .[all]

# Quality & Linting (run from project root)
pre-commit run --all-files

# Testing
pytest tests/ --cov=systems_manager --cov-report=term-missing

# Execution Commands
# systems-manager CLI
python -m systems_manager.systems_manager

# systems-manager MCP
python -m systems_manager.mcp_server

# systems-manager Agent
python -m systems_manager.agent_server

## Project Structure Quick Reference
- MCP Entry Point → `mcp_server.py`
- Agent Entry Point → `agent_server.py`
- Core Systems Manager → `systems_manager.py`
- Source Code → `systems_manager/`
- Agent Data → `agent_data/`
- Tests → `tests/`

### File Tree
```text
├── .bumpversion.cfg\n├── .dockerignore\n├── .env\n├── .gitattributes\n├── .github\n│   └── workflows\n│       └── pipeline.yml\n├── .gitignore\n├── .pre-commit-config.yaml\n├── AGENTS.md\n├── Dockerfile\n├── LICENSE\n├── MANIFEST.in\n├── README.md\n├── compose.yml\n├── debug.Dockerfile\n├── mcp.compose.yml\n├── pyproject.toml\n├── pytest.ini\n├── requirements.txt\n├── scripts\n│   └── validate_a2a_agent.py\n├── systems_manager\n│   ├── __init__.py\n│   ├── __main__.py\n│   ├── agent_server.py\n│   ├── mcp_server.py\n│   └── systems_manager.py\n├── test_ag_ui.py\n└── tests\n    ├── health_check2.py\n    ├── test_ag_ui.py\n    ├── test_fastmcp_server.py\n    ├── test_fastmcp_error.py\n    └── test_get_system_logs.py
```

## Code Style & Conventions
**Always:**
- Use current direct `agent-utilities` modules for shared patterns.
- Define input/output models using Pydantic.
- Include descriptive docstrings for all tools (they are used as tool descriptions for LLMs).
- Check for optional dependencies using `try/except ImportError`.
- Use type hints for function signatures.

**Good example:**
```python
from agent_utilities.mcp.server_factory import create_mcp_server
from fastmcp import FastMCP
from pydantic import Field

mcp = create_mcp_server("my-agent")

@mcp.tool()
async def my_tool(param: str = Field(description="Tool parameter")) -> str:
    """Description for LLM."""
    return f"Result: {param}"
```

## Dos and Don'ts
**Do:**
- Run `pre-commit` before pushing changes.
- Use existing patterns from `agent-utilities`.
- Keep tools focused and idempotent where possible.
- Run pytest with coverage before committing.
- Mock platform-specific operations in tests for cross-platform compatibility.

**Don't:**
- Use `cd` commands in scripts; use absolute paths or relative to project root.
- Add new dependencies to `dependencies` in `pyproject.toml` without checking `optional-dependencies` first.
- Hardcode secrets; use environment variables or `.env` files.
- Commit test coverage reports or generated HTML coverage files.
- Modify the `agent_data/` directory structure without updating agent configuration.

## Safety & Boundaries
**Always do:**
- Run lint/test via `pre-commit`.
- Use `agent-utilities` base classes.
- Test package manager operations with mocking to avoid accidental system modifications.
- Validate user inputs before executing system commands.

**Ask first:**
- Major refactors of `mcp_server.py` or `agent_server.py`.
- Deleting or renaming public tool functions.
- Changes to platform detection logic.
- Modifications to the graph orchestration architecture.

**Never do:**
- Commit `.env` files or secrets.
- Modify `agent-utilities` or `universal-skills` files from within this package.
- Execute destructive operations (package installs, system updates) in tests without proper mocking.
- Hardcode platform-specific paths; use cross-platform path handling.

## Testing
**Test Coverage:**
- Overall coverage: 62% (355 tests passing)
- Key modules with 95%+ coverage: `__init__.py` (96%), `agent_server.py` (96%)
- Platform-specific code tested with extensive mocking
- MCP server functionality validated through integration tests

**Test Structure:**
- `conftest.py`: Shared fixtures for platform mocking, subprocess mocking, psutil mocking
- `test_systems_manager_base.py`: Tests for base class and helper classes (127 tests)
- `test_linux_managers.py`: Tests for Linux package managers (93 tests)
- `test_windows_manager.py`: Tests for Windows manager (50 tests)
- `test_mcp_server.py`: MCP server functionality tests (52 tests)

## When Stuck
- Propose a plan first before making large changes.
- Check `agent-utilities` documentation for existing helpers.
- Review existing test patterns for platform-specific mocking.
- Check the `systems_manager.py` implementation for platform-specific patterns.

## Graph Architecture

This agent uses `pydantic-graph` orchestration for intelligent routing and optimal context management.

```mermaid
---
title: Systems Manager Graph Agent
---
stateDiagram-v2
  [*] --> RouterNode: User Query
  RouterNode --> DomainNode: Classified Domain
  RouterNode --> [*]: Low confidence / Error
  DomainNode --> [*]: Domain Result
```

- **RouterNode**: A fast, lightweight LLM (e.g., `nvidia/nemotron-3-super`) that classifies the user's query into one of the specialized domains.
- **DomainNode**: The executor node. For the selected domain, it dynamically sets environment variables to temporarily enable ONLY the tools relevant to that domain, creating a highly focused sub-agent (e.g., `gpt-4o`) to complete the request. This preserves LLM context and prevents tool hallucination.


## Testing with Timeout

To run tests with a timeout to prevent hanging, use the `pytest-timeout` plugin. You can combine it with the `-k` flag to run specific tests:

```bash
uv run pytest --timeout=60 -k "test_name_pattern"
```

## ⛔ No Scratch or Temporary Files in Repository

**NEVER write any of the following to this repository:**
- Temporary test scripts (`test_*.py`, `debug_*.py` outside of `tests/`)
- Scratch scripts or experimental one-off files
- Log files (`.log`, `.txt` command output)
- Random text files with command output or debug dumps
- Any file that is NOT production source code, tests in `tests/`, or documentation

**Why:** These files expose private filesystem paths, credentials, and internal infrastructure details when pushed to GitHub publicly.

**Where to put scratch work instead:**
- Use `~/workspace/scratch/` for temporary scripts and experiments
- Use `~/workspace/reports/` for command output and reports
- Keep test scripts in the `tests/` directory following proper pytest conventions

## ⛔ Keep the Repository Root Pristine — No Scratch / Temp / Debug Files

**The repository ROOT must contain only canonical project files** (packaging,
config, docs, lockfiles). The only hidden directories allowed at root are
`.git/`, `.github/`, and `.specify/` (plus a local, git-ignored `.venv/`).

**NEVER write any of the following — anywhere in the repo, and ESPECIALLY at the root:**
- One-off / debug / migration scripts: `fix_*.py`, `migrate_*.py`, `refactor_*.py`,
  `replace_*.py`, `update_*.py`, `debug_*.py`, or `test_*.py` **at the root**
  (real tests live in `tests/` only).
- Databases / data dumps: `*.db`, `*.db-wal`, `*.sqlite*`, `*.corrupted`.
- Logs / command output: `*.log`, scratch `*.txt`, `*.orig`, `*.rej`, `*.bak`.
- Build artifacts: `*.tsbuildinfo`, compiled binaries, coverage files.
- AI agent scratch directories: `.agent/`, `.agents/`, `.agent_data/`, `.tmp/`,
  `.hypothesis/`, or any per-tool cache committed to git.
- Any file that is NOT production source, a test in `tests/`, documentation, or
  a recognized config/lockfile.

**Why:** scratch at the root leaks private paths/credentials, bloats the tree,
and erodes a pristine codebase.

**Where scratch goes instead:** `~/workspace/scratch/` (experiments),
`~/workspace/reports/` (command output); tests go in `tests/` (pytest).
Before finishing a task, run `git status` and confirm no stray root files were added.

## Working Discipline — think, simplify, stay surgical, verify

These four habits cut the most common LLM coding mistakes. For trivial tasks, use
judgment; the bias here is correctness over speed.

- **Think before coding.** State your assumptions explicitly. If a request has more than
  one reasonable reading, surface the options instead of silently picking one. If a
  simpler approach exists, say so and push back when warranted. When something is
  genuinely unclear, stop and name what's confusing — ask, don't guess.
- **Simplicity first.** Write the minimum code that solves the stated problem — no
  speculative features, no abstraction for single-use code, no configurability that
  wasn't requested, no error handling for impossible states. If you wrote 200 lines and
  it could be 50, rewrite it. (Name code from its purpose, never `wave0`/`phase2`/`v2`.)
- **Stay surgical.** Every changed line should trace directly to the task. Don't refactor,
  reformat, or "improve" working code adjacent to your change; match the existing style
  even where you'd do it differently. Remove only the imports/symbols your own change
  orphaned; if you spot unrelated dead code, mention it rather than deleting it inline.
  *Exception — the Quality Bar below:* lint/format/type errors the pre-commit gate flags
  get fixed regardless of who introduced them. In short: **surgical on behavior, clean on
  lint.**
- **Verify against a goal.** Turn the task into a checkable outcome before you start:
  "fix the bug" → "write a failing test that reproduces it, then make it pass"; "add
  validation" → "tests for the invalid inputs pass". For multi-step work, state the short
  plan and the check for each step, then loop until the checks pass.

## Quality Bar — Leave the Codebase Clean (REQUIRED)

After completing any code change, run the project's pre-commit suite and drive it
**fully green** before committing:

```bash
pre-commit run --all-files
```

Resolve **every** issue it reports — failures, lint errors, type errors, and
warnings — **including problems that pre-date your change and were not caused by
your edits**. The standing goal is a clean, working codebase with **no errors and
no warnings**. Do not silence checks (`# noqa`, `# type: ignore`, `SKIP=`,
`--no-verify`) to force green unless the exception is already documented in this
file as a known, unavoidable limitation. Only commit once `pre-commit run
--all-files` passes cleanly; if a check legitimately cannot pass, stop and explain
why rather than bypassing it.

## Working with Git Worktrees (multi-session)

Multiple agents/sessions work the `agent-packages/*` repos concurrently. **Do not
edit the canonical checkout** (`${WORKSPACE_ROOT}/agent-packages/<repo>`) — a
background `repository-manager` sync can reset its working tree and discard
uncommitted edits. Take your own git worktree on your own branch instead:

```bash
# preferred — repository-manager MCP:
rm_worktree add <repo> <your-branch>      # -> ${WORKTREE_ROOT}/<repo>/<your-branch>

# raw-git fallback:
git -C agent-packages/<repo> checkout main
git -C agent-packages/<repo> worktree add "${WORKTREE_ROOT}/<repo>/<branch>" -b <branch>
```

Work in the worktree and **commit often** (commits survive a working-tree reset).
Each session must use a **distinct branch** — git allows a branch in only one
worktree, which is what keeps concurrent sessions from colliding. Worktrees live
under `${WORKTREE_ROOT}` (outside the workspace scan, so the sync leaves them
alone).

**Finishing work in a worktree** — run this sequence before calling it done:
1. **Pre-commit green** — `pre-commit run --all-files`; resolve every issue per the
   Quality Bar above (including pre-existing), no `--no-verify`.
2. **Commit** in the worktree.
3. **Merge to main locally** — `rm_worktree merge <repo> <branch> --into main`
   (or `git merge --no-ff`). Push only when the user asks.
4. **Clean up** — remove the worktree and delete the merged branch:
   `rm_worktree remove <repo> <branch> --delete-branch`; `rm_worktree prune` clears
   stale entries. (Raw-git: `git worktree remove <path> && git branch -d <branch>`.)

<!-- BEGIN concept-coordination (generated) -->
## Concept-ID Coordination (multi-session)

Working in parallel with other sessions/worktrees? **Reserve a concept id before you write its `CONCEPT:` marker** so two sessions never collide:

```bash
agent-utilities --json concept reserve --ns EG-KG.compute.backend   # or a package prefix, e.g. KEY
```

Full protocol (ledger, merge=union, reconcile, MCP/REST): <https://knuckles-team.github.io/agent-utilities/concept_coordination/>
<!-- END concept-coordination (generated) -->

## Version & lockfile drift edict (keep the version mirrors AND the lock in sync)

The two most common release-breakers in this fleet are **version drift** (the version in
`pyproject.toml`/`.bumpversion.cfg` advancing while `README.md`, `docker/Dockerfile`, and the
module `__version__`s lag) and a **stale `uv.lock`** (shipping known-vulnerable transitive deps).
A version mismatch makes the next `bump-my-version` throw `VersionNotFoundException`; a stale lock
is what Dependabot flags. Rules:

1. **Never hand-edit a version string.** Change the version ONLY via
   `bump-my-version bump {patch|minor|major}` (a.k.a. `bump2version`), which rewrites every file
   registered in `.bumpversion.cfg` in one atomic, tagged commit. If you edited the version in
   `pyproject.toml` by hand, you created drift — revert and use the bumper.
2. **Every version-bearing file must be registered in `.bumpversion.cfg`** — at minimum
   `pyproject.toml` AND `README.md`, plus `docker/Dockerfile` and any module `__version__`. Never
   add a file that embeds the version without a `[bumpversion:file:...]` entry for it.
3. **Re-lock on every dependency change.** After editing `pyproject.toml` deps/extras, run
   `uv lock` and commit `uv.lock` in the SAME change. The `uv-lock` pre-commit hook runs with
   `--locked` and fails on drift — never bypass it. The committed `uv.lock` is the
   Dependabot/security surface.
4. **Patch CVEs with a version floor at the source, then re-lock.** `uv` resolves one version
   graph-wide, so a lower-bound in the extra that pulls a dependency raises it for the whole lock.
