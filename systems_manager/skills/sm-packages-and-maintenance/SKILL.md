---
name: sm-packages-and-maintenance
skill_type: skill
description: >-
  Install, update, clean and reboot hosts through systems-manager: package search, info and inventory, repositories, installs, updates, cleanup, optimize, reboot, environment variables, Python modules and Windows features. Use for software lifecycle and host maintenance.
---

# sm-packages-and-maintenance

Package and maintenance work. Search and read first; every install, clean or reboot is a confirmed change.

## Steps

1. Look up the package with `sm_system_search_package` and `sm_system_get_package_info`, and verify the name and version match the request.
2. Check what is already present with `sm_system_list_installed_packages` and `sm_system_list_upgradable_packages`, and verify the package is not installed at the wanted version.
3. Apply one change with `sm_system_install_applications`, `sm_system_install_local_package` or `sm_system_update`, passing `confirm=true`, and verify the tool returns a success status.
4. Reclaim space only on request with `sm_system_clean_package_cache` or `sm_system_clean_temp_files`, and verify the reported freed space.
5. Reboot with `sm_system_reboot` only after explicit confirmation, and verify the host answers `health_check` after it returns.

## Failure recovery

| Failure | Cause | Recovery |
|---|---|---|
| An install or update is rejected | `confirm=true` was not supplied | Ask the requester to confirm, and pass `confirm=true` on the same call |
| `sm_system_install_applications` reports package not found | The repository is missing or the name is wrong | Search with `sm_system_search_package` for the exact name, or add the source with `sm_system_add_repository` |
| A mutation is denied by policy | Host mutation is not enabled for this deployment | Report the denial and stop, because a policy denial is final |
| `sm_system_install_local_package` cannot read the file | The path is outside the managed root | Place the file under the managed root and pass that path |

## Packages

- `sm_system_search_package`: search
- `sm_system_get_package_info`: package info
- `sm_system_list_installed_packages`: installed
- `sm_system_list_upgradable_packages`: upgradable
- `sm_system_add_repository`: add a repository
- `sm_system_install_applications`: install
- `sm_system_install_local_package`: install a local package
- `sm_system_update`: update the system

## Maintenance

- `sm_system_clean`: full clean
- `sm_system_clean_package_cache`: package cache
- `sm_system_clean_temp_files`: temporary files
- `sm_system_optimize`: optimize
- `sm_system_reboot`: reboot

## Environment

- `sm_system_list_env_vars`: list variables
- `sm_system_get_env_var`: read one
- `sm_system_install_python_modules`: install Python modules

## Windows

- `sm_system_list_windows_features`: list features
- `sm_system_enable_windows_features`: enable
- `sm_system_disable_windows_features`: disable

## Rules

- Read the state before a change and again after it.
- A destructive tool needs the requester's explicit confirmation (`confirm=true`).
- A policy denial is final; never route around it with another tool.
