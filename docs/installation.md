# Day-0 Installation & Verification Guide

This guide walkthroughs the complete, step-by-step process of installing `systems-manager` on a fresh Linux machine, configuring the secure `sudo` wrapper, and verifying the elevated capabilities under the Principle of Least Privilege (PoLP).

---

## Prerequisites

* **Operating System**: Modern Linux distribution (Ubuntu/Debian recommended; also supports RedHat/CentOS, SUSE, Arch).
* **Python**: Python `>= 3.11` and `< 3.14`.
* **Package Manager**: `pip` or `uv` installed.
* **Sudo Privileges**: Access to `sudo` once during initial setup to write the policy file.

---

## 1. Fresh Workspace Setup

We recommend installing `systems-manager` in a virtual environment to prevent dependency conflicts with the system Python packages.

### Option A: Using `uv` (Fastest)

```bash
# 1. Create a virtual environment
uv venv

# 2. Activate the virtual environment
source .venv/bin/activate

# 3. Install systems-manager from PyPI (or local source folder)
uv pip install systems-manager
```

### Option B: Using standard Python `venv`

```bash
# 1. Create a virtual environment
python3 -m venv .venv

# 2. Activate the virtual environment
source .venv/bin/activate

# 3. Upgrade pip and install systems-manager
pip install --upgrade pip
pip install systems-manager
```

Verify that the CLI command is accessible:
```bash
systems-manager --help
```

---

## 2. Elevated Sudo Wrapper Bootstrapping

To allow the systems manager agent to perform package updates and service management without asking for interactive sudo passwords, execute the self-bootstrapping command:

```bash
systems-manager --setup-sudo
```

### Under the Hood: What `--setup-sudo` Does

1. **Auto-discovers the Current User**: Dynamically determines the standard user executing the agent (e.g. `standard_user`).
2. **Locates the Helper Binary**: Scans the `PATH` and virtual environment folders to find the exact absolute path of the `systems-manager-helper` script entrypoint.
3. **Generates Sudoers Rule**: Constructs a highly restrictive policy statement allowing passwordless sudo access **only** to the helper:
   ```text
   <username> ALL=(ALL) NOPASSWD: /path/to/systems-manager-helper
   ```
4. **Visudo Verification Check**: Writes this statement to a temporary file, executes `visudo -c -f /tmp/...` to ensure there are no syntax errors, and aborts immediately if any errors are detected.
5. **Registers System Policy**: Copies the validated configuration to `/etc/sudoers.d/systems-manager-<username>`, sets the owner to `root:root`, and restricts the file permissions to read-only `0440`.

---

## 3. Verify Sudoers Policy

To manually verify that the bootstrapping succeeded, run the following diagnostic checks:

### Verify Policy File Existence & Permissions
```bash
ls -lh /etc/sudoers.d/systems-manager-$(whoami)
```
**Expected Output:**
```text
-r--r----- 1 root root 82 May 26 13:30 /etc/sudoers.d/systems-manager-<username>
```

### Verify Policy File Content
```bash
sudo cat /etc/sudoers.d/systems-manager-$(whoami)
```
**Expected Output:**
```text
<username> ALL=(ALL) NOPASSWD: /home/<username>/.../bin/systems-manager-helper
```

---

## 4. Operational Verification

To ensure that standard (non-root) execution is successfully delegating privileged tasks to the secure helper, run these standard commands as your normal user (without using `sudo` on the main CLI):

### Service Control Verification
Attempt to check the status or manage one of the whitelisted services (e.g., `docker` or `nginx`):

```bash
# Check status of docker service
systems-manager --silent -c "" # (or run directly via python code)
```

You can test programmatic execution within a Python shell or an agent script:

```python
from systems_manager.systems_manager import AptManager

# Instantiate the manager
manager = AptManager()

# Start docker service - this will automatically invoke the sudo helper under the hood!
result = manager.start_service("docker")
print("Success:", result.success)
print("Output:", result.stdout)
```

### Package Management Verification
Verify that standard system packages can be queried, updated, or installed through the manager:

```python
from systems_manager.systems_manager import AptManager

manager = AptManager()

# Check for upgradable packages
result = manager.list_upgradable_packages()
print("Upgradable packages found:", len(result.stdout) > 0)

# Install a whitelisted package (e.g. htop)
install_result = manager.install_applications(["htop"])
print("HTOP Installed:", install_result["success"])
```

If you attempt to perform an operation on a non-whitelisted service or package, you should see a secure rejection:
```python
# Rejection expected
result = manager.start_service("ssh-malicious")
print("Success:", result.success)
print("Error Message:", result.error)
```
**Expected Error Message:**
```text
Service 'ssh-malicious' is not in the secure helper whitelist.
```
