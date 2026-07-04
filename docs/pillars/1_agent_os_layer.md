# Pillar 1: Agent OS Layer (Systems Manager)

The `systems-manager` acts as the physical execution arm for the `agent-utilities` OS Kernel. While `agent-utilities` makes the decisions, `systems-manager` executes the raw system calls. To scale from local environments to 10,000+ host fleets, we compartmentalize its capabilities into four core conceptual domains.

## SM-OS.deployment.abstracted-os-provider: Abstracted OS Provider

**What it is:**
A unified interface (`OSProvider`) that dynamically loads the correct backend (`LinuxProvider` or `WindowsProvider`) based on the host environment.

**Why it matters:**
When an AI agent says "Restart the web service," it shouldn't have to know if it's talking to `systemctl` on Ubuntu or `Get-Service` on Windows Server. The Abstracted OS Provider hides the system-level syntax.

**How it works:**
The MCP tools invoke standard commands like `provider.manage_service(name, action)`. The factory method `get_os_provider()` detects the platform and automatically formats the request (e.g., executing native API calls using `psutil`, or dropping down into `subprocess` to run `journalctl` / `wevtutil`).

---

## SYS-1.1: Distributed Fleet Control Plane

**What it is:**
An asynchronous publish-subscribe architecture that decouples the MCP Server from local execution, enabling a single Agent to orchestrate 10,000+ machines simultaneously.

**Why it matters:**
Connecting an agent directly to 10,000 different HTTP MCP endpoints is impossible and wastes context window tokens. Scaling requires a single logical connection that fan-outs across the infrastructure.

**How it works:**
1. **The Daemon**: A lightweight instance of `systems-manager` runs on each edge node as a background daemon connected to a Message Broker (NATS/Kafka).
2. **The Control Plane**: A central MCP Server receives the AI agent's tool call (e.g., "query system logs for error code 500").
3. **Execution & Aggregation**: The Control Plane publishes the command. All daemons execute `SM-OS.deployment.abstracted-os-provider` logic and return the result. The Control Plane aggregates the thousands of JSON responses into a single, LLM-friendly summary payload.

---

## SM-OS.deployment.deep-introspection-telemetry: Deep Introspection Telemetry

**What it is:**
The ability to pull low-level OS telemetry (processes, memory maps, TCP/UDP sockets, event logs, and kernel traces) into the agent's context.

**Why it matters:**
Diagnostic agents need more than just CPU metrics. They need to trace exactly which process is holding port 443, what command line flags spawned it, and what kernel modules are backing it. This achieves `ProcMon`-level observability without needing external observability stacks.

**How it works:**
Extends `psutil` native features and utilizes advanced OS-specific diagnostic tracing (e.g., ETW for Windows, eBPF/strace for Linux) mapped directly into FastMCP endpoints.

---

## SM-OS.deployment.package-service-mutation: Package & Service Mutation

**What it is:**
The action-oriented capabilities for modifying the host system—installing packages, restarting daemon services, and optimizing filesystem resources.

**Why it matters:**
Introspection (`SM-OS.deployment.deep-introspection-telemetry`) identifies the problem, but Mutation (`SM-OS.deployment.package-service-mutation`) enables the Agent to implement the fix.

**How it works:**
Exposes tools like `install_applications`, `update`, `optimize`, and `manage_service`. The OS Provider determines whether to route a package installation to `apt`, `dnf`, `choco`, or `winget`. All mutations are protected by `agent-utilities` Identity Management and Destructive Action confirmation gates.
