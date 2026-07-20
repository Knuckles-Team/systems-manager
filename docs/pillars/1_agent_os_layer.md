# Agent OS layer

`systems-manager` is the local execution provider for a reviewed set of host
operations. Agent Utilities and GraphOS provide configuration, policy,
delegation, and lifecycle coordination around that local boundary.

## Platform provider

`get_os_provider()` selects Linux or Windows explicitly. Unsupported platforms
fail instead of inheriting Linux behavior. Provider methods expose bounded
inventory, service operations, logs, and tracing through typed MCP tools.

## Privacy boundary

Process, interface, host, document, and watcher identities are represented by
keyed opaque references. Results exclude usernames, hostnames, local paths,
command lines, raw watcher queries, and pending content. Raw diagnostic output
is not a durable graph or trace payload.

## Package and service operations

Package identifiers, repository URLs, local artifacts, service names, firewall
rules, timeouts, and executable arguments are validated before use. Repository
addition requires a deployment allowlist, local packages require a matching
SHA-256 policy, and interpreter-capable commands accept only fixed internal
programs.

Host mutations remain disabled until an administrator enables the relevant
gate. A request still needs destructive-action approval. The package never
constructs an arbitrary shell command or an interactive elevation flow.

## Fleet composition

The package contains no embedded message broker or broadcast control plane.
GraphOS may delegate to independently authenticated per-host instances, and a
separately reviewed tunnel provider may supply remote transport. Fleet size,
concurrency, retries, routing, and aggregation are deployment responsibilities.

See [Host lifecycle coverage](../host-lifecycle-coverage.md) for the implemented
matrix and explicit gaps.
