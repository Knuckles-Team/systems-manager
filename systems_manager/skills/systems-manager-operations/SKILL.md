---
name: systems-manager-operations
skill_type: skill
description: >-
  Operate hosts and Agent OS services through the governed systems-manager MCP provider and
  Arbora delegation. Use for OS and package lifecycle, services, processes, network and disk
  inspection, storage or BMC health, firewall and managed-file work, agent identity,
  specialist registry, scheduler, watchdog, host telemetry ingestion, troubleshooting, and
  evidence-backed verification.
---

# Systems Manager Operations

Use the provider's governed MCP tools through Arbora delegation.

## Workflow

1. Establish the verified GraphSession and tenant before discovery or retrieval.
2. Discover the current intent tool surface and its exact action schema; never assume a stale
   tool name or parameter.
3. Prefer read-only inspection first. For changes, present impact and use the provider's
   dry-run or preview mode when available.
4. Execute mutations as fenced WorkItems so retries remain idempotent and auditable.
5. Ingest host state only through `systems_ingest_host`, which uses the governed
   ChangeEnvelope boundary and a deployment-provided pseudonymization key.
6. Verify the durable result and its trace/evidence before reporting completion.

## Steps

1. Establish the verified GraphSession and tenant, and verify both are present before the first `find` call.
2. Discover the current tool surface with the intent `find` operation, and verify the exact action schema before building arguments.
3. Run read-only inspection first, such as `get_management_capabilities`, and verify the result describes the intended host.
4. For a change, present the impact, use the provider dry-run or the `act` preview when offered, and verify the preview matches the request.
5. Execute the mutation as a fenced WorkItem with `act`, and verify the returned trace or evidence reference shows the durable result.
6. Ingest host state only through `systems_ingest_host`, and verify the ChangeEnvelope result is accepted.

## Failure recovery

| Failure | Cause | Recovery |
|---|---|---|
| A tool name or parameter is rejected | The cached tool surface is stale | Run `find` for the intent again and use the returned schema |
| A mutation is denied by policy | The host-mutation or approval gate is closed | Report the denial and stop, because a policy denial is final |
| BMC calls fail | `SYSTEMS_MANAGER_BMC_CREDENTIALS` is not resolved at runtime | Ask the operator to provide the BMC credential projection in the deployment configuration |

## Safety contract

- Never persist credentials, endpoints, raw personal identifiers, hostnames, network
  addresses, or local paths.
- Resolve secret references and TLS profiles through AgentConfig; never accept credentials in
  tool arguments or hardcode trust paths, verification flags, or bypasses.
- Treat unknown ACL, tenant, schema, or tool-contract state as a hard failure.
- Require explicit approval for destructive, externally visible, or irreversible actions.
- Keep runtime traces policy-scoped and privacy-sanitized.
- Use typed operations only. Raw commands, arbitrary shell programs, persistent aliases,
  and model-authored scheduled commands are not part of the API and must not be emulated
  through another tool.
- BMC access is health-only. Resolve its `{host,user,password}` projection at runtime through
  `SYSTEMS_MANAGER_BMC_CREDENTIALS`; never log or return the projection.
- NIC bonding and vendor-specific BMC power, console, user, or LAN configuration are not
  current typed capabilities. Report them as unsupported instead of synthesizing shell steps.
- Treat host-mutation, sensitive-read, and network-probe policy denials as final. Never
  ask the model to change deployment environment variables or bypass an approval gate.

## Specialized workflows

Read [the workflow catalog](references/catalog.md) only when the request needs a
provider-specific procedure or action map.
