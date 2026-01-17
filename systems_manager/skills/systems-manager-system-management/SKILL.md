---
name: systems-manager-system-management
description: Systems Manager System Management capabilities for A2A Agent.
---
### Overview
This skill provides access to system_management operations.

### Capabilities
- **install_applications**: Installs applications using the native package manager with Snap fallback.
- **update**: Updates the system and applications.
- **clean**: Cleans system resources (e.g., trash/recycle bin).
- **optimize**: Optimizes system resources (e.g., autoremove, defrag).
- **install_python_modules**: Installs Python modules via pip.
- **install_fonts**: Installs specified Nerd Fonts or all available fonts if 'all' is specified.
- **get_os_statistics**: Retrieves operating system statistics.
- **get_hardware_statistics**: Retrieves hardware statistics.
- **list_windows_features**: Lists all Windows features and their status (Windows only).
- **enable_windows_features**: Enables specified Windows features (Windows only).
- **disable_windows_features**: Disables specified Windows features (Windows only).
- **add_repository**: Adds an upstream repository to the package manager repository list (Linux only).
- **install_local_package**: Installs a local Linux package file using the appropriate tool (dpkg/rpm/dnf/zypper/pacman). (Linux only)
- **run_command**: Runs a command on the host. Can run elevated for administrator or root privileges.

### Common Tools
- `install_applications`: Installs applications using the native package manager with Snap fallback.
- `update`: Updates the system and applications.
- `clean`: Cleans system resources (e.g., trash/recycle bin).
- `optimize`: Optimizes system resources (e.g., autoremove, defrag).
- `install_python_modules`: Installs Python modules via pip.
- `install_fonts`: Installs specified Nerd Fonts or all available fonts if 'all' is specified.
- `get_os_statistics`: Retrieves operating system statistics.
- `get_hardware_statistics`: Retrieves hardware statistics.
- `list_windows_features`: Lists all Windows features and their status (Windows only).
- `enable_windows_features`: Enables specified Windows features (Windows only).
- `disable_windows_features`: Disables specified Windows features (Windows only).
- `add_repository`: Adds an upstream repository to the package manager repository list (Linux only).
- `install_local_package`: Installs a local Linux package file using the appropriate tool (dpkg/rpm/dnf/zypper/pacman). (Linux only)
- `run_command`: Runs a command on the host. Can run elevated for administrator or root privileges.

### Usage Rules
- Use these tools when the user requests actions related to **system_management**.
- Always interpret the output of these tools to provide a concise summary to the user.

### Example Prompts
- "Please optimize"
- "Please install applications"
- "Please install python modules"
- "Please disable windows features"
- "Please install local package"
