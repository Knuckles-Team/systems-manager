"""Surface contracts: tool use, links, data locations and business roles."""

from scion_sdk.surface_contracts import (
    BusinessRole,
    DataLocation,
    Refusal,
    SurfaceLink,
    ToolStep,
    ToolUseContract,
)

CONTRACTS = (
    ToolUseContract(
        task="assess-host-health",
        description="Read capability, uptime, OS and hardware statistics and the health check of a host.",
        steps=(
            ToolStep(
                tool="health_check",
                params=(),
                result=("result",),
                refusals=(
                    Refusal(
                        "ACCESS_DENIED", "the credential lacks access to the operation"
                    ),
                    Refusal(
                        "INVALID_ARGUMENT", "the upstream system rejects the input"
                    ),
                ),
            ),
            ToolStep(
                tool="get_management_capabilities",
                params=(),
                result=("result",),
                refusals=(
                    Refusal(
                        "ACCESS_DENIED", "the credential lacks access to the operation"
                    ),
                    Refusal(
                        "INVALID_ARGUMENT", "the upstream system rejects the input"
                    ),
                ),
            ),
            ToolStep(
                tool="sm_system_get_uptime",
                params=(),
                result=("uptime",),
                refusals=(
                    Refusal(
                        "ACCESS_DENIED", "the credential lacks access to the operation"
                    ),
                    Refusal(
                        "INVALID_ARGUMENT", "the upstream system rejects the input"
                    ),
                ),
            ),
            ToolStep(
                tool="sm_system_get_host_record",
                params=(),
                result=("host_id", "pendingUpdates", "uptimeSeconds"),
                refusals=(
                    Refusal(
                        "ACCESS_DENIED", "the credential lacks access to the operation"
                    ),
                    Refusal(
                        "INVALID_ARGUMENT", "the upstream system rejects the input"
                    ),
                ),
            ),
            ToolStep(
                tool="sm_system_get_os_statistics",
                params=(),
                result=("os", "version"),
                refusals=(
                    Refusal(
                        "ACCESS_DENIED", "the credential lacks access to the operation"
                    ),
                    Refusal(
                        "INVALID_ARGUMENT", "the upstream system rejects the input"
                    ),
                ),
            ),
            ToolStep(
                tool="sm_system_get_hardware_statistics",
                params=(),
                result=("cpu_count", "memory_total"),
                refusals=(
                    Refusal(
                        "ACCESS_DENIED", "the credential lacks access to the operation"
                    ),
                    Refusal(
                        "INVALID_ARGUMENT", "the upstream system rejects the input"
                    ),
                ),
            ),
            ToolStep(
                tool="sm_system_system_health_check",
                params=(),
                result=("result",),
                refusals=(
                    Refusal(
                        "ACCESS_DENIED", "the credential lacks access to the operation"
                    ),
                    Refusal(
                        "INVALID_ARGUMENT", "the upstream system rejects the input"
                    ),
                ),
            ),
            ToolStep(
                tool="capture_system_snapshot",
                params=(),
                result=("snapshot",),
                refusals=(
                    Refusal(
                        "ACCESS_DENIED", "the credential lacks access to the operation"
                    ),
                    Refusal(
                        "INVALID_ARGUMENT", "the upstream system rejects the input"
                    ),
                ),
            ),
        ),
    ),
    ToolUseContract(
        task="ingest-host-graph",
        description="Project a privacy-safe host snapshot into the knowledge graph.",
        steps=(
            ToolStep(
                tool="get_management_capabilities",
                params=(),
                result=("result",),
                refusals=(
                    Refusal(
                        "ACCESS_DENIED", "the credential lacks access to the operation"
                    ),
                    Refusal(
                        "INVALID_ARGUMENT", "the upstream system rejects the input"
                    ),
                ),
            ),
            ToolStep(
                tool="capture_system_snapshot",
                params=(),
                result=("result",),
                refusals=(
                    Refusal(
                        "ACCESS_DENIED", "the credential lacks access to the operation"
                    ),
                    Refusal(
                        "INVALID_ARGUMENT", "the upstream system rejects the input"
                    ),
                ),
            ),
            ToolStep(
                tool="systems_ingest_host",
                params=(),
                result=("ingested",),
                refusals=(
                    Refusal(
                        "ACCESS_DENIED", "the credential lacks access to the operation"
                    ),
                    Refusal(
                        "INVALID_ARGUMENT", "the upstream system rejects the input"
                    ),
                ),
            ),
        ),
    ),
    ToolUseContract(
        task="investigate-logs",
        description="Query system logs and kernel modules to explain a fault.",
        steps=(
            ToolStep(
                tool="query_system_logs",
                params=("limit",),
                result=("entries",),
                refusals=(
                    Refusal(
                        "ACCESS_DENIED", "the credential lacks access to the operation"
                    ),
                    Refusal(
                        "INVALID_ARGUMENT", "the upstream system rejects the input"
                    ),
                ),
            ),
            ToolStep(
                tool="sm_file_get_system_logs",
                params=("lines",),
                result=("logs",),
                refusals=(
                    Refusal(
                        "ACCESS_DENIED", "the credential lacks access to the operation"
                    ),
                    Refusal(
                        "INVALID_ARGUMENT", "the upstream system rejects the input"
                    ),
                ),
            ),
            ToolStep(
                tool="sm_file_tail_log_file",
                params=("filepath", "lines"),
                result=("lines",),
                refusals=(
                    Refusal(
                        "ACCESS_DENIED", "the credential lacks access to the operation"
                    ),
                    Refusal(
                        "INVALID_ARGUMENT", "the upstream system rejects the input"
                    ),
                ),
            ),
            ToolStep(
                tool="list_kernel_modules",
                params=(),
                result=("modules",),
                refusals=(
                    Refusal(
                        "ACCESS_DENIED", "the credential lacks access to the operation"
                    ),
                    Refusal(
                        "INVALID_ARGUMENT", "the upstream system rejects the input"
                    ),
                ),
            ),
        ),
    ),
    ToolUseContract(
        task="trace-system-activity",
        description="Start a bounded system trace, read its logs, then stop it.",
        steps=(
            ToolStep(
                tool="start_system_trace",
                params=("session_name", "confirm"),
                result=("trace_id",),
                refusals=(
                    Refusal(
                        "ACCESS_DENIED", "the credential lacks access to the operation"
                    ),
                    Refusal(
                        "INVALID_ARGUMENT", "the upstream system rejects the input"
                    ),
                    Refusal(
                        "CONFIRMATION_REQUIRED",
                        "the caller has not confirmed the destructive call",
                    ),
                ),
            ),
            ToolStep(
                tool="query_system_logs",
                params=("limit",),
                result=("entries",),
                refusals=(
                    Refusal(
                        "ACCESS_DENIED", "the credential lacks access to the operation"
                    ),
                    Refusal(
                        "INVALID_ARGUMENT", "the upstream system rejects the input"
                    ),
                ),
            ),
            ToolStep(
                tool="stop_system_trace",
                params=("session_name", "confirm"),
                result=("result",),
                refusals=(
                    Refusal(
                        "ACCESS_DENIED", "the credential lacks access to the operation"
                    ),
                    Refusal(
                        "INVALID_ARGUMENT", "the upstream system rejects the input"
                    ),
                    Refusal(
                        "CONFIRMATION_REQUIRED",
                        "the caller has not confirmed the destructive call",
                    ),
                ),
            ),
        ),
    ),
    ToolUseContract(
        task="inspect-services",
        description="List services and read the status of one.",
        steps=(
            ToolStep(
                tool="list_services",
                params=(),
                result=("services",),
                refusals=(
                    Refusal(
                        "ACCESS_DENIED", "the credential lacks access to the operation"
                    ),
                    Refusal(
                        "INVALID_ARGUMENT", "the upstream system rejects the input"
                    ),
                ),
            ),
            ToolStep(
                tool="sm_service_list_services",
                params=(),
                result=("services",),
                refusals=(
                    Refusal(
                        "ACCESS_DENIED", "the credential lacks access to the operation"
                    ),
                    Refusal(
                        "INVALID_ARGUMENT", "the upstream system rejects the input"
                    ),
                ),
            ),
            ToolStep(
                tool="sm_service_get_service_status",
                params=("service_name",),
                result=("name", "state"),
                refusals=(
                    Refusal(
                        "ACCESS_DENIED", "the credential lacks access to the operation"
                    ),
                    Refusal(
                        "INVALID_ARGUMENT", "the upstream system rejects the input"
                    ),
                ),
            ),
        ),
    ),
    ToolUseContract(
        task="control-service",
        description="Start, stop, restart, enable or disable a service and read its status back.",
        steps=(
            ToolStep(
                tool="sm_service_get_service_status",
                params=("service_name",),
                result=("name", "state"),
                refusals=(
                    Refusal(
                        "ACCESS_DENIED", "the credential lacks access to the operation"
                    ),
                    Refusal(
                        "INVALID_ARGUMENT", "the upstream system rejects the input"
                    ),
                ),
            ),
            ToolStep(
                tool="sm_service_start_service",
                params=("service_name", "confirm"),
                result=("result",),
                refusals=(
                    Refusal(
                        "ACCESS_DENIED", "the credential lacks access to the operation"
                    ),
                    Refusal(
                        "INVALID_ARGUMENT", "the upstream system rejects the input"
                    ),
                    Refusal(
                        "CONFIRMATION_REQUIRED",
                        "the caller has not confirmed the destructive call",
                    ),
                ),
            ),
            ToolStep(
                tool="sm_service_stop_service",
                params=("service_name", "confirm"),
                result=("result",),
                refusals=(
                    Refusal(
                        "ACCESS_DENIED", "the credential lacks access to the operation"
                    ),
                    Refusal(
                        "INVALID_ARGUMENT", "the upstream system rejects the input"
                    ),
                    Refusal(
                        "CONFIRMATION_REQUIRED",
                        "the caller has not confirmed the destructive call",
                    ),
                ),
            ),
            ToolStep(
                tool="sm_service_restart_service",
                params=("service_name", "confirm"),
                result=("result",),
                refusals=(
                    Refusal(
                        "ACCESS_DENIED", "the credential lacks access to the operation"
                    ),
                    Refusal(
                        "INVALID_ARGUMENT", "the upstream system rejects the input"
                    ),
                    Refusal(
                        "CONFIRMATION_REQUIRED",
                        "the caller has not confirmed the destructive call",
                    ),
                ),
            ),
            ToolStep(
                tool="sm_service_enable_service",
                params=("service_name", "confirm"),
                result=("result",),
                refusals=(
                    Refusal(
                        "ACCESS_DENIED", "the credential lacks access to the operation"
                    ),
                    Refusal(
                        "INVALID_ARGUMENT", "the upstream system rejects the input"
                    ),
                    Refusal(
                        "CONFIRMATION_REQUIRED",
                        "the caller has not confirmed the destructive call",
                    ),
                ),
            ),
            ToolStep(
                tool="sm_service_disable_service",
                params=("service_name", "confirm"),
                result=("result",),
                refusals=(
                    Refusal(
                        "ACCESS_DENIED", "the credential lacks access to the operation"
                    ),
                    Refusal(
                        "INVALID_ARGUMENT", "the upstream system rejects the input"
                    ),
                    Refusal(
                        "CONFIRMATION_REQUIRED",
                        "the caller has not confirmed the destructive call",
                    ),
                ),
            ),
        ),
    ),
    ToolUseContract(
        task="control-service-by-provider",
        description="Drive a service through the provider-level lifecycle tools and read it back.",
        steps=(
            ToolStep(
                tool="list_services",
                params=(),
                result=("services",),
                refusals=(
                    Refusal(
                        "ACCESS_DENIED", "the credential lacks access to the operation"
                    ),
                    Refusal(
                        "INVALID_ARGUMENT", "the upstream system rejects the input"
                    ),
                ),
            ),
            ToolStep(
                tool="manage_service_start",
                params=("service_name", "confirm"),
                result=("result",),
                refusals=(
                    Refusal(
                        "ACCESS_DENIED", "the credential lacks access to the operation"
                    ),
                    Refusal(
                        "INVALID_ARGUMENT", "the upstream system rejects the input"
                    ),
                    Refusal(
                        "CONFIRMATION_REQUIRED",
                        "the caller has not confirmed the destructive call",
                    ),
                ),
            ),
            ToolStep(
                tool="manage_service_stop",
                params=("service_name", "confirm"),
                result=("result",),
                refusals=(
                    Refusal(
                        "ACCESS_DENIED", "the credential lacks access to the operation"
                    ),
                    Refusal(
                        "INVALID_ARGUMENT", "the upstream system rejects the input"
                    ),
                    Refusal(
                        "CONFIRMATION_REQUIRED",
                        "the caller has not confirmed the destructive call",
                    ),
                ),
            ),
            ToolStep(
                tool="manage_service_restart",
                params=("service_name", "confirm"),
                result=("result",),
                refusals=(
                    Refusal(
                        "ACCESS_DENIED", "the credential lacks access to the operation"
                    ),
                    Refusal(
                        "INVALID_ARGUMENT", "the upstream system rejects the input"
                    ),
                    Refusal(
                        "CONFIRMATION_REQUIRED",
                        "the caller has not confirmed the destructive call",
                    ),
                ),
            ),
            ToolStep(
                tool="manage_service_enable",
                params=("service_name", "confirm"),
                result=("result",),
                refusals=(
                    Refusal(
                        "ACCESS_DENIED", "the credential lacks access to the operation"
                    ),
                    Refusal(
                        "INVALID_ARGUMENT", "the upstream system rejects the input"
                    ),
                    Refusal(
                        "CONFIRMATION_REQUIRED",
                        "the caller has not confirmed the destructive call",
                    ),
                ),
            ),
            ToolStep(
                tool="manage_service_disable",
                params=("service_name", "confirm"),
                result=("result",),
                refusals=(
                    Refusal(
                        "ACCESS_DENIED", "the credential lacks access to the operation"
                    ),
                    Refusal(
                        "INVALID_ARGUMENT", "the upstream system rejects the input"
                    ),
                    Refusal(
                        "CONFIRMATION_REQUIRED",
                        "the caller has not confirmed the destructive call",
                    ),
                ),
            ),
        ),
    ),
    ToolUseContract(
        task="inspect-processes",
        description="List processes, read one in detail and see its network connections.",
        steps=(
            ToolStep(
                tool="sm_process_list_processes",
                params=(),
                result=("processes",),
                refusals=(
                    Refusal(
                        "ACCESS_DENIED", "the credential lacks access to the operation"
                    ),
                    Refusal(
                        "INVALID_ARGUMENT", "the upstream system rejects the input"
                    ),
                ),
            ),
            ToolStep(
                tool="sm_process_get_process_info",
                params=("pid",),
                result=("pid", "name"),
                refusals=(
                    Refusal(
                        "ACCESS_DENIED", "the credential lacks access to the operation"
                    ),
                    Refusal(
                        "INVALID_ARGUMENT", "the upstream system rejects the input"
                    ),
                ),
            ),
            ToolStep(
                tool="get_process_details",
                params=("pid",),
                result=("pid", "name"),
                refusals=(
                    Refusal(
                        "ACCESS_DENIED", "the credential lacks access to the operation"
                    ),
                    Refusal(
                        "INVALID_ARGUMENT", "the upstream system rejects the input"
                    ),
                ),
            ),
            ToolStep(
                tool="get_network_connections",
                params=(),
                result=("connections",),
                refusals=(
                    Refusal(
                        "ACCESS_DENIED", "the credential lacks access to the operation"
                    ),
                    Refusal(
                        "INVALID_ARGUMENT", "the upstream system rejects the input"
                    ),
                ),
            ),
        ),
    ),
    ToolUseContract(
        task="terminate-process",
        description="Identify a process and kill it on explicit confirmation.",
        steps=(
            ToolStep(
                tool="sm_process_list_processes",
                params=(),
                result=("processes",),
                refusals=(
                    Refusal(
                        "ACCESS_DENIED", "the credential lacks access to the operation"
                    ),
                    Refusal(
                        "INVALID_ARGUMENT", "the upstream system rejects the input"
                    ),
                ),
            ),
            ToolStep(
                tool="sm_process_get_process_info",
                params=("pid",),
                result=("pid", "name"),
                refusals=(
                    Refusal(
                        "ACCESS_DENIED", "the credential lacks access to the operation"
                    ),
                    Refusal(
                        "INVALID_ARGUMENT", "the upstream system rejects the input"
                    ),
                ),
            ),
            ToolStep(
                tool="sm_process_kill_process",
                params=("pid", "confirm"),
                result=("result",),
                refusals=(
                    Refusal(
                        "ACCESS_DENIED", "the credential lacks access to the operation"
                    ),
                    Refusal(
                        "INVALID_ARGUMENT", "the upstream system rejects the input"
                    ),
                    Refusal(
                        "CONFIRMATION_REQUIRED",
                        "the caller has not confirmed the destructive call",
                    ),
                ),
            ),
        ),
    ),
    ToolUseContract(
        task="diagnose-network",
        description="Read interfaces and open ports, then probe reachability and name resolution.",
        steps=(
            ToolStep(
                tool="sm_network_list_network_interfaces",
                params=(),
                result=("interfaces",),
                refusals=(
                    Refusal(
                        "ACCESS_DENIED", "the credential lacks access to the operation"
                    ),
                    Refusal(
                        "INVALID_ARGUMENT", "the upstream system rejects the input"
                    ),
                ),
            ),
            ToolStep(
                tool="sm_network_list_open_ports",
                params=(),
                result=("ports",),
                refusals=(
                    Refusal(
                        "ACCESS_DENIED", "the credential lacks access to the operation"
                    ),
                    Refusal(
                        "INVALID_ARGUMENT", "the upstream system rejects the input"
                    ),
                ),
            ),
            ToolStep(
                tool="sm_network_ping_host",
                params=("host", "count"),
                result=("reachable",),
                refusals=(
                    Refusal(
                        "ACCESS_DENIED", "the credential lacks access to the operation"
                    ),
                    Refusal(
                        "INVALID_ARGUMENT", "the upstream system rejects the input"
                    ),
                ),
            ),
            ToolStep(
                tool="sm_network_dns_lookup",
                params=("host",),
                result=("addresses",),
                refusals=(
                    Refusal(
                        "ACCESS_DENIED", "the credential lacks access to the operation"
                    ),
                    Refusal(
                        "INVALID_ARGUMENT", "the upstream system rejects the input"
                    ),
                ),
            ),
            ToolStep(
                tool="get_network_connections",
                params=(),
                result=("connections",),
                refusals=(
                    Refusal(
                        "ACCESS_DENIED", "the credential lacks access to the operation"
                    ),
                    Refusal(
                        "INVALID_ARGUMENT", "the upstream system rejects the input"
                    ),
                ),
            ),
        ),
    ),
    ToolUseContract(
        task="manage-firewall",
        description="Read the firewall status, add or remove a rule, and read it back.",
        steps=(
            ToolStep(
                tool="sm_firewall_get_firewall_status",
                params=(),
                result=("status", "rules"),
                refusals=(
                    Refusal(
                        "ACCESS_DENIED", "the credential lacks access to the operation"
                    ),
                    Refusal(
                        "INVALID_ARGUMENT", "the upstream system rejects the input"
                    ),
                ),
            ),
            ToolStep(
                tool="sm_firewall_add_firewall_rule",
                params=("rule", "confirm"),
                result=("result",),
                refusals=(
                    Refusal(
                        "ACCESS_DENIED", "the credential lacks access to the operation"
                    ),
                    Refusal(
                        "INVALID_ARGUMENT", "the upstream system rejects the input"
                    ),
                    Refusal(
                        "CONFIRMATION_REQUIRED",
                        "the caller has not confirmed the destructive call",
                    ),
                ),
            ),
            ToolStep(
                tool="sm_firewall_remove_firewall_rule",
                params=("rule", "confirm"),
                result=("result",),
                refusals=(
                    Refusal(
                        "ACCESS_DENIED", "the credential lacks access to the operation"
                    ),
                    Refusal(
                        "INVALID_ARGUMENT", "the upstream system rejects the input"
                    ),
                    Refusal(
                        "CONFIRMATION_REQUIRED",
                        "the caller has not confirmed the destructive call",
                    ),
                ),
            ),
        ),
    ),
    ToolUseContract(
        task="audit-accounts",
        description="List local users and groups.",
        steps=(
            ToolStep(
                tool="sm_user_list_users",
                params=(),
                result=("users",),
                refusals=(
                    Refusal(
                        "ACCESS_DENIED", "the credential lacks access to the operation"
                    ),
                    Refusal(
                        "INVALID_ARGUMENT", "the upstream system rejects the input"
                    ),
                ),
            ),
            ToolStep(
                tool="sm_user_list_groups",
                params=(),
                result=("groups",),
                refusals=(
                    Refusal(
                        "ACCESS_DENIED", "the credential lacks access to the operation"
                    ),
                    Refusal(
                        "INVALID_ARGUMENT", "the upstream system rejects the input"
                    ),
                ),
            ),
        ),
    ),
    ToolUseContract(
        task="manage-cron",
        description="List scheduled cron jobs and remove one.",
        steps=(
            ToolStep(
                tool="sm_cron_list_cron_jobs",
                params=("user",),
                result=("jobs",),
                refusals=(
                    Refusal(
                        "ACCESS_DENIED", "the credential lacks access to the operation"
                    ),
                    Refusal(
                        "INVALID_ARGUMENT", "the upstream system rejects the input"
                    ),
                ),
            ),
            ToolStep(
                tool="sm_cron_remove_cron_job",
                params=("job_ref", "user", "confirm"),
                result=("result",),
                refusals=(
                    Refusal(
                        "ACCESS_DENIED", "the credential lacks access to the operation"
                    ),
                    Refusal(
                        "INVALID_ARGUMENT", "the upstream system rejects the input"
                    ),
                    Refusal(
                        "CONFIRMATION_REQUIRED",
                        "the caller has not confirmed the destructive call",
                    ),
                ),
            ),
        ),
    ),
    ToolUseContract(
        task="review-disk-capacity",
        description="List disks and read usage and the space report.",
        steps=(
            ToolStep(
                tool="sm_disk_list_disks",
                params=(),
                result=("disks",),
                refusals=(
                    Refusal(
                        "ACCESS_DENIED", "the credential lacks access to the operation"
                    ),
                    Refusal(
                        "INVALID_ARGUMENT", "the upstream system rejects the input"
                    ),
                ),
            ),
            ToolStep(
                tool="sm_disk_get_disk_usage",
                params=("path",),
                result=("total", "used", "free"),
                refusals=(
                    Refusal(
                        "ACCESS_DENIED", "the credential lacks access to the operation"
                    ),
                    Refusal(
                        "INVALID_ARGUMENT", "the upstream system rejects the input"
                    ),
                ),
            ),
            ToolStep(
                tool="sm_disk_get_disk_space_report",
                params=(),
                result=("report",),
                refusals=(
                    Refusal(
                        "ACCESS_DENIED", "the credential lacks access to the operation"
                    ),
                    Refusal(
                        "INVALID_ARGUMENT", "the upstream system rejects the input"
                    ),
                ),
            ),
        ),
    ),
    ToolUseContract(
        task="check-storage-health",
        description="Read SMART, RAID and drive-fault state and the combined storage health report.",
        steps=(
            ToolStep(
                tool="sm_storage_health_report",
                params=(),
                result=("report",),
                refusals=(
                    Refusal(
                        "ACCESS_DENIED", "the credential lacks access to the operation"
                    ),
                    Refusal(
                        "INVALID_ARGUMENT", "the upstream system rejects the input"
                    ),
                ),
            ),
            ToolStep(
                tool="sm_storage_health_smart",
                params=(),
                result=("devices",),
                refusals=(
                    Refusal(
                        "ACCESS_DENIED", "the credential lacks access to the operation"
                    ),
                    Refusal(
                        "INVALID_ARGUMENT", "the upstream system rejects the input"
                    ),
                ),
            ),
            ToolStep(
                tool="sm_storage_health_raid",
                params=(),
                result=("arrays",),
                refusals=(
                    Refusal(
                        "ACCESS_DENIED", "the credential lacks access to the operation"
                    ),
                    Refusal(
                        "INVALID_ARGUMENT", "the upstream system rejects the input"
                    ),
                ),
            ),
            ToolStep(
                tool="sm_storage_health_faults",
                params=(),
                result=("faults",),
                refusals=(
                    Refusal(
                        "ACCESS_DENIED", "the credential lacks access to the operation"
                    ),
                    Refusal(
                        "INVALID_ARGUMENT", "the upstream system rejects the input"
                    ),
                ),
            ),
        ),
    ),
    ToolUseContract(
        task="browse-files",
        description="List, search and grep files under the managed filesystem root.",
        steps=(
            ToolStep(
                tool="sm_file_list_files",
                params=("filepath", "recursive", "depth"),
                result=("files",),
                refusals=(
                    Refusal(
                        "ACCESS_DENIED", "the credential lacks access to the operation"
                    ),
                    Refusal(
                        "INVALID_ARGUMENT", "the upstream system rejects the input"
                    ),
                ),
            ),
            ToolStep(
                tool="sm_file_search_files",
                params=("filepath", "pattern"),
                result=("matches",),
                refusals=(
                    Refusal(
                        "ACCESS_DENIED", "the credential lacks access to the operation"
                    ),
                    Refusal(
                        "INVALID_ARGUMENT", "the upstream system rejects the input"
                    ),
                ),
            ),
            ToolStep(
                tool="sm_file_grep_files",
                params=("filepath", "pattern", "recursive"),
                result=("matches",),
                refusals=(
                    Refusal(
                        "ACCESS_DENIED", "the credential lacks access to the operation"
                    ),
                    Refusal(
                        "INVALID_ARGUMENT", "the upstream system rejects the input"
                    ),
                ),
            ),
        ),
    ),
    ToolUseContract(
        task="edit-managed-file",
        description="Read a managed file, then create, update or delete it on confirmation.",
        steps=(
            ToolStep(
                tool="sm_file_list_files",
                params=("filepath", "recursive", "depth"),
                result=("files",),
                refusals=(
                    Refusal(
                        "ACCESS_DENIED", "the credential lacks access to the operation"
                    ),
                    Refusal(
                        "INVALID_ARGUMENT", "the upstream system rejects the input"
                    ),
                ),
            ),
            ToolStep(
                tool="sm_file_manage_file",
                params=("filepath", "content", "file_action", "confirm"),
                result=("success",),
                refusals=(
                    Refusal(
                        "ACCESS_DENIED", "the credential lacks access to the operation"
                    ),
                    Refusal(
                        "INVALID_ARGUMENT", "the upstream system rejects the input"
                    ),
                    Refusal(
                        "CONFIRMATION_REQUIRED",
                        "the caller has not confirmed the destructive call",
                    ),
                ),
            ),
        ),
    ),
    ToolUseContract(
        task="install-software",
        description="Find a package, read it, add a repository and install or update software.",
        steps=(
            ToolStep(
                tool="sm_system_search_package",
                params=("package",),
                result=("packages",),
                refusals=(
                    Refusal(
                        "ACCESS_DENIED", "the credential lacks access to the operation"
                    ),
                    Refusal(
                        "INVALID_ARGUMENT", "the upstream system rejects the input"
                    ),
                ),
            ),
            ToolStep(
                tool="sm_system_get_package_info",
                params=("package",),
                result=("name", "version"),
                refusals=(
                    Refusal(
                        "ACCESS_DENIED", "the credential lacks access to the operation"
                    ),
                    Refusal(
                        "INVALID_ARGUMENT", "the upstream system rejects the input"
                    ),
                ),
            ),
            ToolStep(
                tool="sm_system_list_installed_packages",
                params=(),
                result=("packages",),
                refusals=(
                    Refusal(
                        "ACCESS_DENIED", "the credential lacks access to the operation"
                    ),
                    Refusal(
                        "INVALID_ARGUMENT", "the upstream system rejects the input"
                    ),
                ),
            ),
            ToolStep(
                tool="sm_system_list_upgradable_packages",
                params=(),
                result=("packages",),
                refusals=(
                    Refusal(
                        "ACCESS_DENIED", "the credential lacks access to the operation"
                    ),
                    Refusal(
                        "INVALID_ARGUMENT", "the upstream system rejects the input"
                    ),
                ),
            ),
            ToolStep(
                tool="sm_system_add_repository",
                params=("repository", "confirm"),
                result=("result",),
                refusals=(
                    Refusal(
                        "ACCESS_DENIED", "the credential lacks access to the operation"
                    ),
                    Refusal(
                        "INVALID_ARGUMENT", "the upstream system rejects the input"
                    ),
                    Refusal(
                        "CONFIRMATION_REQUIRED",
                        "the caller has not confirmed the destructive call",
                    ),
                ),
            ),
            ToolStep(
                tool="sm_system_install_applications",
                params=("packages", "confirm"),
                result=("result",),
                refusals=(
                    Refusal(
                        "ACCESS_DENIED", "the credential lacks access to the operation"
                    ),
                    Refusal(
                        "INVALID_ARGUMENT", "the upstream system rejects the input"
                    ),
                    Refusal(
                        "CONFIRMATION_REQUIRED",
                        "the caller has not confirmed the destructive call",
                    ),
                ),
            ),
            ToolStep(
                tool="sm_system_install_local_package",
                params=("file_path", "confirm"),
                result=("result",),
                refusals=(
                    Refusal(
                        "ACCESS_DENIED", "the credential lacks access to the operation"
                    ),
                    Refusal(
                        "INVALID_ARGUMENT", "the upstream system rejects the input"
                    ),
                    Refusal(
                        "CONFIRMATION_REQUIRED",
                        "the caller has not confirmed the destructive call",
                    ),
                ),
            ),
            ToolStep(
                tool="sm_system_update",
                params=("confirm",),
                result=("result",),
                refusals=(
                    Refusal(
                        "ACCESS_DENIED", "the credential lacks access to the operation"
                    ),
                    Refusal(
                        "INVALID_ARGUMENT", "the upstream system rejects the input"
                    ),
                    Refusal(
                        "CONFIRMATION_REQUIRED",
                        "the caller has not confirmed the destructive call",
                    ),
                ),
            ),
        ),
    ),
    ToolUseContract(
        task="clean-and-optimize-host",
        description="Clean packages, caches and temporary files, or optimize the host.",
        steps=(
            ToolStep(
                tool="sm_disk_get_disk_usage",
                params=("path",),
                result=("total", "used", "free"),
                refusals=(
                    Refusal(
                        "ACCESS_DENIED", "the credential lacks access to the operation"
                    ),
                    Refusal(
                        "INVALID_ARGUMENT", "the upstream system rejects the input"
                    ),
                ),
            ),
            ToolStep(
                tool="sm_system_clean",
                params=("confirm",),
                result=("result",),
                refusals=(
                    Refusal(
                        "ACCESS_DENIED", "the credential lacks access to the operation"
                    ),
                    Refusal(
                        "INVALID_ARGUMENT", "the upstream system rejects the input"
                    ),
                    Refusal(
                        "CONFIRMATION_REQUIRED",
                        "the caller has not confirmed the destructive call",
                    ),
                ),
            ),
            ToolStep(
                tool="sm_system_clean_package_cache",
                params=("confirm",),
                result=("result",),
                refusals=(
                    Refusal(
                        "ACCESS_DENIED", "the credential lacks access to the operation"
                    ),
                    Refusal(
                        "INVALID_ARGUMENT", "the upstream system rejects the input"
                    ),
                    Refusal(
                        "CONFIRMATION_REQUIRED",
                        "the caller has not confirmed the destructive call",
                    ),
                ),
            ),
            ToolStep(
                tool="sm_system_clean_temp_files",
                params=("confirm",),
                result=("result",),
                refusals=(
                    Refusal(
                        "ACCESS_DENIED", "the credential lacks access to the operation"
                    ),
                    Refusal(
                        "INVALID_ARGUMENT", "the upstream system rejects the input"
                    ),
                    Refusal(
                        "CONFIRMATION_REQUIRED",
                        "the caller has not confirmed the destructive call",
                    ),
                ),
            ),
            ToolStep(
                tool="sm_system_optimize",
                params=("confirm",),
                result=("result",),
                refusals=(
                    Refusal(
                        "ACCESS_DENIED", "the credential lacks access to the operation"
                    ),
                    Refusal(
                        "INVALID_ARGUMENT", "the upstream system rejects the input"
                    ),
                    Refusal(
                        "CONFIRMATION_REQUIRED",
                        "the caller has not confirmed the destructive call",
                    ),
                ),
            ),
        ),
    ),
    ToolUseContract(
        task="reboot-host",
        description="Check uptime and running services, then reboot the host on confirmation.",
        steps=(
            ToolStep(
                tool="sm_system_get_uptime",
                params=(),
                result=("uptime",),
                refusals=(
                    Refusal(
                        "ACCESS_DENIED", "the credential lacks access to the operation"
                    ),
                    Refusal(
                        "INVALID_ARGUMENT", "the upstream system rejects the input"
                    ),
                ),
            ),
            ToolStep(
                tool="sm_service_list_services",
                params=(),
                result=("services",),
                refusals=(
                    Refusal(
                        "ACCESS_DENIED", "the credential lacks access to the operation"
                    ),
                    Refusal(
                        "INVALID_ARGUMENT", "the upstream system rejects the input"
                    ),
                ),
            ),
            ToolStep(
                tool="sm_system_reboot",
                params=("confirm",),
                result=("result",),
                refusals=(
                    Refusal(
                        "ACCESS_DENIED", "the credential lacks access to the operation"
                    ),
                    Refusal(
                        "INVALID_ARGUMENT", "the upstream system rejects the input"
                    ),
                    Refusal(
                        "CONFIRMATION_REQUIRED",
                        "the caller has not confirmed the destructive call",
                    ),
                ),
            ),
        ),
    ),
    ToolUseContract(
        task="manage-environment",
        description="Read environment variables and install Python modules.",
        steps=(
            ToolStep(
                tool="sm_system_list_env_vars",
                params=(),
                result=("variables",),
                refusals=(
                    Refusal(
                        "ACCESS_DENIED", "the credential lacks access to the operation"
                    ),
                    Refusal(
                        "INVALID_ARGUMENT", "the upstream system rejects the input"
                    ),
                ),
            ),
            ToolStep(
                tool="sm_system_get_env_var",
                params=("env_var",),
                result=("name", "value"),
                refusals=(
                    Refusal(
                        "ACCESS_DENIED", "the credential lacks access to the operation"
                    ),
                    Refusal(
                        "INVALID_ARGUMENT", "the upstream system rejects the input"
                    ),
                ),
            ),
            ToolStep(
                tool="sm_system_install_python_modules",
                params=("packages", "confirm"),
                result=("result",),
                refusals=(
                    Refusal(
                        "ACCESS_DENIED", "the credential lacks access to the operation"
                    ),
                    Refusal(
                        "INVALID_ARGUMENT", "the upstream system rejects the input"
                    ),
                    Refusal(
                        "CONFIRMATION_REQUIRED",
                        "the caller has not confirmed the destructive call",
                    ),
                ),
            ),
        ),
    ),
    ToolUseContract(
        task="manage-windows-features",
        description="List, enable and disable Windows optional features.",
        steps=(
            ToolStep(
                tool="sm_system_list_windows_features",
                params=(),
                result=("features",),
                refusals=(
                    Refusal(
                        "ACCESS_DENIED", "the credential lacks access to the operation"
                    ),
                    Refusal(
                        "INVALID_ARGUMENT", "the upstream system rejects the input"
                    ),
                ),
            ),
            ToolStep(
                tool="sm_system_enable_windows_features",
                params=("feature_name", "confirm"),
                result=("result",),
                refusals=(
                    Refusal(
                        "ACCESS_DENIED", "the credential lacks access to the operation"
                    ),
                    Refusal(
                        "INVALID_ARGUMENT", "the upstream system rejects the input"
                    ),
                    Refusal(
                        "CONFIRMATION_REQUIRED",
                        "the caller has not confirmed the destructive call",
                    ),
                ),
            ),
            ToolStep(
                tool="sm_system_disable_windows_features",
                params=("feature_name", "confirm"),
                result=("result",),
                refusals=(
                    Refusal(
                        "ACCESS_DENIED", "the credential lacks access to the operation"
                    ),
                    Refusal(
                        "INVALID_ARGUMENT", "the upstream system rejects the input"
                    ),
                    Refusal(
                        "CONFIRMATION_REQUIRED",
                        "the caller has not confirmed the destructive call",
                    ),
                ),
            ),
        ),
    ),
    ToolUseContract(
        task="provision-dev-runtime",
        description="Install uv, nvm and Node, create virtual environments and install packages for a user.",
        steps=(
            ToolStep(
                tool="sm_advanced_install_uv",
                params=("confirm",),
                result=("result",),
                refusals=(
                    Refusal(
                        "ACCESS_DENIED", "the credential lacks access to the operation"
                    ),
                    Refusal(
                        "INVALID_ARGUMENT", "the upstream system rejects the input"
                    ),
                    Refusal(
                        "CONFIRMATION_REQUIRED",
                        "the caller has not confirmed the destructive call",
                    ),
                ),
            ),
            ToolStep(
                tool="sm_advanced_install_nvm",
                params=("confirm",),
                result=("result",),
                refusals=(
                    Refusal(
                        "ACCESS_DENIED", "the credential lacks access to the operation"
                    ),
                    Refusal(
                        "INVALID_ARGUMENT", "the upstream system rejects the input"
                    ),
                    Refusal(
                        "CONFIRMATION_REQUIRED",
                        "the caller has not confirmed the destructive call",
                    ),
                ),
            ),
            ToolStep(
                tool="sm_advanced_install_node",
                params=("version", "confirm"),
                result=("result",),
                refusals=(
                    Refusal(
                        "ACCESS_DENIED", "the credential lacks access to the operation"
                    ),
                    Refusal(
                        "INVALID_ARGUMENT", "the upstream system rejects the input"
                    ),
                    Refusal(
                        "CONFIRMATION_REQUIRED",
                        "the caller has not confirmed the destructive call",
                    ),
                ),
            ),
            ToolStep(
                tool="sm_advanced_use_node",
                params=("version", "confirm"),
                result=("result",),
                refusals=(
                    Refusal(
                        "ACCESS_DENIED", "the credential lacks access to the operation"
                    ),
                    Refusal(
                        "INVALID_ARGUMENT", "the upstream system rejects the input"
                    ),
                    Refusal(
                        "CONFIRMATION_REQUIRED",
                        "the caller has not confirmed the destructive call",
                    ),
                ),
            ),
            ToolStep(
                tool="sm_advanced_create_venv",
                params=("path", "version", "confirm"),
                result=("result",),
                refusals=(
                    Refusal(
                        "ACCESS_DENIED", "the credential lacks access to the operation"
                    ),
                    Refusal(
                        "INVALID_ARGUMENT", "the upstream system rejects the input"
                    ),
                    Refusal(
                        "CONFIRMATION_REQUIRED",
                        "the caller has not confirmed the destructive call",
                    ),
                ),
            ),
            ToolStep(
                tool="sm_advanced_install_package",
                params=("path", "package", "confirm"),
                result=("result",),
                refusals=(
                    Refusal(
                        "ACCESS_DENIED", "the credential lacks access to the operation"
                    ),
                    Refusal(
                        "INVALID_ARGUMENT", "the upstream system rejects the input"
                    ),
                    Refusal(
                        "CONFIRMATION_REQUIRED",
                        "the caller has not confirmed the destructive call",
                    ),
                ),
            ),
            ToolStep(
                tool="sm_advanced_add_authorized_key",
                params=("public_key", "confirm"),
                result=("result",),
                refusals=(
                    Refusal(
                        "ACCESS_DENIED", "the credential lacks access to the operation"
                    ),
                    Refusal(
                        "INVALID_ARGUMENT", "the upstream system rejects the input"
                    ),
                    Refusal(
                        "CONFIRMATION_REQUIRED",
                        "the caller has not confirmed the destructive call",
                    ),
                ),
            ),
        ),
    ),
)

LINKS = (
    SurfaceLink(
        task="assess-host-health",
        tools=(
            "health_check",
            "get_management_capabilities",
            "sm_system_get_uptime",
            "sm_system_get_host_record",
            "sm_system_get_os_statistics",
            "sm_system_get_hardware_statistics",
            "sm_system_system_health_check",
            "capture_system_snapshot",
        ),
        prompts=("systems-manager-operator", "systems-manager-host-observer"),
        skills=("sm-host-inspection", "systems-manager-operations"),
    ),
    SurfaceLink(
        task="ingest-host-graph",
        tools=(
            "get_management_capabilities",
            "capture_system_snapshot",
            "systems_ingest_host",
        ),
        prompts=("systems-manager-operator", "systems-manager-host-observer"),
        skills=("sm-host-inspection", "systems-manager-operations"),
    ),
    SurfaceLink(
        task="investigate-logs",
        tools=(
            "query_system_logs",
            "sm_file_get_system_logs",
            "sm_file_tail_log_file",
            "list_kernel_modules",
        ),
        prompts=("systems-manager-operator", "systems-manager-host-observer"),
        skills=("sm-host-inspection", "sm-storage-and-files"),
    ),
    SurfaceLink(
        task="trace-system-activity",
        tools=("start_system_trace", "query_system_logs", "stop_system_trace"),
        prompts=("systems-manager-operator", "systems-manager-host-observer"),
        skills=("sm-host-inspection",),
    ),
    SurfaceLink(
        task="inspect-services",
        tools=(
            "list_services",
            "sm_service_list_services",
            "sm_service_get_service_status",
        ),
        prompts=("systems-manager-operator", "systems-manager-host-observer"),
        skills=("sm-service-process-control", "systems-manager-operations"),
    ),
    SurfaceLink(
        task="control-service",
        tools=(
            "sm_service_get_service_status",
            "sm_service_start_service",
            "sm_service_stop_service",
            "sm_service_restart_service",
            "sm_service_enable_service",
            "sm_service_disable_service",
        ),
        prompts=("systems-manager-operator", "systems-manager-host-administrator"),
        skills=("sm-service-process-control", "systems-manager-operations"),
    ),
    SurfaceLink(
        task="control-service-by-provider",
        tools=(
            "list_services",
            "manage_service_start",
            "manage_service_stop",
            "manage_service_restart",
            "manage_service_enable",
            "manage_service_disable",
        ),
        prompts=("systems-manager-operator", "systems-manager-host-administrator"),
        skills=("sm-service-process-control",),
    ),
    SurfaceLink(
        task="inspect-processes",
        tools=(
            "sm_process_list_processes",
            "sm_process_get_process_info",
            "get_process_details",
            "get_network_connections",
        ),
        prompts=("systems-manager-operator", "systems-manager-host-observer"),
        skills=("sm-service-process-control",),
    ),
    SurfaceLink(
        task="terminate-process",
        tools=(
            "sm_process_list_processes",
            "sm_process_get_process_info",
            "sm_process_kill_process",
        ),
        prompts=("systems-manager-operator", "systems-manager-host-administrator"),
        skills=("sm-service-process-control",),
    ),
    SurfaceLink(
        task="diagnose-network",
        tools=(
            "sm_network_list_network_interfaces",
            "sm_network_list_open_ports",
            "sm_network_ping_host",
            "sm_network_dns_lookup",
            "get_network_connections",
        ),
        prompts=("systems-manager-operator", "systems-manager-host-observer"),
        skills=("sm-network-and-accounts", "nic-bond-provisioner"),
    ),
    SurfaceLink(
        task="manage-firewall",
        tools=(
            "sm_firewall_get_firewall_status",
            "sm_firewall_add_firewall_rule",
            "sm_firewall_remove_firewall_rule",
        ),
        prompts=("systems-manager-operator", "systems-manager-host-administrator"),
        skills=("sm-network-and-accounts",),
    ),
    SurfaceLink(
        task="audit-accounts",
        tools=("sm_user_list_users", "sm_user_list_groups"),
        prompts=("systems-manager-operator", "systems-manager-host-observer"),
        skills=("sm-network-and-accounts",),
    ),
    SurfaceLink(
        task="manage-cron",
        tools=("sm_cron_list_cron_jobs", "sm_cron_remove_cron_job"),
        prompts=("systems-manager-operator", "systems-manager-host-administrator"),
        skills=("sm-network-and-accounts",),
    ),
    SurfaceLink(
        task="review-disk-capacity",
        tools=(
            "sm_disk_list_disks",
            "sm_disk_get_disk_usage",
            "sm_disk_get_disk_space_report",
        ),
        prompts=("systems-manager-operator", "systems-manager-host-observer"),
        skills=("sm-storage-and-files",),
    ),
    SurfaceLink(
        task="check-storage-health",
        tools=(
            "sm_storage_health_report",
            "sm_storage_health_smart",
            "sm_storage_health_raid",
            "sm_storage_health_faults",
        ),
        prompts=("systems-manager-operator", "systems-manager-host-observer"),
        skills=("sm-storage-and-files", "ipmi-bmc-manager"),
    ),
    SurfaceLink(
        task="browse-files",
        tools=("sm_file_list_files", "sm_file_search_files", "sm_file_grep_files"),
        prompts=("systems-manager-operator", "systems-manager-host-observer"),
        skills=("sm-storage-and-files",),
    ),
    SurfaceLink(
        task="edit-managed-file",
        tools=("sm_file_list_files", "sm_file_manage_file"),
        prompts=("systems-manager-operator", "systems-manager-host-administrator"),
        skills=("sm-storage-and-files", "systems-manager-operations"),
    ),
    SurfaceLink(
        task="install-software",
        tools=(
            "sm_system_search_package",
            "sm_system_get_package_info",
            "sm_system_list_installed_packages",
            "sm_system_list_upgradable_packages",
            "sm_system_add_repository",
            "sm_system_install_applications",
            "sm_system_install_local_package",
            "sm_system_update",
        ),
        prompts=("systems-manager-operator", "systems-manager-host-administrator"),
        skills=("sm-packages-and-maintenance",),
    ),
    SurfaceLink(
        task="clean-and-optimize-host",
        tools=(
            "sm_disk_get_disk_usage",
            "sm_system_clean",
            "sm_system_clean_package_cache",
            "sm_system_clean_temp_files",
            "sm_system_optimize",
        ),
        prompts=("systems-manager-operator", "systems-manager-host-administrator"),
        skills=("sm-packages-and-maintenance",),
    ),
    SurfaceLink(
        task="reboot-host",
        tools=("sm_system_get_uptime", "sm_service_list_services", "sm_system_reboot"),
        prompts=("systems-manager-operator", "systems-manager-host-administrator"),
        skills=("sm-packages-and-maintenance",),
    ),
    SurfaceLink(
        task="manage-environment",
        tools=(
            "sm_system_list_env_vars",
            "sm_system_get_env_var",
            "sm_system_install_python_modules",
        ),
        prompts=("systems-manager-operator", "systems-manager-host-administrator"),
        skills=("sm-packages-and-maintenance",),
    ),
    SurfaceLink(
        task="manage-windows-features",
        tools=(
            "sm_system_list_windows_features",
            "sm_system_enable_windows_features",
            "sm_system_disable_windows_features",
        ),
        prompts=("systems-manager-operator", "systems-manager-host-administrator"),
        skills=("sm-packages-and-maintenance",),
    ),
    SurfaceLink(
        task="provision-dev-runtime",
        tools=(
            "sm_advanced_install_uv",
            "sm_advanced_install_nvm",
            "sm_advanced_install_node",
            "sm_advanced_use_node",
            "sm_advanced_create_venv",
            "sm_advanced_install_package",
            "sm_advanced_add_authorized_key",
        ),
        prompts=("systems-manager-operator", "systems-manager-host-administrator"),
        skills=("sm-runtime-provisioning",),
    ),
)

LOCATIONS = (
    DataLocation(
        name="host-state",
        holds=("HardwareNode", "NetworkInterface"),
        instance="SYSTEMS_MANAGER_NODE_REF",
        read_tool="sm_system_get_hardware_statistics",
        federation_key="externalToolId",
    ),
    DataLocation(
        name="host-services",
        holds=("SystemService", "SoftwarePackage"),
        instance="SYSTEMS_MANAGER_NODE_REF",
        read_tool="sm_service_list_services",
        federation_key="externalToolId",
    ),
    DataLocation(
        name="host-storage",
        holds=("DiskVolume",),
        instance="SYSTEMS_MANAGER_NODE_REF",
        read_tool="sm_disk_list_disks",
        federation_key="externalToolId",
    ),
)

ROLES = (
    BusinessRole(
        name="host administrator",
        description="Change services, software, files, firewall rules and scheduled jobs on managed hosts on request.",
        tasks=(
            "control-service",
            "control-service-by-provider",
            "terminate-process",
            "manage-firewall",
            "manage-cron",
            "edit-managed-file",
            "install-software",
            "clean-and-optimize-host",
            "reboot-host",
            "manage-environment",
            "manage-windows-features",
            "provision-dev-runtime",
        ),
    ),
    BusinessRole(
        name="host observer",
        description="Report host health, capacity, services, processes, network and accounts without changing anything.",
        tasks=(
            "assess-host-health",
            "ingest-host-graph",
            "investigate-logs",
            "trace-system-activity",
            "inspect-services",
            "inspect-processes",
            "diagnose-network",
            "audit-accounts",
            "review-disk-capacity",
            "check-storage-health",
            "browse-files",
        ),
    ),
)
