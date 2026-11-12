---
name: sm-runtime-provisioning
skill_type: skill
description: >-
  Provision developer runtimes through systems-manager: install uv, nvm and Node, select a Node version, create virtual environments, install packages and add an authorized SSH key. Use when a host or user needs a runtime set up.
---

# sm-runtime-provisioning

Runtime provisioning for a user account.

## Runtimes

- `sm_advanced_install_uv`: install uv
- `sm_advanced_install_nvm`: install nvm
- `sm_advanced_install_node`: install Node
- `sm_advanced_use_node`: select a Node version
- `sm_advanced_create_venv`: create a virtual environment
- `sm_advanced_install_package`: install a package into it

## Access

- `sm_advanced_add_authorized_key`: add an authorized SSH key

## Rules

- Read the state before a change and again after it.
- A destructive tool needs the requester's explicit confirmation (`confirm=true`).
- A policy denial is final; never route around it with another tool.
