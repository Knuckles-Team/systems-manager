import os
import re

files_to_fix = [
    "tests/test_linux_managers.py",
    "tests/test_mcp_server.py",
    "tests/test_systems_manager_base.py",
    "tests/test_windows_manager.py",
]

base_dir = "/home/apps/workspace/agent-packages/agents/systems-manager"

vulture_output = """
tests/test_linux_managers.py:17: unused variable 'mock_linux_platform' (100% confidence)
tests/test_linux_managers.py:39: unused variable 'kwargs' (100% confidence)
tests/test_linux_managers.py:55: unused variable 'kwargs' (100% confidence)
tests/test_linux_managers.py:76: unused variable 'kwargs' (100% confidence)
tests/test_linux_managers.py:123: unused variable 'kwargs' (100% confidence)
tests/test_linux_managers.py:162: unused variable 'kwargs' (100% confidence)
tests/test_linux_managers.py:206: unused variable 'kwargs' (100% confidence)
tests/test_linux_managers.py:232: unused variable 'kwargs' (100% confidence)
tests/test_linux_managers.py:349: unused variable 'mock_rhel_platform' (100% confidence)
tests/test_linux_managers.py:370: unused variable 'kwargs' (100% confidence)
tests/test_linux_managers.py:582: unused variable 'kwargs' (100% confidence)
tests/test_linux_managers.py:761: unused variable 'mock_arch_platform' (100% confidence)
tests/test_linux_managers.py:782: unused variable 'kwargs' (100% confidence)
tests/test_linux_managers.py:889: unused variable 'kwargs' (100% confidence)
tests/test_mcp_server.py:690: unused variable 'kwargs' (100% confidence)
tests/test_mcp_server.py:702: unused variable 'kwargs' (100% confidence)
tests/test_mcp_server.py:714: unused variable 'kwargs' (100% confidence)
tests/test_mcp_server.py:755: unused variable 'kwargs' (100% confidence)
tests/test_mcp_server.py:803: unused variable 'mock_requests_get' (100% confidence)
tests/test_systems_manager_base.py:364: unused variable 'kwargs' (100% confidence)
tests/test_systems_manager_base.py:379: unused variable 'kwargs' (100% confidence)
tests/test_systems_manager_base.py:390: unused variable 'kwargs' (100% confidence)
tests/test_systems_manager_base.py:404: unused variable 'kwargs' (100% confidence)
tests/test_systems_manager_base.py:419: unused variable 'kwargs' (100% confidence)
tests/test_systems_manager_base.py:433: unused variable 'kwargs' (100% confidence)
tests/test_systems_manager_base.py:447: unused variable 'kwargs' (100% confidence)
tests/test_systems_manager_base.py:464: unused variable 'kwargs' (100% confidence)
tests/test_systems_manager_base.py:862: unused variable 'kwargs' (100% confidence)
tests/test_systems_manager_base.py:981: unused variable 'kwargs' (100% confidence)
tests/test_windows_manager.py:13: unused variable 'mock_windows_platform' (100% confidence)
tests/test_windows_manager.py:26: unused variable 'mock_windows_platform' (100% confidence)
tests/test_windows_manager.py:57: unused variable 'kwargs' (100% confidence)
tests/test_windows_manager.py:89: unused variable 'kwargs' (100% confidence)
tests/test_windows_manager.py:103: unused variable 'kwargs' (100% confidence)
tests/test_windows_manager.py:141: unused variable 'kwargs' (100% confidence)
tests/test_windows_manager.py:214: unused variable 'kwargs' (100% confidence)
tests/test_windows_manager.py:247: unused variable 'kwargs' (100% confidence)
tests/test_windows_manager.py:376: unused variable 'mock_windows_platform' (100% confidence)
"""

for line in vulture_output.strip().split("\n"):
    parts = line.split(":")
    if len(parts) < 3:
        continue
    file_rel = parts[0]
    line_num = int(parts[1])
    var_match = re.search(r"unused variable '([^']+)'", parts[2])
    if not var_match:
        continue
    var_name = var_match.group(1)

    abs_path = os.path.join(base_dir, file_rel)
    if not os.path.exists(abs_path):
        continue

    with open(abs_path) as f:
        file_lines = f.readlines()

    idx = line_num - 1
    if idx < len(file_lines):
        # Be careful not to replace part of a longer word
        # This is a bit naive but usually fine for these specific vars
        file_lines[idx] = re.sub(rf"\b{var_name}\b", f"_{var_name}", file_lines[idx])

    with open(abs_path, "w") as f:
        f.writelines(file_lines)

print("Vulture fixes applied.")
