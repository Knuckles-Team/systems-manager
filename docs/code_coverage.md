# Code Coverage & Testing Integration Progress

This document tracks the code coverage diagnostics, baseline metrics, architectural blueprints, and execution pipelines utilized to elevate `pytest` code coverage for the `systems-manager` agent package.

---

## 📊 Code Coverage Uplift

Through targeted architectural testing, the codebase's overall code coverage was significantly increased.

### Coverage Progress
- **Baseline Coverage**: `13%` (with 1,978 statement misses)
- **Current Coverage**: `61%` (an increase of **+48%**)

### Breakdown by Module File

| Module File | Statement Count | Missed Statements | Current Coverage | Status | Key Targeted Gaps Filled |
| :--- | :---: | :---: | :---: | :---: | :--- |
| [`os_provider_tools.py`](https://github.com/Knuckles-Team/systems-manager/blob/main/systems_manager/os_provider_tools.py) | 101 | 0 | **100%** | 🟢 Passed | Comprehensive registration and execution of OS provider MCP tools. |
| [`agent_os_tools.py`](https://github.com/Knuckles-Team/systems-manager/blob/main/systems_manager/agent_os_tools.py) | 230 | 28 | **88%** | 🟢 Passed | Covered specialist registration, identities, schedulers, and watchdogs. |
| [`os_provider.py`](https://github.com/Knuckles-Team/systems-manager/blob/main/systems_manager/os_provider.py) | 171 | 8 | **95%** | 🟢 Passed | Mocked `psutil` metrics, telemetry, and platform service listings. |
| [`models.py`](https://github.com/Knuckles-Team/systems-manager/blob/main/systems_manager/models.py) | 57 | 6 | **89%** | 🟢 Passed | Covered dictionary override and fallback checks. |
| [`mcp_server.py`](https://github.com/Knuckles-Team/systems-manager/blob/main/systems_manager/mcp_server.py) | 260 | 37 | **86%** | 🟢 Passed | Routing of system operations, platform operations, and tools. |
| [`systems_manager.py`](https://github.com/Knuckles-Team/systems-manager/blob/main/systems_manager/systems_manager.py) | 1399 | 767 | **45%** | 🟡 Improving | Covered FileSystem and Profile Manager, PythonManager, and NodeManager. |

---

## 🔍 Core Mocking Blueprints

To achieve safe, repeatable tests without mutating the host machine or relying on specific underlying OS platforms, the test suites leverage four advanced testing paradigms:

### 1. Sandboxed Home Directory Environment
By redirecting the user's `HOME` directory to a temporary path, tests safely mutate file system layouts and shell profiles (`.bashrc`, `.zshrc`, PowerShell scripts) under test:

```python
@pytest.fixture
def temp_home(tmp_path, monkeypatch):
    """Sets a temporary HOME directory to isolate file/profile changes."""
    home_dir = tmp_path / "home"
    home_dir.mkdir()
    monkeypatch.setenv("HOME", str(home_dir))
    return home_dir
```

### 2. Deep `subprocess` & CLI Mocking
All mutating operating system changes (such as installing/uninstalling packages via `apt`, `yum`, or `brew`, or executing Python virtual environment builders) are intercepted:

```python
with patch("subprocess.run") as mock_run:
    mock_run.return_value = MagicMock(
        returncode=0,
        stdout="Preparing to unpack...\nUnpacking htop...\nSetting up htop...",
        stderr=""
    )
    # Exercise and verify command parameters
```

### 3. Comprehensive `psutil` Telemetry Simulation
The abstract `OSProvider` captures active system processes, CPU/memory stats, network connection states, and user sessions by mocking underlying telemetry libraries:

```python
with patch("psutil.cpu_percent", return_value=12.5), \
     patch("psutil.virtual_memory") as mock_vm:

    mock_vm.return_value = MagicMock(
        total=16000000000,
        available=8000000000,
        percent=50.0
    )
    # Verify metric compilation and formatting
```

### 4. Direct FastMCP Routing Integration
FastMCP server tool registrations are validated end-to-end by invoking the tool executors directly via the server context:

```python
args, mcp_server, middlewares = get_mcp_instance()

# Call the registered tool asynchronously
res = await mcp_server.call_tool("issue_agent_identity", arguments={
    "agent_name": "agent-test",
    "role": "specialist"
})
```

---

## 🚀 Execution & Verification

Run the full automated test suite and generate coverage reports using:

```bash
uv run pytest --cov=systems_manager --cov-report=term-missing
```
