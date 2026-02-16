---
name: systems-manager-process-management
description: Systems Manager Process Management capabilities for A2A Agent.
---
### Overview
This skill provides access to process management operations for monitoring and controlling processes.

### Capabilities
- **list_processes**: Lists all running processes with PID, name, CPU%, memory%, and status.
- **get_process_info**: Gets detailed information about a specific process by PID.
- **kill_process**: Kills a process by PID. Default signal is SIGTERM (15), use 9 for SIGKILL.

### Common Tools
- `list_processes`: Lists all running processes with PID, name, CPU%, memory%, and status.
- `get_process_info`: Gets detailed information about a specific process by PID.
- `kill_process`: Kills a process by PID. Default signal is SIGTERM (15), use 9 for SIGKILL.

### Common Prompts
- "List all process management information"
- "Lists all running processes with PID, name, CPU%, memory%, and status"
- "Gets detailed information about a specific process by PID"
- "Kills a process by PID. Default signal is SIGTERM (15), use 9 for SIGKILL"

### MCP Tags
- `process_management`
