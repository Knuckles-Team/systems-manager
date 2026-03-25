"""Systems Manager graph configuration — tag prompts and env var mappings.

This is the only file needed to enable graph mode for this agent.
Provides TAG_PROMPTS and TAG_ENV_VARS for create_graph_agent_server().
"""

# ── Tag → System Prompt Mapping ──────────────────────────────────────
TAG_PROMPTS: dict[str, str] = {
    "cron": (
        "You are a Systems Manager Cron specialist. Help users manage and interact with Cron functionality using the available tools."
    ),
    "disk": (
        "You are a Systems Manager Disk specialist. Help users manage and interact with Disk functionality using the available tools."
    ),
    "filesystem": (
        "You are a Systems Manager Filesystem specialist. Help users manage and interact with Filesystem functionality using the available tools."
    ),
    "firewall_management": (
        "You are a Systems Manager Firewall Management specialist. Help users manage and interact with Firewall Management functionality using the available tools."
    ),
    "log": (
        "You are a Systems Manager Log specialist. Help users manage and interact with Log functionality using the available tools."
    ),
    "network": (
        "You are a Systems Manager Network specialist. Help users manage and interact with Network functionality using the available tools."
    ),
    "nodejs": (
        "You are a Systems Manager Nodejs specialist. Help users manage and interact with Nodejs functionality using the available tools."
    ),
    "process": (
        "You are a Systems Manager Process specialist. Help users manage and interact with Process functionality using the available tools."
    ),
    "python": (
        "You are a Systems Manager Python specialist. Help users manage and interact with Python functionality using the available tools."
    ),
    "service": (
        "You are a Systems Manager Service specialist. Help users manage and interact with Service functionality using the available tools."
    ),
    "shell": (
        "You are a Systems Manager Shell specialist. Help users manage and interact with Shell functionality using the available tools."
    ),
    "ssh_management": (
        "You are a Systems Manager Ssh Management specialist. Help users manage and interact with Ssh Management functionality using the available tools."
    ),
    "system": (
        "You are a Systems Manager System specialist. Help users manage and interact with System functionality using the available tools."
    ),
    "user": (
        "You are a Systems Manager User specialist. Help users manage and interact with User functionality using the available tools."
    ),
}


# ── Tag → Environment Variable Mapping ────────────────────────────────
TAG_ENV_VARS: dict[str, str] = {
    "cron": "CRONTOOL",
    "disk": "DISKTOOL",
    "filesystem": "FILESYSTEMTOOL",
    "firewall_management": "FIREWALL_MANAGEMENTTOOL",
    "log": "LOGTOOL",
    "network": "NETWORKTOOL",
    "nodejs": "NODEJSTOOL",
    "process": "PROCESSTOOL",
    "python": "PYTHONTOOL",
    "service": "SERVICETOOL",
    "shell": "SHELLTOOL",
    "ssh_management": "SSH_MANAGEMENTTOOL",
    "system": "SYSTEMTOOL",
    "user": "USERTOOL",
}
