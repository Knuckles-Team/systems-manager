---
name: systems-manager-firewall-management
description: Systems Manager Firewall Management capabilities for A2A Agent.
tags: [firewall, firewall-management]
---
### Overview
This skill provides access to firewall management operations (ufw/firewalld/iptables on Linux, netsh on Windows).

### Capabilities
- **get_firewall_status**: Gets the current firewall status.
- **list_firewall_rules**: Lists all firewall rules.
- **add_firewall_rule**: Adds a firewall rule using the detected firewall tool.
- **remove_firewall_rule**: Removes a firewall rule using the detected firewall tool.

### Common Tools
- `get_firewall_status`: Gets the current firewall status.
- `list_firewall_rules`: Lists all firewall rules.
- `add_firewall_rule`: Adds a firewall rule using the detected firewall tool.
- `remove_firewall_rule`: Removes a firewall rule using the detected firewall tool.

### Common Prompts
- "List all firewall management information"
- "Gets the current firewall status"
- "Lists all firewall rules"
- "Adds a firewall rule using the detected firewall tool"
- "Removes a firewall rule using the detected firewall tool"

### MCP Tags
- `firewall_management`
