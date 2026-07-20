# Configuration, trust, and privacy

This page is the operator contract for `systems-manager`. Package-specific endpoint,
authentication, tool-toggle, and model settings remain documented in the
repository README and the installed command's `--help` output. Runtime values
must be injected by the launcher; they do not belong in source, packaged skill
content, traces, or generated reports.

## Capability configuration

The current capability source is defined by three versioned artifact groups:

- the action-routed MCP tools described in the README and `docs/usage.md`;
- the single canonical `systems-manager-operations` skill and its focused catalog;
- the human-authored ontology, source preset, and source mapping shipped by the
  provider.

Release automation derives and commits the exact local schema fingerprint, signed
manifest, SHACL shapes, neutral mapping and fixture, migration ledger, and offline
source attestation from those sources. These artifacts contain no environment-bound
values and do not claim external-live certification. Use the compact intent-oriented
surface for delegated agents and load current typed actions on demand. Raw-command
surfaces are not part of the API.

## Runtime values and secrets

- Supply service endpoints, tenant identifiers, credentials, and model keys through
  AgentConfig references resolved by the launcher.
- Use non-personal agent aliases and opaque tenant/correlation identifiers.
- Keep developer directories, workstation names, and deployment hostnames out
  of checked-in configuration.
- Bind network transports to an explicitly chosen interface and require the
  deployment's MCP authentication policy before accepting remote traffic.
- Enable optional agent, embedding, evolution, or observability features only
  when their dependencies and backends are configured and healthy.

The checked-in examples use `localhost` for loopback-only development and
`example.invalid` for replaceable network endpoints. Neither value is a
production default.

## Host capability policy

All host mutations are denied unless the deployment sets
`SYSTEMS_MANAGER_ALLOW_HOST_MUTATIONS=true`. Generic file edits have a second,
independent `SYSTEMS_MANAGER_ALLOW_FILESYSTEM_MUTATIONS=true` gate. Sensitive
inventory and active network probes have independent
`SYSTEMS_MANAGER_ALLOW_SENSITIVE_READS` and
`SYSTEMS_MANAGER_ALLOW_NETWORK_PROBES` gates. A mutating MCP operation also
requires request-channel elicitation. Elicitation confirms intent in that MCP
session; it is not a substitute for transport authentication, operating-system
authorization, or an independent human approval broker.

Raw command execution, shell programs, model-authored cron entries, persistent
shell aliases, and unsigned remote font archives are not part of the API.
Managed child processes
use fixed argv vectors, an executable/interpreter allowlist, a minimal
environment, bounded output, and a bounded timeout. Configure the default timeout with
`SYSTEMS_MANAGER_COMMAND_TIMEOUT_SECONDS` (1 through 3,600 seconds). Package
operations default to 1,800 seconds; other operations default to 120 seconds.

Repository addition is disabled unless the exact credential-free HTTPS URL is
present in the launcher-controlled JSON array
`SYSTEMS_MANAGER_REPOSITORY_ALLOWLIST_JSON`. Local package installation is
disabled unless `SYSTEMS_MANAGER_LOCAL_PACKAGE_SHA256_MAP` is a JSON object
mapping the package's managed-root-relative path to its release SHA-256 digest.
These policies must come from the deployment boundary, not model arguments or
a sidecar file writable by the agent.

Filesystem tools are confined beneath an explicit
`SYSTEMS_MANAGER_FILESYSTEM_ROOT`; there is no current-directory or workspace
fallback. A volume root is never accepted. Temporary
cleanup is similarly limited to `SYSTEMS_MANAGER_TEMP_ROOT`, which must resolve
beneath the managed root. Runtime logs contain metadata only and go to stderr.

Windows elevation is not synthesized with PowerShell. Run the service under a
pre-authorized, least-privilege service account or use an external elevation
broker. Secret-bearing SSH key generation likewise requires an external secret
broker; never pass a plaintext passphrase as a tool argument.

## TLS trust

Certificate verification is required. Define private trust in the shared AgentConfig
TLS catalog and select it with `TLS_PROFILE` / `TLS_PROFILE_REF` and
`TLS_PROFILES_REF`. A profile may reference a mounted PEM bundle containing the
required intermediate and root certificates. Service-specific selectors such as
`OIDC_TLS_PROFILE_REF`, `MODEL_TLS_PROFILE_REF`, and `LANGFUSE_TLS_PROFILE_REF` use
the same resolver. `UV_NATIVE_TLS=true` is an installer setting for `uv` package
resolution; it is not application TLS policy.

Do not disable verification to work around an incomplete server chain. Keep trust
references external and stable for the runtime; never embed a workstation path,
certificate material, or a hardcoded verification argument in provider code.

## Privacy and data governance

The default observability posture is metadata-only. Do not persist prompts,
message bodies, tool inputs/results, document content, raw traces, credentials,
local paths, hostnames, or personal identity unless an approved data contract
explicitly requires it. Keep Langfuse or OTLP content capture disabled unless a
reviewed retention and access policy authorizes it.

When host ingestion is enabled, the native governed boundary supplies tenant, ACL,
classification, retention, provenance, and ChangeEnvelope authority. Reject records
that cannot satisfy that contract; never silently widen a tenant scope. The provider's
allowlist rejects arbitrary node fields, relationship types, and endpoints. Logs and
reports should contain counts, status, and opaque references only.

## Deployment verification

1. Validate the capability bundle and skill metadata against the installed tool
   schemas.
2. Confirm required secrets are present without printing their values.
3. Verify the complete TLS chain with certificate verification enabled.
4. Exercise health/readiness and one least-privilege read operation.
5. Confirm traces arrive under the expected opaque tenant/run identifiers and
   contain no captured content.
6. Record only sanitized pass/fail evidence and version identifiers.
