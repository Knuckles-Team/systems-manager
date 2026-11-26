---
name: sm-runtime-provisioning
skill_type: skill
description: >-
  Provision developer runtimes through systems-manager: install uv, nvm and Node, select a Node version, create virtual environments, install packages and add an authorized SSH key. Use when a host or user needs a runtime set up.
---

# sm-runtime-provisioning

Runtime provisioning for a user account.

## Steps

1. Read the current state with `sm_system_list_installed_packages` and verify whether uv, nvm or Node is already present.
2. Install only the missing runtime with `sm_advanced_install_uv`, `sm_advanced_install_nvm` or `sm_advanced_install_node`, and verify the tool returns a success status and a version.
3. Select the Node version with `sm_advanced_use_node` and verify the reported active version matches the one requested.
4. Create the environment with `sm_advanced_create_venv` and verify the returned path exists before installing into it.
5. Add packages with `sm_advanced_install_package` and verify the package name and version appear in the tool result.
6. Add an authorized key only when requested, using `sm_advanced_add_authorized_key`, and verify the key fingerprint in the result matches the one supplied.

## Failure recovery

| Failure | Cause | Recovery |
|---|---|---|
| An install tool is denied by policy | Host mutation is not enabled for this deployment | Report the denial and stop, because a policy denial is final |
| `sm_advanced_install_package` cannot find the environment | `sm_advanced_create_venv` was not run or used another path | Call `sm_advanced_create_venv` with the target path and pass that same path to `sm_advanced_install_package` |
| `sm_advanced_use_node` reports the version is not installed | `sm_advanced_install_node` was not run for that version | Call `sm_advanced_install_node` with the version, and call `sm_advanced_use_node` with the same value afterwards |
| `sm_advanced_add_authorized_key` is refused | The key text is malformed or the user account is wrong | Supply the public key line unchanged and the correct account name |

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
