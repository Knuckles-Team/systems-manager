---
name: systems-manager-linux
description: Systems Manager Linux capabilities for A2A Agent.
---
### Overview
This skill provides access to linux operations.

### Capabilities
- **add_repository**: Adds an upstream repository to the package manager repository list (Linux only).
- **install_local_package**: Installs a local Linux package file using the appropriate tool (dpkg/rpm/dnf/zypper/pacman). (Linux only)
- **run_command**: Runs a command on the host. Can run elevated for administrator or root privileges.

### Common Tools
- `add_repository`: Adds an upstream repository to the package manager repository list (Linux only).
- `install_local_package`: Installs a local Linux package file using the appropriate tool (dpkg/rpm/dnf/zypper/pacman). (Linux only)
- `run_command`: Runs a command on the host. Can run elevated for administrator or root privileges.

### Usage Rules
- Use these tools when the user requests actions related to **linux**.
- Always interpret the output of these tools to provide a concise summary to the user.

### Example Prompts
- "Please add repository"
- "Please install local package"
- "Please run command"
