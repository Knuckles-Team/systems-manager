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
- **install_python_modules**: Installs Python modules using pip.
- **get_os_statistics**: Gets OS information (platform, version, architecture).
- **get_hardware_statistics**: Gets hardware statistics (CPU, memory, disk, network).
- **search_package**: Searches for packages in the system package manager repositories.
- **get_package_info**: Gets detailed information about a specific package.
- **list_installed_packages**: Lists all installed packages on the system.
- **list_upgradable_packages**: Lists all packages that have updates available.
- **system_health_check**: Performs a comprehensive system health check including CPU, memory, disk, swap, and top processes.
- **get_uptime**: Gets system uptime and boot time.
- **list_env_vars**: Lists all environment variables on the system.
- **get_env_var**: Gets the value of a specific environment variable.
- **clean_temp_files**: Cleans temporary files from system temp directories.
- **clean_package_cache**: Cleans the package manager cache to free disk space.

### Common Tools
- `install_applications`: Installs applications using the native package manager with Snap fallback.
- `update`: Updates the system and applications.
- `clean`: Cleans system resources (e.g., trash/recycle bin).
- `optimize`: Optimizes system resources (e.g., autoremove, defrag).
- `install_python_modules`: Installs Python modules using pip.
- `get_os_statistics`: Gets OS information (platform, version, architecture).
- `get_hardware_statistics`: Gets hardware statistics (CPU, memory, disk, network).
- `search_package`: Searches for packages in the system package manager repositories.
- `get_package_info`: Gets detailed information about a specific package.
- `list_installed_packages`: Lists all installed packages on the system.
- `list_upgradable_packages`: Lists all packages that have updates available.
- `system_health_check`: Performs a comprehensive system health check.
- `get_uptime`: Gets system uptime and boot time.
- `list_env_vars`: Lists all environment variables.
- `get_env_var`: Gets a specific environment variable.
- `clean_temp_files`: Cleans temporary files from system temp directories.
- `clean_package_cache`: Cleans the package manager cache.

### Common Prompts
- "Install these applications: vim, git, curl"
- "Update all system packages"
- "Clean up system resources"
- "Optimize the system"
- "Install python modules: requests, flask"
- "What operating system is this?"
- "Show hardware statistics"
- "Search for package nginx"
- "Show info for package git"
- "List all installed packages"
- "What packages need updating?"
- "Run a system health check"
- "How long has the system been running?"
- "Show all environment variables"
- "What is the value of PATH?"
- "Clean temporary files"
- "Clean the package cache"

### MCP Tags
- `system_management`
