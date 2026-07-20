# Agent Utilities integration

`systems-manager` is a typed, local host-operation provider. Agent Utilities
supplies the MCP server, configuration, transport security, approval prompts,
delegation, and observability boundaries. Neither component turns model output
into a shell command.

## Current integration

- The package uses the current Agent Utilities server factory and intent-first
  tool surface.
- Sensitive reads, active network probes, host mutations, and generic file
  mutations have separate default-deny administrator gates.
- Mutations are serialized and require request-channel approval.
- Agent OS identity, specialist registry, scheduler, and watchdog tools call
  only current public authorities. Results are projected to bounded status and
  opaque references.
- Host health can be materialized through the native knowledge-graph boundary
  after allowlist validation and keyed pseudonymization.
- Remote MCP and agent transports require authentication and verified TLS.

## Delegated operation

GraphOS can delegate a typed operation to an authenticated systems-manager
instance on the target host. Target inventory, credentials, endpoints, TLS
profiles, and policy are deployment configuration; none is packaged here.

A safe delegated workflow is:

1. resolve a target capability by opaque deployment alias;
2. enable only the read or mutation gate required for the request;
3. perform bounded discovery without persisting raw paths, hostnames, command
   lines, logs, or content;
4. obtain approval for a typed mutation;
5. execute at the target host boundary; and
6. verify with a separate read and retain sanitized status evidence.

## Explicit non-capabilities

This package is not an EDR, SIEM, remote shell, message-broker fleet control
plane, autonomous remediation system, or Windows Update orchestrator. It does
not promise fan-out to a fixed fleet size. Those concerns belong to reviewed
providers and the deployment orchestration layer, with their own resource and
security policies.
