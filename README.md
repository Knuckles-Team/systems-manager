# systems-manager

Version: 2.0.0

`systems-manager` is the typed host-operations provider for Agent Utilities and
GraphOS. It exposes cross-platform package, service, process, network, disk,
managed-file, firewall, physical-storage, Agent OS, and privacy-safe host-ingestion
capabilities without exposing a raw command tool.

The current package requires Python 3.11–3.14 and
`agent-utilities>=2.0.0,<3.0.0`.

## Install and run

Install only the interface you need:

```bash
pip install "systems-manager[mcp]"
systems-manager-mcp --transport stdio
```

The optional extras are:

| Extra | Capability |
| --- | --- |
| `mcp` | FastMCP provider runtime |
| `agent` | Agent server and Logfire integration |
| `all` | MCP plus agent runtime |
| `test` | Test dependencies |

For an ephemeral MCP launch:

```bash
uvx --from "systems-manager[mcp]" systems-manager-mcp --transport stdio
```

The checked-in `mcp_config.json` is a reference-only client catalog. It contains
`env://` references and safe deny defaults, never deployment endpoints, credentials,
certificate paths, filesystem paths, hostnames, or identities. Project-specific values
belong in AgentConfig or the process launcher.

## Security contract

- Network MCP listeners require configured authentication. Non-loopback listeners also
  require direct TLS or a trusted TLS-terminating proxy, exact allowed hosts, and the
  current Agent Utilities transport checks.
- Host mutations are denied unless `SYSTEMS_MANAGER_ALLOW_HOST_MUTATIONS=true` and the
  individual request receives destructive-operation approval.
- Managed-file writes additionally require
  `SYSTEMS_MANAGER_ALLOW_FILESYSTEM_MUTATIONS=true`.
- Sensitive reads and active probes have independent default-deny gates.
- Managed paths are confined beneath an explicit
  `SYSTEMS_MANAGER_FILESYSTEM_ROOT`; there is no working-directory fallback.
- Raw shell, arbitrary commands, plaintext credentials, model-authored cron creation,
  and compatibility command aliases are not capabilities.
- Logs and observability are metadata-only. Keep `LANGFUSE_CAPTURE_CONTENT=false`.

## AgentConfig, secrets, and TLS

Use `TLS_PROFILE` / `TLS_PROFILE_REF` with `TLS_PROFILES_REF` for shared verified
outbound trust. Service-specific profiles such as `OIDC_TLS_PROFILE_REF`,
`MODEL_TLS_PROFILE_REF`, and `LANGFUSE_TLS_PROFILE_REF` may select entries from the
same runtime catalog. Do not hardcode CA paths or verification flags in application
code, and do not disable verification for incomplete certificate chains.

Out-of-band BMC health reads consume one runtime secret projection from
`SYSTEMS_MANAGER_BMC_CREDENTIALS`. AgentConfig resolves the checked `env://` or secret
reference before launch; the provider accepts exactly a JSON object with `host`, `user`,
and `password`. No secret-store vendor, secret path, token, or credential value is
embedded in this package.

The MCP listener's own certificate or trusted-proxy boundary uses the current Agent
Utilities `MCP_TLS_*` configuration. The optional agent listener uses `SERVER_TLS_*`
and requires JWT configuration for non-loopback serving.

## MCP tools

The default `MCP_TOOL_MODE=intent` exposes the small intent-verb surface. Backing
action-routed tools stay available for governed discovery and on-demand loading. Tool
and tag filters can further reduce the visible surface.

_Auto-generated from the live MCP server; do not edit between the markers._

<!-- MCP-TOOLS-TABLE:START -->

#### Condensed action-routed tools (`MCP_TOOL_MODE=condensed`)

| MCP Tool | Toggle Env Var | Description |
|----------|----------------|-------------|
| `capture_system_snapshot` | `OS_PROVIDERTOOL` | Takes a point-in-time snapshot of the system state (CPU, RAM, Processes). |
| `get_management_capabilities` | — |  |
| `get_network_connections` | `OS_PROVIDERTOOL` | Maps active TCP/UDP endpoints directly to owning processes. |
| `get_process_details` | `OS_PROVIDERTOOL` | Retrieves deep cross-platform process details (threads, modules, memory). |
| `health_check` | — |  |
| `list_kernel_modules` | `OS_PROVIDERTOOL` | List loaded drivers/modules (lsmod or driverquery). |
| `list_services` | `OS_PROVIDERTOOL` | Cross-platform service enumeration (systemctl or Get-Service). |
| `manage_service` | `OS_PROVIDERTOOL` | Start/Stop/Restart/Enable/Disable services cross-platform. |
| `query_system_logs` | `OS_PROVIDERTOOL` | Cross-platform log querying (journalctl or Get-WinEvent). |
| `sm_advanced_operations` | — | Operations for SSH and specialized managers |
| `sm_agent_identity_operations` | `IDENTITYTOOL` | Issues or verifies privacy-preserving agent identities. |
| `sm_agent_scheduler_operations` | `AGENT_HEALTHTOOL` | Manages the cognitive scheduler: get stats, list processes, preempt, or reset quota. |
| `sm_agent_specialist_operations` | `SPECIALIST_REGISTRYTOOL` | Manages specialist packages: install, uninstall, list, or search. |
| `sm_agent_watchdog_operations` | `WATCHDOGTOOL` | Manages file watchdog triggers: check file change, list active watchers, or drain triggers. |
| `sm_cron_operations` | — | Operations for cron jobs |
| `sm_disk_operations` | — | Operations for managing system disks |
| `sm_file_operations` | — | Operations for file and log management |
| `sm_firewall_operations` | — | Operations for firewall management |
| `sm_network_operations` | — | Operations for network analysis |
| `sm_process_operations` | — | Operations for managing system processes |
| `sm_service_operations` | — | Operations for managing system services |
| `sm_storage_health` | `STORAGE_HEALTHTOOL` | Physical disk + BMC drive-fault health: SMART (incl. megaraid passthrough), |
| `sm_system_operations` | — | System operations for managing packages, system health, and updates |
| `sm_user_operations` | — | Operations for user and group management |
| `start_system_trace` | `OS_PROVIDERTOOL` | Start a kernel-level event trace (ETW on Windows, or strace on Linux). |
| `stop_system_trace` | `OS_PROVIDERTOOL` | Stop a kernel-level event trace. |
| `systems_ingest_host` | — | Ingest a keyed host telemetry projection through the governed ChangeEnvelope boundary as typed HardwareNode, NetworkInterface, and DiskVolume nodes. |

_27 action-routed tool(s) · 0 verbose 1:1 tool(s). Each is enabled unless its `<DOMAIN>TOOL` toggle is set false; `MCP_TOOL_MODE` selects the surface (**`intent` default** — the six verb-tools, granular set loaded on demand · `condensed` action-routed · `verbose` 1:1 · `both`). Auto-generated — do not edit._
<!-- MCP-TOOLS-TABLE:END -->

Typical backing domains include OS/package lifecycle, services, processes, networks,
disks, managed files, cron removal, structured firewall rules, storage/BMC diagnostics,
Agent OS administration, and governed host telemetry ingestion. Discover an action
schema before calling it; unavailable operations must not be emulated with another
tool.

## Knowledge-graph ingestion

`systems_ingest_host` reads local typed telemetry and submits an allowlisted projection
through the Agent Utilities native governed ingestion boundary. It emits only:

- `HardwareNode`, `NetworkInterface`, and `DiskVolume` nodes;
- `hasInterface` and `hasVolume` relationships;
- HMAC-SHA-256 opaque identifiers derived with the deployment-owned
  `SYSTEMS_MANAGER_PSEUDONYMIZATION_KEY`.

Hostnames, network addresses, hardware addresses, usernames, local paths, credentials,
and arbitrary extra fields are rejected or excluded. Missing graph authority, invalid
content, and unavailable ingestion fail explicitly; they are not silent no-ops.

## GraphOS delegation

Host operations execute inside the service's local operating-system boundary. For
fleet work, GraphOS delegates to an authenticated systems-manager service on the target
boundary. Inventory, endpoints, credentials, TLS profiles, and target aliases remain
external deployment configuration. Persist only opaque, non-personal references.

The bundled `systems-manager-operations` skill covers every current provider workflow.
Older BMC command and NIC-bond script skills were consolidated because those raw-script
surfaces are not part of the typed current contract.

## Agent server

Install the agent extra and launch:

```bash
pip install "systems-manager[agent]"
systems-manager-agent --help
```

Workspace, MCP catalog, and custom-skill paths are accepted only when explicitly
configured and present. There is no packaged-config or current-directory fallback.
A non-loopback listener requires an explicit allow gate, direct or trusted-proxy TLS,
JWT issuer/JWKS/audience configuration, and debug mode disabled.

## Environment variables

The generated table is sourced from the value-free `.env.example` plus the inherited
Agent Utilities contract.

<!-- ENV-VARS-TABLE:START -->

#### Package environment variables

| Variable | Example | Description |
|----------|---------|-------------|
| `SYSTEMS_MANAGER_FILESYSTEM_ROOT` | — | Required managed filesystem boundary |
| `SYSTEMS_MANAGER_TEMP_ROOT` | — | Optional cleanup root beneath the managed boundary |
| `SYSTEMS_MANAGER_PSEUDONYMIZATION_KEY` | secret-injected | Deployment-owned secret, at least 32 bytes |
| `SYSTEMS_MANAGER_BMC_CREDENTIALS` | — | Secret-projected JSON with host/user/password |
| `TLS_PROFILE` | — | Shared mandatory-verification transport profile |
| `TLS_PROFILES_REF` | — | Runtime reference to the transport profile catalog |
| `LANGFUSE_TLS_PROFILE_REF` | — | Runtime reference to verified Langfuse trust |
| `MCP_TOOL_MODE` | `intent` | Current intent-first tool surface |
| `SYSTEMS_MANAGER_ALLOW_HOST_MUTATIONS` | `false` | Default-deny host mutations |
| `SYSTEMS_MANAGER_ALLOW_FILESYSTEM_MUTATIONS` | `false` | Default-deny file mutations |
| `SYSTEMS_MANAGER_ALLOW_SENSITIVE_READS` | `false` | Default-deny sensitive inventory |
| `SYSTEMS_MANAGER_ALLOW_NETWORK_PROBES` | `false` | Default-deny active probes |
| `SYSTEMS_MANAGER_MAX_BLOCKING_OPERATIONS` | `2` | Bounded host-operation concurrency |
| `SYSTEMS_MANAGER_HEALTH_INGEST` | `true` | Enable governed health trend ingestion |
| `SYSTEMS_MANAGER_HEALTH_AGGREGATE_S` | `3600` | Health trend aggregation window |
| `SYSTEMS_MANAGER_NODE_REF` | — | Runtime node alias; only a keyed digest persists |
| `SYSTEMS_MANAGER_NODE_REFS` | — | Runtime aliases for governed derivation |
| `SYSTEMS_MANAGER_NOTIFY_URL` | — | Optional credential-free HTTPS notification target |
| `SYSTEMS_MANAGER_REPOSITORY_ALLOWLIST_JSON` | `[]` | Approved credential-free repositories |
| `SYSTEMS_MANAGER_LOCAL_PACKAGE_SHA256_MAP` | `{}` | Approved package paths and digests |
| `SYSTEMS_MANAGER_COMMAND_TIMEOUT_SECONDS` | `120` | Default command timeout |
| `SYSTEMS_MANAGER_ENV_METADATA_ALLOWLIST` | — | Non-sensitive environment names readable as metadata |
| `SYSTEMS_MANAGER_UV_VERSION` | — | Exact approved uv release |
| `SYSTEMS_MANAGER_NVM_COMMIT` | — | Exact approved NVM commit |
| `SYSTEMS_MANAGER_NVM_DIR` | — | NVM directory beneath the managed filesystem root |
| `ALLOW_UPDATE_ON_K8S` | `false` | Keep Kubernetes lifecycle guard enabled |
| `MISCTOOL` | `true` | Register base health/readiness tools |
| `OS_PROVIDERTOOL` | `true` | Register operating-system provider tools |
| `STORAGE_HEALTHTOOL` | `true` | Register storage health tools |
| `AGENT_HEALTHTOOL` | `true` | Register agent health tools |
| `IDENTITYTOOL` | `true` | Register identity tools |
| `SPECIALIST_REGISTRYTOOL` | `true` | Register specialist registry tools |
| `WATCHDOGTOOL` | `true` | Register filesystem watchdog tools |
| `MAX_CONCURRENT_AGENTS` | `5` | Agent scheduler limit |
| `AGENT_POLICIES_PATH` | — | Runtime policy location |
| `PERMISSIONS_SIGNING_KEY` | secret-injected | Runtime secret projection for identity signing |
| `SPECIALIST_REGISTRY_PATH` | — | Runtime specialist registry location |
| `MCP_CONFIG_PATH` | — | Runtime MCP catalog location |
| `PROJECT_ROOT` | — | Runtime automation boundary |
| `WORKSPACE_PATH` | — | Explicit agent workspace directory |
| `TRANSPORT` | `stdio` | Local MCP transport |
| `HOST` | `127.0.0.1` | Loopback bind for HTTP transports |
| `PORT` | `8000` | Bind port for HTTP transports |
| `SYSTEMS_MANAGER_ALLOW_REMOTE_AGENT_SERVER` | `false` | Explicit non-loopback agent-listener gate |
| `ENABLE_OTEL` | `false` | Enable only with an approved collector |
| `LANGFUSE_CAPTURE_CONTENT` | `false` | Never capture host/tool content |
| `SERVER_TRUSTED_PROXY_CIDRS` | — | Trusted proxy networks for a remotely served agent |

#### Inherited agent-utilities variables (apply to every connector)

| Variable | Example | Description |
|----------|---------|-------------|
| `MCP_ENABLED_TOOLS` | — | Comma-separated tool allow-list |
| `MCP_DISABLED_TOOLS` | — | Comma-separated tool deny-list |
| `MCP_ENABLED_TAGS` | — | Comma-separated tag allow-list |
| `MCP_DISABLED_TAGS` | — | Comma-separated tag deny-list |
| `EUNOMIA_TYPE` | `none` | Authorization mode: `none` \| `embedded` \| `remote` |
| `EUNOMIA_POLICY_FILE` | `mcp_policies.json` | Embedded Eunomia policy file |
| `EUNOMIA_REMOTE_URL` | — | Remote Eunomia authorization server URL |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | — | OTLP collector endpoint |
| `MCP_CLIENT_AUTH` | — | Outbound MCP child auth: `oidc-client-credentials` \| `basic` \| `none` |
| `OIDC_CLIENT_ID` | — | OIDC client id (service-account auth) |
| `OIDC_CLIENT_SECRET_REF` | `secret://identity/oidc-client-secret` | Runtime secret reference for the OIDC service account |
| `MCP_BASIC_AUTH_USERNAME` | — | HTTP Basic username (`MCP_CLIENT_AUTH=basic`) |
| `MCP_BASIC_AUTH_PASSWORD_REF` | `secret://identity/mcp-basic-password` | Runtime secret reference for HTTP Basic auth (`MCP_CLIENT_AUTH=basic`) |
| `DEBUG` | `False` | Verbose logging |
| `PYTHONUNBUFFERED` | `1` | Unbuffered stdout (recommended in containers) |
| `MCP_URL` | `http://localhost:8000/mcp` | URL of the MCP server the agent connects to |
| `PROVIDER` | `openai` | LLM provider for the agent |
| `MODEL_ID` | `gpt-4o` | Model id for the agent |
| `ENABLE_WEB_UI` | `True` | Serve the AG-UI web interface |

_47 package + 19 inherited variable(s). Auto-generated from `.env.example` + the shared agent-utilities set — do not edit._
<!-- ENV-VARS-TABLE:END -->

## Development and release gates

```bash
pytest -q
ruff check systems_manager tests
black --check systems_manager tests
mkdocs build --strict
pre-commit run --all-files
```

Run host operations only through mocks during tests. Do not run native builds or live
host mutations as a validation shortcut. The source dependency floor is intentionally
`agent-utilities>=2.0.0`; regenerate and commit a neutral lock only after that release
is available from the configured package index. Never commit an editable local source
or a stale dependency resolution.

See [the documentation](docs/index.md) for installation, deployment, configuration,
usage, multi-host delegation, and security details.


<!-- BEGIN agent-utilities-deployment (generated; do not edit between markers) -->

## Deploy with `agent-utilities-deployment`

Provision this package with the consolidated **`agent-utilities-deployment`**
workflow. It selects an installed-package, editable-source, or immutable-container
path; records only runtime secret and TLS-profile references in `AgentConfig`; and
runs doctor, registration, policy, observability, and rollback gates. Ask your agent
to **"deploy `systems-manager` with agent-utilities-deployment"**.

| Install mode | Command |
|------|---------|
| Installed package | `uv tool install "systems-manager[mcp]"`, then run `systems-manager-mcp` |
| Editable source | `uv pip install -e ".[agent]"`, then run `systems-manager-mcp` |
| Immutable container | deploy `registry.example.invalid/systems-manager@sha256:<digest>` through the operator-selected orchestrator |

The repository embeds no deployment profile, credential value, certificate path, or
environment-specific endpoint. Supply those at runtime through `AgentConfig` and the
configured secret provider.

<!-- END agent-utilities-deployment -->
