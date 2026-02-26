---
name: systems-manager-ssh-management
description: Systems Manager SSH Key Management capabilities for A2A Agent.
tags: [ssh, ssh-management]
---
### Overview
This skill provides access to SSH key management operations.

### Capabilities
- **list_ssh_keys**: Lists all SSH keys in the user's ~/.ssh directory.
- **generate_ssh_key**: Generates a new SSH key pair.
- **add_authorized_key**: Adds a public key to the authorized_keys file.

### Common Tools
- `list_ssh_keys`: Lists all SSH keys in the user's ~/.ssh directory.
- `generate_ssh_key`: Generates a new SSH key pair.
- `add_authorized_key`: Adds a public key to the authorized_keys file.

### Common Prompts
- "List all ssh management information"
- "Lists all SSH keys in the user's ~/.ssh directory"
- "Generates a new SSH key pair"
- "Adds a public key to the authorized_keys file"

### MCP Tags
- `ssh_management`
