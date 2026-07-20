# Sudo and elevation security

`systems-manager` does not synthesize interactive elevation, store passwords, or
grant itself blanket sudo. The preferred boundary is a dedicated service account
with only the operating-system permissions required for its deployment.

## Optional helper

`systems-manager-helper` is a small local elevation broker for reviewed Linux
deployments. It accepts a fixed grammar:

- `service {start|stop|restart|status|enable|disable} NAME`
- `package {install|remove} NAME`
- `package {update|upgrade|autoremove|autoclean}`

Service and package names must be present in deployment-controlled JSON
allowlists:

- `SYSTEMS_MANAGER_HELPER_ALLOWED_SERVICES_JSON`
- `SYSTEMS_MANAGER_HELPER_ALLOWED_PACKAGES_JSON`

The helper uses fixed absolute executables, `shell=False`, a minimal environment,
no stdin, bounded time, bounded output, and process-group termination. Results
contain status metadata rather than command output.

## Sudoers boundary

Provision sudoers outside the agent. Resolve the installed helper path, verify that
it and every ancestor are root-owned and not group/world writable, and authorize
only that exact executable. Do not authorize:

- shells or interpreters;
- wildcards;
- `sudo`, `systemctl`, or package managers directly;
- writable scripts or virtual-environment entry points;
- arbitrary environment preservation;
- password input from an MCP request.

The helper still enforces its own allowlists after sudoers authorizes the
executable. Both layers are required.

## Windows boundary

Windows elevation is not created with `Start-Process`, PowerShell command
construction, or an interactive UAC workaround. Run the service under a
pre-authorized, least-privilege identity or integrate a separately reviewed
elevation broker.

## Operational gates

Elevation never replaces application policy. Host mutations require the
administrator gate and per-request approval. Managed-file writes require the
additional filesystem gate. Kubernetes nodes also apply the lifecycle guard for
updates and reboot.

## Verification

1. Confirm the helper refuses to run without the expected elevated identity.
2. Confirm empty/malformed allowlists deny all named service/package operations.
3. Confirm an allowlisted no-op/status operation succeeds without returning raw
   stdout or stderr.
4. Confirm a non-allowlisted name fails and no child process starts.
5. Confirm timeout terminates the child process group.
6. Audit sudoers ownership, exact path, environment handling, and arguments.
7. Record only sanitized pass/fail evidence.

Never place a password, private key, host identity, local path, or command output
in documentation, configuration committed to source, or observability traces.
