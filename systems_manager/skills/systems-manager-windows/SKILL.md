---
name: systems-manager-windows
description: Systems Manager Windows capabilities for A2A Agent.
---
### Overview
This skill provides access to windows operations.

### Capabilities
- **list_windows_features**: Lists all Windows features and their status (Windows only).
- **enable_windows_features**: Enables specified Windows features (Windows only).
- **disable_windows_features**: Disables specified Windows features (Windows only).

### Common Tools
- `list_windows_features`: Lists all Windows features and their status (Windows only).
- `enable_windows_features`: Enables specified Windows features (Windows only).
- `disable_windows_features`: Disables specified Windows features (Windows only).

### Usage Rules
- Use these tools when the user requests actions related to **windows**.
- Always interpret the output of these tools to provide a concise summary to the user.

### Example Prompts
- "Please disable windows features"
- "Please enable windows features"
- "Please list windows features"
