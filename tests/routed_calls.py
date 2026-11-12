"""Call an operation by its routing group and action, as the one tool per action it now is."""

from typing import Any

#: routing group -> tool prefix
PREFIXES = {
    "sm_system_operations": "sm_system",
    "sm_service_operations": "sm_service",
    "sm_process_operations": "sm_process",
    "sm_network_operations": "sm_network",
    "sm_disk_operations": "sm_disk",
    "sm_user_operations": "sm_user",
    "sm_file_operations": "sm_file",
    "sm_cron_operations": "sm_cron",
    "sm_firewall_operations": "sm_firewall",
    "sm_advanced_operations": "sm_advanced",
}


def tool_for(name: str, arguments: dict[str, Any] | None) -> tuple[str, dict[str, Any]]:
    """Map ``(group, {"action": a, ...})`` to ``(<prefix>_<a>, {...})``."""
    arguments = dict(arguments or {})
    if name in PREFIXES and "action" in arguments:
        return f"{PREFIXES[name]}_{arguments.pop('action')}", arguments
    return name, arguments


class RoutedServer:
    """Wrap a FastMCP server or client so ``call_tool`` accepts the old group-and-action form."""

    def __init__(self, target: Any) -> None:
        self._target = target

    async def call_tool(
        self, name: str, arguments: Any = None, *args: Any, **kwargs: Any
    ):
        name, arguments = tool_for(name, arguments)
        return await self._target.call_tool(name, arguments, *args, **kwargs)

    def __getattr__(self, item: str) -> Any:
        return getattr(self._target, item)
