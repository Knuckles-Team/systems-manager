import abc
import json
import logging
import platform
import subprocess
from typing import Any

import psutil

logger = logging.getLogger(__name__)


class OSProvider(abc.ABC):
    """
    Abstract base class for OS-specific system operations.

    CONCEPT:SYS-1.0: Abstracted OS Provider
    CONCEPT:SYS-1.2: Deep Introspection Telemetry
    """

    def get_process_details(self, pid: int | None = None) -> list[dict[str, Any]]:
        """Cross-platform process details using psutil."""
        processes = []
        attrs = [
            "pid",
            "name",
            "username",
            "status",
            "cpu_percent",
            "memory_info",
            "cmdline",
            "create_time",
        ]

        if pid is not None:
            try:
                p = psutil.Process(pid)
                processes.append(p.as_dict(attrs=attrs))
            except psutil.NoSuchProcess:
                pass
        else:
            for p in psutil.process_iter(attrs):
                processes.append(p.info)
        return processes

    def get_network_connections(self) -> list[dict[str, Any]]:
        """Cross-platform network connections mapping to processes."""
        connections = []

        def format_addr(addr):
            if not addr:
                return None
            if isinstance(addr, str):
                return addr
            if hasattr(addr, "ip") and hasattr(addr, "port"):
                return f"{addr.ip}:{addr.port}"
            return str(addr)

        try:
            for conn in psutil.net_connections(kind="all"):
                connections.append(
                    {
                        "fd": conn.fd,
                        "family": (
                            conn.family.name
                            if hasattr(conn.family, "name")
                            else conn.family
                        ),
                        "type": (
                            conn.type.name if hasattr(conn.type, "name") else conn.type
                        ),
                        "laddr": format_addr(conn.laddr),
                        "raddr": format_addr(conn.raddr),
                        "status": conn.status,
                        "pid": conn.pid,
                    }
                )
        except psutil.AccessDenied:
            logger.warning(
                "Access denied when fetching network connections. Try running as admin/root."
            )
        return connections

    def capture_system_snapshot(self) -> dict[str, Any]:
        """Take a point-in-time snapshot of the system state."""
        return {
            "cpu_percent": psutil.cpu_percent(interval=1),
            "memory": psutil.virtual_memory()._asdict(),
            "disk": psutil.disk_usage("/")._asdict(),
            "processes_count": len(psutil.pids()),
            "users": [u.name for u in psutil.users()],
            "boot_time": psutil.boot_time(),
        }

    @abc.abstractmethod
    def list_services(self) -> list[dict[str, Any]]:
        pass

    @abc.abstractmethod
    def manage_service(self, service_name: str, action: str) -> dict[str, Any]:
        pass

    @abc.abstractmethod
    def list_kernel_modules(self) -> list[dict[str, Any]]:
        pass

    @abc.abstractmethod
    def query_system_logs(self, limit: int = 50) -> list[dict[str, Any]]:
        pass

    @abc.abstractmethod
    def start_system_trace(self, session_name: str) -> dict[str, Any]:
        pass

    @abc.abstractmethod
    def stop_system_trace(self, session_name: str) -> dict[str, Any]:
        pass


class LinuxProvider(OSProvider):
    """
    Linux-specific implementation of the OSProvider.

    CONCEPT:SYS-1.0: Abstracted OS Provider
    CONCEPT:SYS-1.2: Deep Introspection Telemetry
    """

    def list_services(self) -> list[dict[str, Any]]:
        try:
            # list-units is reliable across systemd systems
            cmd = ["systemctl", "list-units", "--type=service", "--all", "--no-pager"]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            services = []
            for line in result.stdout.splitlines():
                if ".service" in line:
                    parts = line.split()
                    if len(parts) >= 4:
                        services.append(
                            {
                                "name": parts[0],
                                "load": parts[1],
                                "active": parts[2],
                                "sub": parts[3],
                                "description": " ".join(parts[4:]),
                            }
                        )
            return services
        except Exception as e:
            return [{"error": f"Failed to list services: {e}"}]

    def manage_service(self, service_name: str, action: str) -> dict[str, Any]:
        try:
            cmd = ["sudo", "systemctl", action, service_name]
            result = subprocess.run(cmd, capture_output=True, text=True)
            return {
                "success": result.returncode == 0,
                "action": action,
                "service": service_name,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def list_kernel_modules(self) -> list[dict[str, Any]]:
        try:
            cmd = ["lsmod"]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            modules = []
            for line in result.stdout.splitlines()[1:]:  # skip header
                parts = line.split()
                if len(parts) >= 3:
                    modules.append(
                        {"name": parts[0], "size": parts[1], "used_by": parts[2]}
                    )
            return modules
        except Exception as e:
            return [{"error": f"Failed to list kernel modules: {e}"}]

    def query_system_logs(self, limit: int = 50) -> list[dict[str, Any]]:
        try:
            cmd = ["journalctl", "-n", str(limit), "-o", "json"]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            logs = []
            for line in result.stdout.splitlines():
                if line.strip():
                    logs.append(json.loads(line))
            return logs
        except Exception as e:
            return [{"error": f"Failed to query system logs: {e}"}]

    def start_system_trace(self, session_name: str) -> dict[str, Any]:
        return {
            "success": False,
            "error": "System tracing (eBPF) requires manual tool execution on Linux currently.",
        }

    def stop_system_trace(self, session_name: str) -> dict[str, Any]:
        return {
            "success": False,
            "error": "System tracing (eBPF) requires manual tool execution on Linux currently.",
        }


class WindowsProvider(OSProvider):
    """
    Windows-specific implementation of the OSProvider.

    CONCEPT:SYS-1.0: Abstracted OS Provider
    CONCEPT:SYS-1.2: Deep Introspection Telemetry
    """

    def _run_powershell_json(self, command: str) -> Any:
        try:
            cmd = [
                "powershell",
                "-NoProfile",
                "-Command",
                f"{command} | ConvertTo-Json -Depth 2",
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return json.loads(result.stdout) if result.stdout.strip() else []
        except Exception as e:
            return {"error": str(e)}

    def list_services(self) -> list[dict[str, Any]]:
        command = "Get-Service | Select-Object Name, DisplayName, Status, StartType"
        res = self._run_powershell_json(command)
        if isinstance(res, list):
            return res
        elif isinstance(res, dict) and "error" not in res:
            return [res]  # single item
        return [res]

    def manage_service(self, service_name: str, action: str) -> dict[str, Any]:
        # map common systemd actions to powershell
        action_map = {
            "start": "Start-Service",
            "stop": "Stop-Service",
            "restart": "Restart-Service",
            "suspend": "Suspend-Service",
            "resume": "Resume-Service",
        }
        ps_action = action_map.get(action.lower(), "Start-Service")
        try:
            cmd = ["powershell", "-Command", f"{ps_action} -Name {service_name}"]
            result = subprocess.run(cmd, capture_output=True, text=True)
            return {
                "success": result.returncode == 0,
                "action": action,
                "service": service_name,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def list_kernel_modules(self) -> list[dict[str, Any]]:
        # Using driverquery on Windows
        try:
            cmd = ["driverquery", "/FO", "CSV"]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            lines = result.stdout.splitlines()
            if len(lines) < 2:
                return []
            import csv

            reader = csv.DictReader(lines)
            return [row for row in reader]
        except Exception as e:
            return [{"error": f"Failed to list drivers: {e}"}]

    def query_system_logs(self, limit: int = 50) -> list[dict[str, Any]]:
        command = f"Get-WinEvent -LogName System,Security,Application -MaxEvents {limit} -ErrorAction SilentlyContinue | Select-Object TimeCreated, Id, LevelDisplayName, Message, ProviderName"
        res = self._run_powershell_json(command)
        if isinstance(res, list):
            return res
        elif isinstance(res, dict) and "error" not in res:
            return [res]
        return [res]

    def start_system_trace(self, session_name: str) -> dict[str, Any]:
        try:
            # basic logman start
            cmd = [
                "logman",
                "start",
                session_name,
                "-p",
                "Microsoft-Windows-Kernel-Process",
                "-ets",
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            return {
                "success": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def stop_system_trace(self, session_name: str) -> dict[str, Any]:
        try:
            cmd = ["logman", "stop", session_name, "-ets"]
            result = subprocess.run(cmd, capture_output=True, text=True)
            return {
                "success": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}


def get_os_provider() -> OSProvider:
    system = platform.system().lower()
    if system == "windows":
        return WindowsProvider()
    elif system in ["linux", "darwin"]:  # fallback mac to linux for now
        return LinuxProvider()
    else:
        return LinuxProvider()
