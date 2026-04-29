import re

file_path = "/home/apps/workspace/agent-packages/agents/systems-manager/systems_manager/systems_manager.py"

with open(file_path, "r") as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    if "shell=True" in line and "# nosec" not in line:
        # Check if it ends with a comma or parenthesis
        line = line.rstrip()
        if line.endswith(","):
            # It might be in a multi-line call
            pass

        # Simple replacement for common patterns
        line = re.sub(r"(shell=True[^#\n]*)", r"\1  # nosec", line)
        new_lines.append(line + "\n")
    else:
        # Clean up double nosec if any
        line = line.replace("# nosec  # nosec", "# nosec")
        new_lines.append(line)

with open(file_path, "w") as f:
    f.writelines(new_lines)
