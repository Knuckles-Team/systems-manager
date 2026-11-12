---
name: sm-packages-and-maintenance
skill_type: skill
description: >-
  Install, update, clean and reboot hosts through systems-manager: package search, info and inventory, repositories, installs, updates, cleanup, optimize, reboot, environment variables, Python modules and Windows features. Use for software lifecycle and host maintenance.
---

# sm-packages-and-maintenance

Package and maintenance work. Search and read first; every install, clean or reboot is a confirmed change.

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
