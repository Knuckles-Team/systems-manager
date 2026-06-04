#!/usr/bin/env python
import argparse
import glob
import json
import logging
import os
import platform
import shutil
import socket
import subprocess
import sys
import tempfile
import zipfile
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

import distro
import psutil
import requests

from systems_manager.models import (
    CommandResult,
    SystemStats,
)

__version__ = "1.26.0"


def setup_logging(
    _is_mcp_server: bool = False, log_file: str = "systems_manager_mcp.log"
):
    if not log_file:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        log_file = os.path.join(script_dir, "systems_manager.log")
    logging.basicConfig(
        filename=log_file,
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )
    logger = logging.getLogger(__name__)
    logger.info(f"MCP server logging initialized to {log_file}")
    return logger


class FileSystemManager:
    def __init__(self, manager):
        self.manager = manager
        self.logger = manager.logger

    def list_files(
        self, path: str = ".", recursive: bool = False, depth: int = 1
    ) -> CommandResult:
        try:
            expanded_path = os.path.abspath(os.path.expanduser(path))
            if not os.path.exists(expanded_path):
                return CommandResult(
                    **{"success": False, "error": f"Path not found: {path}"}
                )

            items = []
            if recursive:
                for root, dirs, files in os.walk(expanded_path):
                    current_depth = root[len(expanded_path) :].count(os.sep)
                    if current_depth >= depth:
                        continue
                    for name in dirs:
                        items.append(
                            {
                                "name": name,
                                "type": "directory",
                                "path": os.path.join(root, name),
                            }
                        )
                    for name in files:
                        items.append(
                            {
                                "name": name,
                                "type": "file",
                                "path": os.path.join(root, name),
                            }
                        )
            else:
                for entry in os.scandir(expanded_path):
                    items.append(
                        {
                            "name": entry.name,
                            "type": "directory" if entry.is_dir() else "file",
                            "path": entry.path,
                        }
                    )
            return CommandResult(
                **{
                    "success": True,
                    "path": expanded_path,
                    "items": items,
                    "total": len(items),
                }
            )
        except Exception as e:
            return CommandResult(**{"success": False, "error": str(e)})

    def search_files(self, path: str, pattern: str) -> CommandResult:
        try:
            expanded_path = os.path.abspath(os.path.expanduser(path))
            matches = []
            for root, _, files in os.walk(expanded_path):
                for name in files:
                    if pattern in name:
                        matches.append(os.path.join(root, name))
            return CommandResult(
                **{"success": True, "matches": matches, "total": len(matches)}
            )
        except Exception as e:
            return CommandResult(**{"success": False, "error": str(e)})

    def grep_files(
        self, path: str, pattern: str, recursive: bool = False
    ) -> CommandResult:
        try:
            cmd = ["grep", "-rn" if recursive else "-n", pattern, path]
            result = self.manager.run_command(cmd)
            return CommandResult(
                **{
                    "success": result["success"],
                    "matches": result.get("stdout", ""),
                    "path": path,
                }
            )
        except Exception as e:
            return CommandResult(**{"success": False, "error": str(e)})

    def manage_file(
        self, action: str, path: str, content: str | None = None
    ) -> CommandResult:
        try:
            expanded_path = os.path.abspath(os.path.expanduser(path))
            if action == "create" or action == "update":
                os.makedirs(os.path.dirname(expanded_path), exist_ok=True)
                with open(expanded_path, "w") as f:
                    f.write(content or "")
                return CommandResult(
                    **{"success": True, "message": f"File {action}d: {path}"}
                )
            elif action == "delete":
                if os.path.exists(expanded_path):
                    os.remove(expanded_path)
                    return CommandResult(
                        **{"success": True, "message": f"File deleted: {path}"}
                    )
                return CommandResult(
                    **{"success": False, "error": f"File not found: {path}"}
                )
            elif action == "read":
                if os.path.exists(expanded_path):
                    with open(expanded_path) as f:
                        return CommandResult(**{"success": True, "content": f.read()})
                return CommandResult(
                    **{"success": False, "error": f"File not found: {path}"}
                )
            else:
                return CommandResult(
                    **{"success": False, "error": f"Unknown action: {action}"}
                )
        except Exception as e:
            return CommandResult(**{"success": False, "error": str(e)})


class ShellProfileManager:
    def __init__(self, manager):
        self.manager = manager

    def get_profile_path(self, shell: str = "bash") -> str:
        home = os.path.expanduser("~")
        if shell == "bash":
            return os.path.join(home, ".bashrc")
        elif shell == "zsh":
            return os.path.join(home, ".zshrc")
        elif shell == "fish":
            return os.path.join(home, ".config/fish/config.fish")
        elif platform.system() == "Windows":
            return os.path.join(
                home,
                "Documents",
                "WindowsPowerShell",
                "Microsoft.PowerShell_profile.ps1",
            )
        return os.path.join(home, ".profile")

    def add_alias(self, name: str, command: str, shell: str = "bash") -> CommandResult:
        try:
            profile_path = self.get_profile_path(shell)
            alias_cmd = f'alias {name}="{command}"'

            if platform.system() == "Windows":
                alias_cmd = f"function {name} {{ {command} }}"

            if os.path.exists(profile_path):
                with open(profile_path) as f:
                    if alias_cmd in f.read():
                        return CommandResult(
                            **{"success": True, "message": "Alias already exists"}
                        )

            os.makedirs(os.path.dirname(profile_path), exist_ok=True)
            with open(profile_path, "a") as f:
                f.write(f"\n{alias_cmd}\n")
            return CommandResult(
                **{"success": True, "message": f"Alias added to {profile_path}"}
            )
        except Exception as e:
            return CommandResult(**{"success": False, "error": str(e)})


class PythonManager:
    def __init__(self, manager):
        self.manager = manager

    def install_uv(self) -> CommandResult:
        cmd = ["curl", "-LsSf", "https://astral.sh/uv/install.sh", "|", "sh"]
        if platform.system() == "Windows":
            cmd = ["powershell", "-c", "irm https://astral.sh/uv/install.ps1 | iex"]

        try:
            if platform.system() == "Windows":
                result = self.manager.run_command(cmd[-1], shell=True)  # nosec
            else:
                result = self.manager.run_command(
                    "curl -LsSf https://astral.sh/uv/install.sh | sh",
                    shell=True,  # nosec
                )  # nosec
            return result
        except Exception as e:
            return CommandResult(**{"success": False, "error": str(e)})

    def create_venv(
        self, path: str, python_version: str | None = None
    ) -> CommandResult:
        cmd = ["uv", "venv", path]
        if python_version:
            cmd.extend(["--python", python_version])
        return self.manager.run_command(cmd)

    def install_package(
        self, package: str, venv_path: str | None = None
    ) -> CommandResult:
        cmd = ["uv", "pip", "install", package]
        env = os.environ.copy()
        if venv_path:
            if platform.system() == "Windows":
                env["VIRTUAL_ENV"] = venv_path
            else:
                env["VIRTUAL_ENV"] = venv_path

        return self.manager.run_command(cmd)


class NodeManager:
    def __init__(self, manager):
        self.manager = manager

    def install_nvm(self) -> CommandResult:
        if platform.system() == "Windows":
            return CommandResult(
                **{
                    "success": False,
                    "error": "NVM for Windows not supported directly via this tool yet. Use nvm-windows installer.",
                }
            )

        cmd = "curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash"
        return self.manager.run_command(cmd, shell=True)  # nosec

    def install_node(self, version: str = "--lts") -> CommandResult:

        cmd = f". ~/.nvm/nvm.sh && nvm install {version}"
        return self.manager.run_command(cmd, shell=True)  # nosec

    def use_node(self, version: str) -> CommandResult:
        cmd = f". ~/.nvm/nvm.sh && nvm use {version}"
        return self.manager.run_command(cmd, shell=True)  # nosec


class SystemsManagerBase(ABC):
    def __init__(
        self, host: str | None = None, silent: bool = False, log_file: str | None = None
    ):
        self.host = host
        self.silent = silent
        self.logger = setup_logging(log_file)  # type: ignore
        self.fs_manager = FileSystemManager(self)
        self.shell_manager = ShellProfileManager(self)
        self.python_manager = PythonManager(self)
        self.node_manager = NodeManager(self)

    def log_command(
        self,
        command: list[str] | str,
        result: (
            subprocess.CompletedProcess | subprocess.CalledProcessError | None
        ) = None,
        error: Exception | None = None,
    ):
        if isinstance(command, str):
            command = command.split()
        self.logger.info(f"Running command: {' '.join(command)}")
        if result:
            self.logger.info(f"Return code: {result.returncode}")
            self.logger.info(f"Stdout: {result.stdout}")
            self.logger.info(f"Stderr: {result.stderr}")
        if error:
            self.logger.error(f"Error: {str(error)}")

    def remote_eval(self, py_code: str) -> Any:
        if not self.host:
            raise ValueError("remote_eval called but no remote host is configured")

        from tunnel_manager.tunnel_manager import HostManager

        hm = HostManager()
        if self.host not in hm.hosts:
            raise ValueError(
                f"Host '{self.host}' not configured in inventory ({hm.config_file})"
            )
        hinfo = hm.hosts[self.host]

        hostname = hinfo.get("hostname")
        user = hinfo.get("user", "genius")
        port = hinfo.get("port", 22)
        identity_file = hinfo.get("key_path") or hinfo.get("identity_file")

        import base64

        encoded_py = base64.b64encode(py_code.encode("utf-8")).decode("utf-8")
        remote_py_cmd = f"python3 -c \"import base64; exec(base64.b64decode('{encoded_py}').decode('utf-8'))\""

        ssh_cmd = ["ssh", "-o", "StrictHostKeyChecking=no"]
        if identity_file:
            ssh_cmd.extend(["-i", os.path.expanduser(identity_file)])
        ssh_cmd.extend(["-p", str(port), f"{user}@{hostname}", remote_py_cmd])

        try:
            res = subprocess.run(ssh_cmd, capture_output=True, text=True, timeout=15)
            if res.returncode != 0:
                raise RuntimeError(f"Remote evaluation failed: {res.stderr}")
            return json.loads(res.stdout)
        except Exception as e:
            self.logger.error(f"Failed to execute remote_eval: {str(e)}")
            raise

    def run_elevated_tool(
        self, category: str, action: str, target: str | None = None
    ) -> dict:
        """
        Subprocess invocation from non-privileged space to secure helper.
        """
        helper_name = "systems-manager-helper"
        helper_path = shutil.which(helper_name)
        if not helper_path:
            helper_path = os.path.join(os.path.dirname(sys.executable), helper_name)
            if not os.path.exists(helper_path):
                # Check default user paths
                home = os.path.expanduser("~")
                possible_path = os.path.join(home, ".local", "bin", helper_name)
                if os.path.exists(possible_path):
                    helper_path = possible_path

        cmd = ["sudo", helper_path, category, action]
        if target:
            cmd.append(target)

        try:
            # Enforce shell=False to ensure no shell injection
            res = subprocess.run(cmd, capture_output=True, text=True, shell=False)
            if res.returncode != 0:
                err_msg = (
                    res.stderr.strip()
                    or f"Elevated helper failed with returncode {res.returncode}"
                )
                if res.stdout:
                    try:
                        return json.loads(res.stdout)
                    except json.JSONDecodeError:
                        pass
                return {
                    "success": False,
                    "error": err_msg,
                    "returncode": res.returncode,
                    "stdout": res.stdout.strip(),
                    "stderr": res.stderr.strip(),
                }

            return json.loads(res.stdout)
        except json.JSONDecodeError:
            return {
                "success": False,
                "error": "Failed to parse structured JSON response from elevated helper.",
                "stdout": res.stdout,
                "stderr": res.stderr,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def run_command(
        self,
        command: list[str] | str,
        elevated: bool = False,
        shell: bool = False,
    ) -> CommandResult:
        if self.host:
            from tunnel_manager.tunnel_manager import HostManager

            hm = HostManager()
            if self.host not in hm.hosts:
                raise ValueError(
                    f"Host '{self.host}' not configured in inventory ({hm.config_file})"
                )
            hinfo = hm.hosts[self.host]

            if isinstance(command, str):
                remote_cmd = command
            else:
                remote_cmd = " ".join(
                    (
                        f'"{c}"'
                        if " " in c or "*" in c or "$" in c or "?" in c or ";" in c
                        else c
                    )
                    for c in command
                )

            if elevated:
                remote_cmd = f"sudo {remote_cmd}"

            ssh_args = ["ssh", "-o", "StrictHostKeyChecking=no"]
            identity_file = hinfo.get("key_path") or hinfo.get("identity_file")
            if identity_file:
                ssh_args.extend(["-i", os.path.expanduser(identity_file)])
            port = hinfo.get("port", 22)
            ssh_args.extend(["-p", str(port)])

            user = hinfo.get("user", "genius")
            hostname = hinfo.get("hostname")
            ssh_args.append(f"{user}@{hostname}")
            ssh_args.append(remote_cmd)

            command = ssh_args
            shell = False

        if isinstance(command, str):
            command = command.split()
        if not self.host and elevated and platform.system() == "Linux":
            command = ["sudo"] + command
        elif not self.host and elevated and platform.system() == "Windows":
            arg_list = " ".join(f'"{c}"' if " " in c else c for c in command)
            command = [
                "powershell.exe",
                "Start-Process",
                "powershell",
                "-Verb",
                "runAs",
                "-ArgumentList",
                f'-Command "{arg_list}"',
                "-Wait",
            ]
            shell = True
        try:
            if self.silent:
                result_sp: subprocess.CompletedProcess[Any] = subprocess.run(
                    command,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    shell=shell,
                    check=True,
                )  # nosec
                stdout = None
                stderr = None
            else:
                print(f"Running: {' '.join(command)}", file=sys.stderr)
                result_sp: subprocess.CompletedProcess[Any] = subprocess.run(  # type: ignore
                    command,
                    capture_output=True,
                    text=True,
                    shell=shell,
                    check=True,
                )  # nosec
                stdout = result_sp.stdout
                stderr = result_sp.stderr
            self.log_command(command, result_sp)
            return CommandResult(
                **{
                    "success": True,
                    "returncode": result_sp.returncode,
                    "stdout": stdout,
                    "stderr": stderr,
                }
            )
        except subprocess.CalledProcessError as e:
            self.log_command(command, result=e, error=e)
            if not self.silent:
                print(f"Error: {e.stderr}", file=sys.stderr)
            return CommandResult(
                **{
                    "success": False,
                    "returncode": e.returncode,
                    "stdout": e.stdout,
                    "stderr": e.stderr,
                    "error": str(e),
                }
            )
        except Exception as e:
            self.log_command(command, error=e)
            return CommandResult(**{"success": False, "error": str(e)})

    @abstractmethod
    def install_applications(self, apps: list[str]) -> CommandResult:
        pass

    @abstractmethod
    def update(self) -> CommandResult:
        pass

    @abstractmethod
    def clean(self) -> CommandResult:
        pass

    @abstractmethod
    def optimize(self) -> CommandResult:
        pass

    @abstractmethod
    def install_snapd(self) -> CommandResult:
        pass

    @abstractmethod
    def add_repository(self, repo_url: str, name: str | None = None) -> CommandResult:
        pass

    @abstractmethod
    def install_local_package(self, file_path: str) -> CommandResult:
        pass

    @abstractmethod
    def search_package(self, query: str) -> CommandResult:
        pass

    @abstractmethod
    def get_package_info(self, package: str) -> CommandResult:
        pass

    @abstractmethod
    def list_installed_packages(self) -> CommandResult:
        pass

    @abstractmethod
    def list_upgradable_packages(self) -> CommandResult:
        pass

    @abstractmethod
    def clean_package_cache(self) -> CommandResult:
        pass

    def install_via_snap(self, app: str) -> CommandResult:
        snap_bin = shutil.which("snap")
        if snap_bin is None:
            self.logger.info("Snap not found; installing snapd...")
            snapd_result = self.install_snapd()
            if not snapd_result["success"]:
                return CommandResult(
                    **{
                        "success": False,
                        "error": "Failed to install snapd",
                        "details": snapd_result,
                    }
                )
            enable_result = self.run_command(
                ["systemctl", "enable", "--now", "snapd.socket"], elevated=True
            )
            if not enable_result["success"]:
                self.logger.warning("Failed to enable snapd.socket")
            symlink_result = self.run_command(
                ["ln", "-s", "/var/lib/snapd/snap", "/snap"], elevated=True
            )
            if not symlink_result["success"]:
                self.logger.warning("Failed to create /snap symlink")
        install_result = self.run_command(["snap", "install", app], elevated=True)
        return CommandResult(
            **{
                "success": install_result["success"],
                "details": install_result,
                "app": app,
            }
        )

    def install_python_modules(self, modules: list[str]) -> dict[str, Any]:
        results: dict[str, Any] = {
            "upgraded_pip": False,
            "installed": [],
            "failed": [],
            "success": True,
        }
        pip_upgrade_cmd = ["python", "-m", "pip", "install", "--upgrade", "pip"]
        pip_upgrade_result = self.run_command(pip_upgrade_cmd)
        if pip_upgrade_result["success"]:
            results["upgraded_pip"] = True
        else:
            results["success"] = False
            self.logger.error("Failed to upgrade pip")
        for module in modules:
            install_cmd = ["python", "-m", "pip", "install", "--upgrade", module]
            install_result = self.run_command(install_cmd)
            if install_result["success"]:
                results["installed"].append(module)
            else:
                results["failed"].append(module)
                results["success"] = False
                self.logger.error(
                    f"Failed to install {module}: {install_result.get('error', 'Unknown error')}"
                )
        return results

    def font(self, fonts: list[str] | None = None) -> CommandResult:
        if not fonts:
            fonts = ["Hack"]
        api_url = "https://api.github.com/repos/ryanoasis/nerd-fonts/releases/latest"
        response = requests.get(api_url, timeout=10).json()
        all_assets = [
            a
            for a in response["assets"]
            if a["name"].endswith(".zip") and "FontPatcher" not in a["name"]
        ]

        if any(f.lower() == "all" for f in fonts):
            assets = all_assets
        else:
            assets = [
                a
                for a in all_assets
                if any(f.lower() in a["name"].lower() for f in fonts)
            ]

        if not assets:
            return CommandResult(
                **{"success": False, "error": f"No matching fonts found for {fonts}"}
            )

        if platform.system() == "Linux":
            font_dir = os.path.expanduser("~/.local/share/fonts")
            os.makedirs(font_dir, exist_ok=True)
            extract_path = font_dir
        elif platform.system() == "Windows":
            font_dir = r"C:\Windows\Fonts"
            extract_path = "."
        else:
            return CommandResult(
                **{"success": False, "error": "Unsupported OS for font installation"}
            )

        successful_downloads = []
        for asset in assets:
            zip_name = asset["name"]
            url = asset["browser_download_url"]
            self.logger.info(f"Downloading {zip_name} from {url}")
            if not self.silent:
                print(f"Downloading {zip_name} from {url}", file=sys.stderr)
            try:
                r = requests.get(url, timeout=10)
                r.raise_for_status()
                with open(zip_name, "wb") as f:
                    f.write(r.content)
                with zipfile.ZipFile(zip_name, "r") as zip_ref:
                    zip_ref.extractall(extract_path)
                os.remove(zip_name)
                successful_downloads.append(zip_name)
            except Exception as e:
                self.logger.error(f"Failed to process {zip_name}: {e}")
                continue

        font_files = glob.glob(
            os.path.join(extract_path, "**/*.ttf"), recursive=True
        ) + glob.glob(os.path.join(extract_path, "**/*.otf"), recursive=True)

        installed_fonts = []
        if platform.system() == "Windows":
            for font in font_files:
                dest = os.path.join(font_dir, os.path.basename(font))
                self.logger.info(f"Moving {font} to {dest}")
                if not self.silent:
                    print(f"Moving {font} to {dest}", file=sys.stderr)
                copy_cmd = [
                    "powershell.exe",
                    "Copy-Item",
                    "-Path",
                    f'"{font}"',
                    "-Destination",
                    f'"{dest}"',
                    "-Force",
                ]
                copy_result = self.run_command(copy_cmd, elevated=True)
                if copy_result["success"]:
                    installed_fonts.append(os.path.basename(font))
                else:
                    self.logger.error(
                        f"Failed to copy {font}: {copy_result.get('error')}"
                    )
        elif platform.system() == "Linux":
            cache_result = self.run_command(["fc-cache", "-fv"], elevated=True)
            if cache_result["success"]:
                installed_fonts = [os.path.basename(f) for f in font_files]
            else:
                self.logger.error("Failed to update font cache")

        overall_success = len(successful_downloads) > 0
        return CommandResult(
            **{
                "success": overall_success,
                "requested_fonts": fonts,
                "downloaded": successful_downloads,
                "installed_fonts": installed_fonts,
                "total_fonts": len(font_files),
                "os": platform.system(),
            }
        )

    def get_os_statistics(self) -> SystemStats:
        if self.host:
            py_code = """
import json, platform, os
try:
    load_avg = os.getloadavg()
except Exception:
    load_avg = "N/A"
stats = {
    "system": platform.system(),
    "release": platform.release(),
    "version": platform.version(),
    "machine": platform.machine(),
    "processor": platform.processor(),
    "load_avg": load_avg
}
print(json.dumps(stats))
"""
            return SystemStats(**self.remote_eval(py_code))

        return SystemStats(
            **{  # type: ignore
                "system": platform.system(),
                "release": platform.release(),
                "version": platform.version(),
                "machine": platform.machine(),
                "processor": platform.processor(),
                "load_avg": (
                    os.getloadavg() if platform.system() != "Windows" else "N/A"
                ),
            }
        )

    def get_hardware_statistics(self) -> SystemStats:
        if self.host:
            py_code = """
import json, psutil
stats = {
    "cpu_percent": psutil.cpu_percent(interval=0.5),
    "cpu_count": psutil.cpu_count(),
    "memory": psutil.virtual_memory()._asdict(),
    "disk_usage": psutil.disk_usage("/")._asdict(),
    "network": psutil.net_io_counters()._asdict(),
}
print(json.dumps(stats))
"""
            return SystemStats(**self.remote_eval(py_code))

        return SystemStats(
            **{
                "cpu_percent": psutil.cpu_percent(interval=1),
                "cpu_count": psutil.cpu_count(),
                "memory": psutil.virtual_memory()._asdict(),
                "disk_usage": psutil.disk_usage("/")._asdict(),
                "network": psutil.net_io_counters()._asdict(),
            }
        )

    def list_services(self) -> CommandResult:
        try:
            if platform.system() == "Linux":
                result = self.run_command(
                    [
                        "systemctl",
                        "list-units",
                        "--type=service",
                        "--all",
                        "--no-pager",
                        "--plain",
                        "--no-legend",
                    ]
                )
                if not result["success"]:
                    return result
                services = []
                for line in (result.get("stdout") or "").strip().splitlines():
                    parts = line.split(None, 4)
                    if len(parts) >= 4:
                        services.append(
                            {
                                "name": parts[0],
                                "load": parts[1],
                                "active": parts[2],
                                "sub": parts[3],
                                "description": parts[4] if len(parts) > 4 else "",
                            }
                        )
                return CommandResult(
                    **{"success": True, "services": services, "total": len(services)}
                )
            elif platform.system() == "Windows":
                result = self.run_command(
                    [
                        "powershell.exe",
                        "-Command",
                        "Get-Service | Select-Object Name,Status,DisplayName | ConvertTo-Json -Depth 3",
                    ],
                    shell=True,  # nosec
                )  # nosec
                if not result["success"]:
                    return result
                try:
                    services = json.loads(result.get("stdout", "[]"))
                    if isinstance(services, dict):
                        services = [services]
                    return CommandResult(
                        **{
                            "success": True,
                            "services": services,
                            "total": len(services),
                        }
                    )
                except json.JSONDecodeError:
                    return CommandResult(
                        **{"success": False, "error": "Failed to parse service list"}
                    )
            return CommandResult(
                **{"success": False, "error": f"Unsupported OS: {platform.system()}"}
            )
        except Exception as e:
            return CommandResult(**{"success": False, "error": str(e)})

    def get_service_status(self, name: str) -> CommandResult:
        try:
            if platform.system() == "Linux":
                result = self.run_command(["systemctl", "status", name, "--no-pager"])
                return CommandResult(
                    **{
                        "success": True,
                        "service": name,
                        "output": result.get("stdout", ""),
                        "returncode": result.get("returncode"),
                    }
                )
            elif platform.system() == "Windows":
                result = self.run_command(
                    [
                        "powershell.exe",
                        "-Command",
                        f"Get-Service -Name '{name}' | Select-Object Name,Status,DisplayName,StartType | ConvertTo-Json",
                    ],
                    shell=True,  # nosec
                )  # nosec
                if result["success"]:
                    try:
                        return CommandResult(
                            **{
                                "success": True,
                                "service": json.loads(result.get("stdout", "{}")),
                            }
                        )
                    except json.JSONDecodeError:
                        pass
                return CommandResult(
                    **{
                        "success": result["success"],
                        "service": name,
                        "output": result.get("stdout", ""),
                    }
                )
            return CommandResult(
                **{"success": False, "error": f"Unsupported OS: {platform.system()}"}
            )
        except Exception as e:
            return CommandResult(**{"success": False, "error": str(e)})

    def start_service(self, name: str) -> CommandResult:
        if platform.system() == "Linux":
            if self.host is None:
                res = self.run_elevated_tool("service", "start", name)
                return CommandResult(
                    success=res.get("success", False),
                    stdout=res.get("stdout"),
                    stderr=res.get("stderr"),
                    error=res.get("error"),
                    command=f"sudo systems-manager-helper service start {name}",
                )
            else:
                return self.run_command(["systemctl", "start", name], elevated=True)
        elif platform.system() == "Windows":
            return self.run_command(
                ["powershell.exe", "-Command", f"Start-Service -Name '{name}'"],
                elevated=True,
                shell=True,  # nosec
            )  # nosec
        return CommandResult(
            **{"success": False, "error": f"Unsupported OS: {platform.system()}"}
        )

    def stop_service(self, name: str) -> CommandResult:
        if platform.system() == "Linux":
            if self.host is None:
                res = self.run_elevated_tool("service", "stop", name)
                return CommandResult(
                    success=res.get("success", False),
                    stdout=res.get("stdout"),
                    stderr=res.get("stderr"),
                    error=res.get("error"),
                    command=f"sudo systems-manager-helper service stop {name}",
                )
            else:
                return self.run_command(["systemctl", "stop", name], elevated=True)
        elif platform.system() == "Windows":
            return self.run_command(
                ["powershell.exe", "-Command", f"Stop-Service -Name '{name}' -Force"],
                elevated=True,
                shell=True,  # nosec
            )  # nosec
        return CommandResult(
            **{"success": False, "error": f"Unsupported OS: {platform.system()}"}
        )

    def restart_service(self, name: str) -> CommandResult:
        if platform.system() == "Linux":
            if self.host is None:
                res = self.run_elevated_tool("service", "restart", name)
                return CommandResult(
                    success=res.get("success", False),
                    stdout=res.get("stdout"),
                    stderr=res.get("stderr"),
                    error=res.get("error"),
                    command=f"sudo systems-manager-helper service restart {name}",
                )
            else:
                return self.run_command(["systemctl", "restart", name], elevated=True)
        elif platform.system() == "Windows":
            if not os.path.exists(self.winget_bin):  # type: ignore
                self.winget_bin = "winget.exe"
            return self.run_command(
                [
                    "powershell.exe",
                    "-Command",
                    f"Restart-Service -Name '{name}' -Force",
                ],
                elevated=True,
                shell=True,  # nosec
            )  # nosec
        return CommandResult(
            **{"success": False, "error": f"Unsupported OS: {platform.system()}"}
        )

    def enable_service(self, name: str) -> CommandResult:
        if platform.system() == "Linux":
            if self.host is None:
                res = self.run_elevated_tool("service", "enable", name)
                return CommandResult(
                    success=res.get("success", False),
                    stdout=res.get("stdout"),
                    stderr=res.get("stderr"),
                    error=res.get("error"),
                    command=f"sudo systems-manager-helper service enable {name}",
                )
            else:
                return self.run_command(["systemctl", "enable", name], elevated=True)
        elif platform.system() == "Windows":
            return self.run_command(
                [
                    "powershell.exe",
                    "-Command",
                    f"Set-Service -Name '{name}' -StartupType Automatic",
                ],
                elevated=True,
                shell=True,  # nosec
            )  # nosec
        return CommandResult(
            **{"success": False, "error": f"Unsupported OS: {platform.system()}"}
        )

    def disable_service(self, name: str) -> CommandResult:
        if platform.system() == "Linux":
            if self.host is None:
                res = self.run_elevated_tool("service", "disable", name)
                return CommandResult(
                    success=res.get("success", False),
                    stdout=res.get("stdout"),
                    stderr=res.get("stderr"),
                    error=res.get("error"),
                    command=f"sudo systems-manager-helper service disable {name}",
                )
            else:
                return self.run_command(["systemctl", "disable", name], elevated=True)
        elif platform.system() == "Windows":
            return self.run_command(
                [
                    "powershell.exe",
                    "-Command",
                    f"Set-Service -Name '{name}' -StartupType Disabled",
                ],
                elevated=True,
                shell=True,  # nosec
            )  # nosec
        return CommandResult(
            **{"success": False, "error": f"Unsupported OS: {platform.system()}"}
        )

    def list_processes(self) -> CommandResult:
        if self.host:
            py_code = """
import json, psutil
processes = []
for proc in psutil.process_iter(["pid", "name", "username", "cpu_percent", "memory_percent", "status"]):
    try:
        info = proc.info
        processes.append({
            "pid": info["pid"],
            "name": info["name"],
            "username": info["username"],
            "cpu_percent": info["cpu_percent"],
            "memory_percent": round(info["memory_percent"], 2) if info["memory_percent"] else 0,
            "status": info["status"],
        })
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        continue
print(json.dumps(processes))
"""
            res = self.remote_eval(py_code)
            return CommandResult(
                **{"success": True, "processes": res, "total": len(res)}
            )

        try:
            processes = []
            for proc in psutil.process_iter(
                ["pid", "name", "username", "cpu_percent", "memory_percent", "status"]
            ):
                try:
                    info = proc.info
                    processes.append(
                        {
                            "pid": info["pid"],
                            "name": info["name"],
                            "username": info["username"],
                            "cpu_percent": info["cpu_percent"],
                            "memory_percent": (
                                round(info["memory_percent"], 2)
                                if info["memory_percent"]
                                else 0
                            ),
                            "status": info["status"],
                        }
                    )
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            return CommandResult(
                **{"success": True, "processes": processes, "total": len(processes)}
            )
        except Exception as e:
            return CommandResult(**{"success": False, "error": str(e)})

    def get_process_info(self, pid: int) -> CommandResult:
        if self.host:
            py_code = f"""
import json, psutil, datetime
try:
    proc = psutil.Process({pid})
    with proc.oneshot():
        info = {{
            "pid": proc.pid,
            "name": proc.name(),
            "status": proc.status(),
            "username": proc.username(),
            "cpu_percent": proc.cpu_percent(interval=0.1),
            "memory_percent": round(proc.memory_percent(), 2),
            "memory_info": proc.memory_info()._asdict(),
            "create_time": datetime.datetime.fromtimestamp(proc.create_time()).isoformat(),
            "cmdline": proc.cmdline(),
            "num_threads": proc.num_threads(),
        }}
    print(json.dumps({{"success": True, "process": info}}))
except psutil.NoSuchProcess:
    print(json.dumps({{"success": False, "error": "No process found with PID {pid}"}}))
except psutil.AccessDenied:
    print(json.dumps({{"success": False, "error": "Access denied to process {pid}"}}))
except Exception as e:
    print(json.dumps({{"success": False, "error": str(e)}}))
"""
            res = self.remote_eval(py_code)
            return CommandResult(**res)

        try:
            proc = psutil.Process(pid)
            with proc.oneshot():
                info = {
                    "pid": proc.pid,
                    "name": proc.name(),
                    "status": proc.status(),
                    "username": proc.username(),
                    "cpu_percent": proc.cpu_percent(interval=0.1),
                    "memory_percent": round(proc.memory_percent(), 2),
                    "memory_info": proc.memory_info()._asdict(),
                    "create_time": datetime.fromtimestamp(
                        proc.create_time()
                    ).isoformat(),
                    "cmdline": proc.cmdline(),
                    "num_threads": proc.num_threads(),
                }
            return CommandResult(**{"success": True, "process": info})
        except psutil.NoSuchProcess:
            return CommandResult(
                **{"success": False, "error": f"No process found with PID {pid}"}
            )
        except psutil.AccessDenied:
            return CommandResult(
                **{"success": False, "error": f"Access denied to process {pid}"}
            )
        except Exception as e:
            return CommandResult(**{"success": False, "error": str(e)})

    def kill_process(self, pid: int, signal: int = 15) -> CommandResult:
        try:
            proc = psutil.Process(pid)
            name = proc.name()
            proc.kill() if signal == 9 else proc.terminate()
            return CommandResult(
                **{
                    "success": True,
                    "message": f"Signal {signal} sent to process {pid} ({name})",
                }
            )
        except psutil.NoSuchProcess:
            return CommandResult(
                **{"success": False, "error": f"No process found with PID {pid}"}
            )
        except psutil.AccessDenied:
            return CommandResult(
                **{"success": False, "error": f"Access denied to process {pid}"}
            )
        except Exception as e:
            return CommandResult(**{"success": False, "error": str(e)})

    def list_network_interfaces(self) -> CommandResult:
        if self.host:
            py_code = """
import json, psutil
interfaces = {}
addrs = psutil.net_if_addrs()
stats = psutil.net_if_stats()
for iface, addr_list in addrs.items():
    iface_info = {"addresses": [], "is_up": False, "speed": 0}
    if iface in stats:
        iface_info.update({
            "is_up": stats[iface].isup,
            "speed": stats[iface].speed,
            "mtu": stats[iface].mtu,
        })
    for addr in addr_list:
        iface_info["addresses"].append({
            "family": str(addr.family),
            "address": addr.address,
            "netmask": addr.netmask,
            "broadcast": addr.broadcast,
        })
    interfaces[iface] = iface_info
print(json.dumps(interfaces))
"""
            res = self.remote_eval(py_code)
            return CommandResult(**{"success": True, "interfaces": res})

        try:
            interfaces = {}
            addrs = psutil.net_if_addrs()
            stats = psutil.net_if_stats()
            for iface, addr_list in addrs.items():
                iface_info = {"addresses": [], "is_up": False, "speed": 0}
                if iface in stats:
                    iface_info.update(
                        {
                            "is_up": stats[iface].isup,
                            "speed": stats[iface].speed,
                            "mtu": stats[iface].mtu,
                        }
                    )
                for addr in addr_list:
                    iface_info["addresses"].append(  # type: ignore
                        {
                            "family": str(addr.family),
                            "address": addr.address,
                            "netmask": addr.netmask,
                            "broadcast": addr.broadcast,
                        }
                    )
                interfaces[iface] = iface_info
            return CommandResult(**{"success": True, "interfaces": interfaces})
        except Exception as e:
            return CommandResult(**{"success": False, "error": str(e)})

    def list_open_ports(self) -> CommandResult:
        if self.host:
            py_code = """
import json, psutil, subprocess
try:
    connections = []
    for conn in psutil.net_connections(kind="inet"):
        if conn.status == "LISTEN":
            connections.append({
                "local_address": conn.laddr.ip if conn.laddr else None,
                "local_port": conn.laddr.port if conn.laddr else None,
                "pid": conn.pid,
                "status": conn.status,
            })
    print(json.dumps({"success": True, "ports": connections, "total": len(connections)}))
except Exception as e:
    try:
        res = subprocess.run(["ss", "-tlnp"], capture_output=True, text=True)
        print(json.dumps({"success": True, "output": res.stdout}))
    except Exception as ex:
        print(json.dumps({"success": False, "error": str(e)}))
"""
            res = self.remote_eval(py_code)
            return CommandResult(**res)

        try:
            connections = []
            for conn in psutil.net_connections(kind="inet"):
                if conn.status == "LISTEN":
                    connections.append(
                        {
                            "local_address": conn.laddr.ip if conn.laddr else None,
                            "local_port": conn.laddr.port if conn.laddr else None,
                            "pid": conn.pid,
                            "status": conn.status,
                        }
                    )
            return CommandResult(
                **{"success": True, "ports": connections, "total": len(connections)}
            )
        except psutil.AccessDenied:
            cmd = (
                ["ss", "-tlnp"] if platform.system() == "Linux" else ["netstat", "-an"]
            )
            result = self.run_command(cmd)
            return CommandResult(
                **{"success": result["success"], "output": result.get("stdout", "")}
            )
        except Exception as e:
            return CommandResult(**{"success": False, "error": str(e)})

    def ping_host(self, host: str, count: int = 4) -> CommandResult:
        flag = "-n" if platform.system() == "Windows" else "-c"
        result = self.run_command(["ping", flag, str(count), host])
        return CommandResult(
            **{
                "success": result["success"],
                "host": host,
                "output": result.get("stdout", ""),
            }
        )

    def dns_lookup(self, hostname: str) -> CommandResult:
        if self.host:
            py_code = f"""
import json, socket
try:
    results = socket.getaddrinfo({repr(hostname)}, None)
    addresses = list(set(addr[4][0] for addr in results))
    print(json.dumps({{"success": True, "hostname": {repr(hostname)}, "addresses": addresses}}))
except Exception as e:
    print(json.dumps({{"success": False, "error": str(e)}}))
"""
            res = self.remote_eval(py_code)
            return CommandResult(**res)

        try:
            results = socket.getaddrinfo(hostname, None)
            addresses = list(set(addr[4][0] for addr in results))
            return CommandResult(
                **{"success": True, "hostname": hostname, "addresses": addresses}
            )
        except socket.gaierror as e:
            return CommandResult(
                **{"success": False, "error": f"DNS lookup failed: {str(e)}"}
            )
        except Exception as e:
            return CommandResult(**{"success": False, "error": str(e)})

    def list_disks(self) -> CommandResult:
        if self.host:
            py_code = """
import json, psutil
partitions = []
for part in psutil.disk_partitions(all=False):
    entry = {
        "device": part.device,
        "mountpoint": part.mountpoint,
        "fstype": part.fstype,
        "opts": part.opts,
    }
    try:
        usage = psutil.disk_usage(part.mountpoint)
        entry.update({
            "total": usage.total,
            "used": usage.used,
            "free": usage.free,
            "percent": usage.percent,
        })
    except Exception:
        pass
    partitions.append(entry)
print(json.dumps(partitions))
"""
            res = self.remote_eval(py_code)
            return CommandResult(**{"success": True, "disks": res, "total": len(res)})

        try:
            partitions = []
            for part in psutil.disk_partitions(all=False):
                entry = {
                    "device": part.device,
                    "mountpoint": part.mountpoint,
                    "fstype": part.fstype,
                    "opts": part.opts,
                }
                try:
                    usage = psutil.disk_usage(part.mountpoint)
                    entry.update(
                        {
                            "total": usage.total,
                            "used": usage.used,
                            "free": usage.free,
                            "percent": usage.percent,
                        }
                    )
                except (PermissionError, OSError):
                    pass
                partitions.append(entry)
            return CommandResult(
                **{"success": True, "disks": partitions, "total": len(partitions)}
            )
        except Exception as e:
            return CommandResult(**{"success": False, "error": str(e)})

    def get_disk_usage(self, path: str = "/") -> CommandResult:
        if self.host:
            py_code = f"""
import json, psutil
try:
    usage = psutil.disk_usage({repr(path)})
    print(json.dumps({{
        "success": True,
        "path": {repr(path)},
        "total": usage.total,
        "used": usage.used,
        "free": usage.free,
        "percent": usage.percent,
    }}))
except Exception as e:
    print(json.dumps({{"success": False, "error": str(e)}}))
"""
            res = self.remote_eval(py_code)
            return CommandResult(**res)

        try:
            usage = psutil.disk_usage(path)
            return CommandResult(
                **{
                    "success": True,
                    "path": path,
                    "total": usage.total,
                    "used": usage.used,
                    "free": usage.free,
                    "percent": usage.percent,
                }
            )
        except Exception as e:
            return CommandResult(**{"success": False, "error": str(e)})

    def list_users(self) -> CommandResult:
        if self.host:
            py_code = """
import json
users = []
try:
    with open("/etc/passwd") as f:
        for line in f:
            parts = line.strip().split(":")
            if len(parts) >= 7:
                users.append({
                    "username": parts[0],
                    "uid": int(parts[2]),
                    "gid": int(parts[3]),
                    "home": parts[5],
                    "shell": parts[6],
                })
    print(json.dumps({"success": True, "users": users, "total": len(users)}))
except Exception as e:
    print(json.dumps({"success": False, "error": str(e)}))
"""
            res = self.remote_eval(py_code)
            return CommandResult(**res)

        try:
            if platform.system() == "Linux":
                users = []
                with open("/etc/passwd") as f:
                    for line in f:
                        parts = line.strip().split(":")
                        if len(parts) >= 7:
                            users.append(
                                {
                                    "username": parts[0],
                                    "uid": int(parts[2]),
                                    "gid": int(parts[3]),
                                    "home": parts[5],
                                    "shell": parts[6],
                                }
                            )
                return CommandResult(
                    **{"success": True, "users": users, "total": len(users)}
                )
            elif platform.system() == "Windows":
                result = self.run_command(
                    [
                        "powershell.exe",
                        "-Command",
                        "Get-LocalUser | Select-Object Name,Enabled,Description | ConvertTo-Json -Depth 3",
                    ],
                    shell=True,  # nosec
                )
                if result["success"]:
                    try:
                        users = json.loads(result.get("stdout", "[]"))
                        if isinstance(users, dict):
                            users = [users]
                        return CommandResult(
                            **{"success": True, "users": users, "total": len(users)}
                        )
                    except json.JSONDecodeError:
                        return CommandResult(
                            **{"success": False, "error": "Failed to parse user list"}
                        )
                return result
            return CommandResult(
                **{"success": False, "error": f"Unsupported OS: {platform.system()}"}
            )
        except Exception as e:
            return CommandResult(**{"success": False, "error": str(e)})

    def list_groups(self) -> CommandResult:
        if self.host:
            py_code = """
import json
groups = []
try:
    with open("/etc/group") as f:
        for line in f:
            parts = line.strip().split(":")
            if len(parts) >= 4:
                groups.append({
                    "name": parts[0],
                    "gid": int(parts[2]),
                    "members": parts[3].split(",") if parts[3] else [],
                })
    print(json.dumps({"success": True, "groups": groups, "total": len(groups)}))
except Exception as e:
    print(json.dumps({"success": False, "error": str(e)}))
"""
            res = self.remote_eval(py_code)
            return CommandResult(**res)

        try:
            if platform.system() == "Linux":
                groups = []
                with open("/etc/group") as f:
                    for line in f:
                        parts = line.strip().split(":")
                        if len(parts) >= 4:
                            groups.append(
                                {
                                    "name": parts[0],
                                    "gid": int(parts[2]),
                                    "members": parts[3].split(",") if parts[3] else [],
                                }
                            )
                return CommandResult(
                    **{"success": True, "groups": groups, "total": len(groups)}
                )
            elif platform.system() == "Windows":
                result = self.run_command(
                    [
                        "powershell.exe",
                        "-Command",
                        "Get-LocalGroup | Select-Object Name,Description | ConvertTo-Json -Depth 3",
                    ],
                    shell=True,  # nosec
                )
                if result["success"]:
                    try:
                        groups = json.loads(result.get("stdout", "[]"))
                        if isinstance(groups, dict):
                            groups = [groups]
                        return CommandResult(
                            **{"success": True, "groups": groups, "total": len(groups)}
                        )
                    except json.JSONDecodeError:
                        return CommandResult(
                            **{"success": False, "error": "Failed to parse group list"}
                        )
                return result
            return CommandResult(
                **{"success": False, "error": f"Unsupported OS: {platform.system()}"}
            )
        except Exception as e:
            return CommandResult(**{"success": False, "error": str(e)})

    def get_system_logs(
        self, unit: str | None = None, lines: int = 100, priority: str | None = None
    ) -> CommandResult:
        try:
            if platform.system() == "Linux":
                cmd = ["journalctl", "--no-pager", "-n", str(lines)]
                if unit:
                    cmd.extend(["-u", unit])
                if priority:
                    cmd.extend(["-p", priority])
                result = self.run_command(cmd)
                logs = (
                    result.get("stdout", "")
                    if result["success"]
                    else result.get("stderr", result.get("error", "Unknown error"))
                )
                return CommandResult(**{"success": result["success"], "logs": logs})
            elif platform.system() == "Windows":
                result = self.run_command(
                    [
                        "powershell.exe",
                        "-Command",
                        f"Get-EventLog -LogName System -Newest {lines} | Format-List | Out-String",
                    ],
                    shell=True,  # nosec
                )
                logs = (
                    result.get("stdout", "")
                    if result["success"]
                    else result.get("stderr", result.get("error", "Unknown error"))
                )
                return CommandResult(**{"success": result["success"], "logs": logs})
            return CommandResult(
                **{"success": False, "error": f"Unsupported OS: {platform.system()}"}
            )
        except Exception as e:
            return CommandResult(**{"success": False, "error": str(e)})

    def tail_log_file(self, path: str, lines: int = 50) -> CommandResult:
        try:
            if not os.path.exists(path):
                return CommandResult(
                    **{"success": False, "error": f"File not found: {path}"}
                )
            with open(path, errors="replace") as f:
                all_lines = f.readlines()
                tail = all_lines[-lines:] if len(all_lines) > lines else all_lines
            return CommandResult(
                **{
                    "success": True,
                    "path": path,
                    "lines": len(tail),
                    "content": "".join(tail),
                }
            )
        except Exception as e:
            return CommandResult(**{"success": False, "error": str(e)})

    def system_health_check(self) -> CommandResult:
        try:
            boot_time = datetime.fromtimestamp(psutil.boot_time())
            uptime = datetime.now() - boot_time
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            swap = psutil.swap_memory()
            disk_warnings = []
            for part in psutil.disk_partitions(all=False):
                try:
                    usage = psutil.disk_usage(part.mountpoint)
                    if usage.percent > 90:
                        disk_warnings.append(
                            {
                                "mountpoint": part.mountpoint,
                                "percent": usage.percent,
                                "free_gb": round(usage.free / (1024**3), 2),
                            }
                        )
                except (PermissionError, OSError):
                    continue
            top_procs = []
            for proc in sorted(
                psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]),
                key=lambda p: p.info.get("memory_percent", 0) or 0,
                reverse=True,
            )[:10]:
                try:
                    top_procs.append(proc.info)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            warnings = []
            if cpu_percent > 90:
                warnings.append(f"HIGH CPU: {cpu_percent}%")
            if memory.percent > 90:
                warnings.append(f"HIGH MEMORY: {memory.percent}%")
            if swap.percent > 80:
                warnings.append(f"HIGH SWAP: {swap.percent}%")
            for dw in disk_warnings:
                warnings.append(f"DISK FULL: {dw['mountpoint']} at {dw['percent']}%")
            load_avg = os.getloadavg() if platform.system() != "Windows" else None
            return CommandResult(
                **{
                    "success": True,
                    "status": "warning" if warnings else "healthy",
                    "warnings": warnings,
                    "uptime_seconds": int(uptime.total_seconds()),
                    "uptime_human": str(uptime).split(".")[0],
                    "cpu_percent": cpu_percent,
                    "memory_percent": memory.percent,
                    "memory_available_gb": round(memory.available / (1024**3), 2),
                    "swap_percent": swap.percent,
                    "disk_warnings": disk_warnings,
                    "load_average": load_avg,
                    "top_memory_processes": top_procs,
                }
            )
        except Exception as e:
            return CommandResult(**{"success": False, "error": str(e)})

    def get_uptime(self) -> CommandResult:
        try:
            boot_time = datetime.fromtimestamp(psutil.boot_time())
            uptime = datetime.now() - boot_time
            return CommandResult(
                **{
                    "success": True,
                    "boot_time": boot_time.isoformat(),
                    "uptime_seconds": int(uptime.total_seconds()),
                    "uptime_human": str(uptime).split(".")[0],
                }
            )
        except Exception as e:
            return CommandResult(**{"success": False, "error": str(e)})

    def list_cron_jobs(self, user: str | None = None) -> CommandResult:
        try:
            if platform.system() == "Linux":
                cmd = ["crontab", "-l", "-u", user] if user else ["crontab", "-l"]
                result = self.run_command(cmd)
                jobs = []
                if result["success"]:
                    for line in (result.get("stdout") or "").strip().splitlines():
                        if line.strip() and not line.strip().startswith("#"):
                            jobs.append(line.strip())
                return CommandResult(
                    **{"success": True, "jobs": jobs, "total": len(jobs)}
                )
            elif platform.system() == "Windows":
                result = self.run_command(
                    ["schtasks", "/query", "/fo", "CSV", "/v"],
                    shell=True,  # nosec
                )  # nosec
                return CommandResult(
                    **{
                        "success": result["success"],
                        "output": result.get("stdout", ""),
                    }
                )
            return CommandResult(
                **{"success": False, "error": f"Unsupported OS: {platform.system()}"}
            )
        except Exception as e:
            return CommandResult(**{"success": False, "error": str(e)})

    def add_cron_job(
        self, schedule: str, command: str, user: str | None = None
    ) -> CommandResult:
        try:
            if platform.system() != "Linux":
                return CommandResult(
                    **{
                        "success": False,
                        "error": "Cron jobs are only supported on Linux",
                    }
                )
            cron_entry = f"{schedule} {command}"
            list_cmd = ["crontab", "-l", "-u", user] if user else ["crontab", "-l"]
            existing = self.run_command(list_cmd)
            current = existing.get("stdout", "") if existing["success"] else ""
            new_crontab = current.rstrip("\n") + "\n" + cron_entry + "\n"
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".cron", delete=False
            ) as tmp:
                tmp.write(new_crontab)
                tmp_path = tmp.name
            try:
                install_cmd = (
                    ["crontab", "-u", user, tmp_path] if user else ["crontab", tmp_path]
                )
                result = self.run_command(install_cmd, elevated=bool(user))
                return CommandResult(
                    **{
                        "success": result["success"],
                        "message": (
                            f"Cron job added: {cron_entry}"
                            if result["success"]
                            else "Failed"
                        ),
                        "details": result,
                    }
                )
            finally:
                os.remove(tmp_path)
        except Exception as e:
            return CommandResult(**{"success": False, "error": str(e)})

    def remove_cron_job(self, pattern: str, user: str | None = None) -> CommandResult:
        try:
            if platform.system() != "Linux":
                return CommandResult(
                    **{
                        "success": False,
                        "error": "Cron jobs are only supported on Linux",
                    }
                )
            list_cmd = ["crontab", "-l", "-u", user] if user else ["crontab", "-l"]
            existing = self.run_command(list_cmd)
            if not existing["success"]:
                return CommandResult(
                    **{"success": False, "error": "Failed to read current crontab"}
                )
            lines = (existing.get("stdout") or "").splitlines()
            removed = [
                line_content for line_content in lines if pattern in line_content
            ]
            kept = [
                line_content for line_content in lines if pattern not in line_content
            ]
            if not removed:
                return CommandResult(
                    **{
                        "success": False,
                        "error": f"Cron job with pattern '{pattern}' not found",
                    }
                )

            if not removed:
                return CommandResult(
                    **{
                        "success": True,
                        "message": "No matching cron jobs found",
                        "removed": [],
                    }
                )
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".cron", delete=False
            ) as tmp:
                tmp.write("\n".join(kept) + "\n")
                tmp_path = tmp.name
            try:
                install_cmd = (
                    ["crontab", "-u", user, tmp_path] if user else ["crontab", tmp_path]
                )
                result = self.run_command(install_cmd, elevated=bool(user))
                return CommandResult(
                    **{
                        "success": result["success"],
                        "removed": removed,
                        "message": (
                            f"Removed {len(removed)} cron job(s)"
                            if result["success"]
                            else "Failed"
                        ),
                    }
                )
            finally:
                os.remove(tmp_path)
        except Exception as e:
            return CommandResult(**{"success": False, "error": str(e)})

    def get_firewall_status(self) -> CommandResult:
        try:
            if platform.system() == "Linux":
                if shutil.which("ufw"):
                    r = self.run_command(["ufw", "status", "verbose"], elevated=True)
                    return CommandResult(
                        **{
                            "success": r["success"],
                            "tool": "ufw",
                            "output": r.get("stdout", ""),
                        }
                    )
                if shutil.which("firewall-cmd"):
                    r = self.run_command(["firewall-cmd", "--state"], elevated=True)
                    return CommandResult(
                        **{
                            "success": r["success"],
                            "tool": "firewalld",
                            "output": r.get("stdout", ""),
                        }
                    )
                r = self.run_command(
                    ["iptables", "-L", "-n", "--line-numbers"], elevated=True
                )
                return CommandResult(
                    **{
                        "success": r["success"],
                        "tool": "iptables",
                        "output": r.get("stdout", ""),
                    }
                )
            elif platform.system() == "Windows":
                r = self.run_command(
                    ["netsh", "advfirewall", "show", "allprofiles"],
                    shell=True,  # nosec
                )  # nosec
                return CommandResult(
                    **{
                        "success": r["success"],
                        "tool": "netsh",
                        "output": r.get("stdout", ""),
                    }
                )
            return CommandResult(
                **{"success": False, "error": f"Unsupported OS: {platform.system()}"}
            )
        except Exception as e:
            return CommandResult(**{"success": False, "error": str(e)})

    def list_firewall_rules(self) -> CommandResult:
        try:
            if platform.system() == "Linux":
                if shutil.which("ufw"):
                    r = self.run_command(["ufw", "status", "numbered"], elevated=True)
                    return CommandResult(
                        **{
                            "success": r["success"],
                            "tool": "ufw",
                            "output": r.get("stdout", ""),
                        }
                    )
                if shutil.which("firewall-cmd"):
                    r = self.run_command(["firewall-cmd", "--list-all"], elevated=True)
                    return CommandResult(
                        **{
                            "success": r["success"],
                            "tool": "firewalld",
                            "output": r.get("stdout", ""),
                        }
                    )
                r = self.run_command(
                    ["iptables", "-L", "-n", "-v", "--line-numbers"], elevated=True
                )
                return CommandResult(
                    **{
                        "success": r["success"],
                        "tool": "iptables",
                        "output": r.get("stdout", ""),
                    }
                )
            elif platform.system() == "Windows":
                r = self.run_command(
                    [
                        "powershell.exe",
                        "-Command",
                        "Get-NetFirewallRule | Select-Object Name,DisplayName,Enabled,Direction,Action "
                        "| ConvertTo-Json -Depth 3",
                    ],
                    shell=True,  # nosec
                )
                if r["success"]:
                    try:
                        rules = json.loads(r.get("stdout", "[]"))
                        if isinstance(rules, dict):
                            rules = [rules]
                        return CommandResult(
                            **{
                                "success": True,
                                "tool": "netsh",
                                "rules": rules,
                                "total": len(rules),
                            }
                        )
                    except json.JSONDecodeError:
                        pass
                return CommandResult(
                    **{
                        "success": r["success"],
                        "tool": "netsh",
                        "output": r.get("stdout", ""),
                    }
                )
            return CommandResult(
                **{"success": False, "error": f"Unsupported OS: {platform.system()}"}
            )
        except Exception as e:
            return CommandResult(**{"success": False, "error": str(e)})

    def add_firewall_rule(self, rule: str) -> CommandResult:
        try:
            if platform.system() == "Linux":
                if shutil.which("ufw"):
                    r = self.run_command(["ufw"] + rule.split(), elevated=True)
                    return CommandResult(
                        **{"success": r["success"], "tool": "ufw", "details": r}
                    )
                if shutil.which("firewall-cmd"):
                    r = self.run_command(["firewall-cmd"] + rule.split(), elevated=True)
                    return CommandResult(
                        **{"success": r["success"], "tool": "firewalld", "details": r}
                    )
                r = self.run_command(["iptables"] + rule.split(), elevated=True)
                return CommandResult(
                    **{"success": r["success"], "tool": "iptables", "details": r}
                )
            elif platform.system() == "Windows":
                r = self.run_command(
                    ["netsh", "advfirewall", "firewall", "add", "rule"] + rule.split(),
                    shell=True,  # nosec
                    elevated=True,
                )
                return CommandResult(
                    **{"success": r["success"], "tool": "netsh", "details": r}
                )
            return CommandResult(
                **{"success": False, "error": f"Unsupported OS: {platform.system()}"}
            )
        except Exception as e:
            return CommandResult(**{"success": False, "error": str(e)})

    def remove_firewall_rule(self, rule: str) -> CommandResult:
        try:
            if platform.system() == "Linux":
                if shutil.which("ufw"):
                    r = self.run_command(
                        ["ufw", "delete"] + rule.split(), elevated=True
                    )
                    return CommandResult(
                        **{"success": r["success"], "tool": "ufw", "details": r}
                    )
                if shutil.which("firewall-cmd"):
                    r = self.run_command(
                        ["firewall-cmd", "--remove-" + rule], elevated=True
                    )
                    return CommandResult(
                        **{"success": r["success"], "tool": "firewalld", "details": r}
                    )
                r = self.run_command(["iptables", "-D"] + rule.split(), elevated=True)
                return CommandResult(
                    **{"success": r["success"], "tool": "iptables", "details": r}
                )
            elif platform.system() == "Windows":
                r = self.run_command(
                    ["netsh", "advfirewall", "firewall", "delete", "rule"]
                    + rule.split(),
                    shell=True,  # nosec
                    elevated=True,
                )
                return CommandResult(
                    **{"success": r["success"], "tool": "netsh", "details": r}
                )
            return CommandResult(
                **{"success": False, "error": f"Unsupported OS: {platform.system()}"}
            )
        except Exception as e:
            return CommandResult(**{"success": False, "error": str(e)})

    def list_ssh_keys(self) -> CommandResult:
        try:
            ssh_dir = os.path.expanduser("~/.ssh")
            if not os.path.exists(ssh_dir):
                return CommandResult(
                    **{
                        "success": True,
                        "keys": [],
                        "message": "No .ssh directory found",
                    }
                )
            keys = []
            for filename in os.listdir(ssh_dir):
                filepath = os.path.join(ssh_dir, filename)
                if os.path.isfile(filepath):
                    stat = os.stat(filepath)
                    keys.append(
                        {
                            "filename": filename,
                            "path": filepath,
                            "is_public": filename.endswith(".pub"),
                            "size": stat.st_size,
                            "permissions": oct(stat.st_mode)[-3:],
                        }
                    )
            return CommandResult(**{"success": True, "keys": keys, "total": len(keys)})
        except Exception as e:
            return CommandResult(**{"success": False, "error": str(e)})

    def generate_ssh_key(
        self,
        key_type: str = "ed25519",
        comment: str = "",
        passphrase: str = "",  # nosec
    ) -> CommandResult:
        try:
            ssh_dir = os.path.expanduser("~/.ssh")
            os.makedirs(ssh_dir, exist_ok=True)
            key_path = os.path.join(ssh_dir, f"id_{key_type}")
            if os.path.exists(key_path):
                return CommandResult(
                    **{"success": False, "error": f"Key already exists: {key_path}"}
                )
            result = self.run_command(
                [
                    "ssh-keygen",
                    "-t",
                    key_type,
                    "-f",
                    key_path,
                    "-N",
                    passphrase,
                    "-C",
                    comment,
                ]
            )
            return CommandResult(
                **{
                    "success": result["success"],
                    "key_path": key_path,
                    "public_key_path": f"{key_path}.pub",
                    "details": result,
                }
            )
        except Exception as e:
            return CommandResult(**{"success": False, "error": str(e)})

    def add_authorized_key(self, public_key: str) -> CommandResult:
        try:
            ssh_dir = os.path.expanduser("~/.ssh")
            os.makedirs(ssh_dir, exist_ok=True)
            auth_keys = os.path.join(ssh_dir, "authorized_keys")
            if os.path.exists(auth_keys):
                with open(auth_keys) as f:
                    if public_key.strip() in f.read():
                        return CommandResult(
                            **{
                                "success": True,
                                "message": "Key already exists in authorized_keys",
                            }
                        )
            with open(auth_keys, "a") as f:
                f.write(public_key.strip() + "\n")
            os.chmod(auth_keys, 0o600)
            return CommandResult(
                **{"success": True, "message": "Public key added to authorized_keys"}
            )
        except Exception as e:
            return CommandResult(**{"success": False, "error": str(e)})

    def list_env_vars(self) -> CommandResult:
        return CommandResult(
            **{
                "success": True,
                "variables": dict(os.environ),
                "total": len(os.environ),
            }
        )

    def get_env_var(self, name: str) -> CommandResult:
        value = os.environ.get(name)
        if value is None:
            return CommandResult(
                **{
                    "success": False,
                    "error": f"Environment variable '{name}' not found",
                }
            )
        return CommandResult(**{"success": True, "name": name, "value": value})

    def clean_temp_files(self) -> CommandResult:
        try:
            temp_dir = tempfile.gettempdir()
            cleaned, errors = 0, 0
            for item in os.listdir(temp_dir):
                item_path = os.path.join(temp_dir, item)
                try:
                    if os.path.isfile(item_path):
                        os.remove(item_path)
                    elif os.path.isdir(item_path):
                        shutil.rmtree(item_path, ignore_errors=True)
                    cleaned += 1
                except (PermissionError, OSError):
                    errors += 1
            return CommandResult(
                **{
                    "success": True,
                    "temp_dir": temp_dir,
                    "cleaned": cleaned,
                    "errors": errors,
                }
            )
        except Exception as e:
            return CommandResult(**{"success": False, "error": str(e)})

    def get_disk_space_report(self, path: str = "/", top_n: int = 10) -> CommandResult:
        try:
            if platform.system() == "Linux":
                result = self.run_command(
                    ["du", "-h", "--max-depth=1", path, "--threshold=100M"],
                    elevated=True,
                )
                if result["success"]:
                    entries = []
                    for line in (result.get("stdout") or "").strip().splitlines():
                        parts = line.split(None, 1)
                        if len(parts) == 2:
                            entries.append({"size": parts[0], "path": parts[1]})
                    entries.sort(key=lambda x: x["size"], reverse=True)
                    return CommandResult(
                        **{
                            "success": True,
                            "entries": entries[:top_n],
                            "base_path": path,
                        }
                    )
                return result
            elif platform.system() == "Windows":
                ps_cmd = (
                    f"Get-ChildItem '{path}' -Directory | ForEach-Object {{ $s = "
                    f"(Get-ChildItem $_.FullName -Recurse -File -EA SilentlyContinue "
                    f"| Measure-Object Length -Sum).Sum; [PSCustomObject]@{{Path=$_.FullName; "
                    f"SizeGB=[math]::Round($s/1GB,2)}} }} | Sort-Object SizeGB -Desc "
                    f"| Select-Object -First {top_n} | ConvertTo-Json"
                )
                result = self.run_command(
                    ["powershell.exe", "-Command", ps_cmd],
                    shell=True,  # nosec
                )  # nosec
                if result["success"]:
                    try:
                        entries = json.loads(result.get("stdout", "[]"))
                        if isinstance(entries, dict):
                            entries = [entries]
                        return CommandResult(
                            **{"success": True, "entries": entries, "base_path": path}
                        )
                    except json.JSONDecodeError:
                        pass
                return CommandResult(
                    **{
                        "success": result["success"],
                        "output": result.get("stdout", ""),
                    }
                )
            return CommandResult(
                **{"success": False, "error": f"Unsupported OS: {platform.system()}"}
            )
        except Exception as e:
            return CommandResult(**{"success": False, "error": str(e)})


class AptManager(SystemsManagerBase):
    def __init__(
        self,
        host: str | None = None,
        silent: bool = False,
        log_file: str | None = None,
    ):
        super().__init__(host, silent, log_file)
        self.not_found_msg = "Unable to locate package"

    def install_applications(self, apps: list[str]) -> CommandResult:
        results = {
            "natively_installed": [],
            "snap_installed": [],
            "failed": [],
            "success": True,
        }
        if self.host is None:
            res = self.run_elevated_tool("package", "update")
            update_result = CommandResult(
                success=res.get("success", False),
                stdout=res.get("stdout"),
                stderr=res.get("stderr"),
                error=res.get("error"),
                command="sudo systems-manager-helper package update",
            )
        else:
            update_result = self.run_command(["apt", "update"], elevated=True)

        if not update_result["success"]:
            results["success"] = False
            results["update_error"] = update_result.get("error")
            self.logger.error("apt update failed")

        for app in apps:
            if self.host is None:
                res = self.run_elevated_tool("package", "install", app)
                install_result = CommandResult(
                    success=res.get("success", False),
                    stdout=res.get("stdout"),
                    stderr=res.get("stderr"),
                    error=res.get("error"),
                    command=f"sudo systems-manager-helper package install {app}",
                )
            else:
                install_result = self.run_command(
                    ["apt", "install", "-y", app], elevated=True
                )

            if install_result["success"]:
                results["natively_installed"].append(app)  # type: ignore
            else:
                if self.not_found_msg in install_result.get("stderr", ""):
                    if not self.silent:
                        print(f"Falling back to Snap for {app}...", file=sys.stderr)
                    self.logger.info(
                        f"Native install failed for {app}; falling back to Snap..."
                    )
                    snap_result = self.install_via_snap(app)
                    if snap_result["success"]:
                        results["snap_installed"].append(app)  # type: ignore
                    else:
                        results["failed"].append(app)  # type: ignore
                        results["success"] = False
                        self.logger.error(
                            f"Snap install failed for {app}: {snap_result.get('error')}"
                        )
                else:
                    results["failed"].append(app)  # type: ignore
                    results["success"] = False
                    self.logger.error(
                        f"Native install failed for {app}: {install_result.get('error')}"
                    )
        return results  # type: ignore

    def update(self) -> CommandResult:
        try:
            if self.host is None:
                res = self.run_elevated_tool("package", "update")
                update_result = CommandResult(
                    success=res.get("success", False),
                    stdout=res.get("stdout"),
                    stderr=res.get("stderr"),
                    error=res.get("error"),
                    command="sudo systems-manager-helper package update",
                )
            else:
                update_result = self.run_command(["apt", "update"], elevated=True)

            if not update_result["success"]:
                return CommandResult(
                    **{
                        "success": False,
                        "error": "apt update failed",
                        "details": update_result,
                    }
                )

            if self.host is None:
                res = self.run_elevated_tool("package", "upgrade")
                upgrade_result = CommandResult(
                    success=res.get("success", False),
                    stdout=res.get("stdout"),
                    stderr=res.get("stderr"),
                    error=res.get("error"),
                    command="sudo systems-manager-helper package upgrade",
                )
            else:
                upgrade_result = self.run_command(
                    ["apt", "upgrade", "-y"], elevated=True
                )

            if not upgrade_result["success"]:
                return CommandResult(
                    **{
                        "success": False,
                        "error": "apt upgrade failed",
                        "details": upgrade_result,
                    }
                )
            return CommandResult(
                **{"success": True, "message": "System and packages updated"}
            )
        except Exception as e:
            self.logger.error(f"Unexpected error in update: {e}")
            return CommandResult(**{"success": False, "error": str(e)})

    def clean(self) -> CommandResult:
        if self.host is None:
            res = self.run_elevated_tool("package", "install", "trash-cli")
            install_result = CommandResult(
                success=res.get("success", False),
                stdout=res.get("stdout"),
                stderr=res.get("stderr"),
                error=res.get("error"),
                command="sudo systems-manager-helper package install trash-cli",
            )
        else:
            install_result = self.run_command(
                ["apt", "install", "-y", "trash-cli"], elevated=True
            )

        if not install_result["success"]:
            self.logger.warning("Failed to install trash-cli")
        empty_result = self.run_command(["trash-empty"])
        if empty_result["success"]:
            return CommandResult(**{"success": True, "message": "Trash emptied"})
        else:
            return CommandResult(
                **{
                    "success": False,
                    "error": "Failed to empty trash",
                    "details": empty_result,
                }
            )

    def optimize(self) -> CommandResult:
        if self.host is None:
            res_remove = self.run_elevated_tool("package", "autoremove")
            autoremove_result = CommandResult(
                success=res_remove.get("success", False),
                stdout=res_remove.get("stdout"),
                stderr=res_remove.get("stderr"),
                error=res_remove.get("error"),
                command="sudo systems-manager-helper package autoremove",
            )
            res_clean = self.run_elevated_tool("package", "autoclean")
            autoclean_result = CommandResult(
                success=res_clean.get("success", False),
                stdout=res_clean.get("stdout"),
                stderr=res_clean.get("stderr"),
                error=res_clean.get("error"),
                command="sudo systems-manager-helper package autoclean",
            )
        else:
            autoremove_result = self.run_command(
                ["apt", "autoremove", "-y"], elevated=True
            )
            autoclean_result = self.run_command(["apt", "autoclean"], elevated=True)

        overall_success = autoremove_result["success"] and autoclean_result["success"]
        return CommandResult(
            **{
                "success": overall_success,
                "message": (
                    "System optimized" if overall_success else "Partial optimization"
                ),
                "details": {
                    "autoremove": autoremove_result,
                    "autoclean": autoclean_result,
                },
            }
        )

    def install_snapd(self) -> CommandResult:
        if self.host is None:
            res = self.run_elevated_tool("package", "install", "snapd")
            result = CommandResult(
                success=res.get("success", False),
                stdout=res.get("stdout"),
                stderr=res.get("stderr"),
                error=res.get("error"),
                command="sudo systems-manager-helper package install snapd",
            )
        else:
            result = self.run_command(["apt", "install", "-y", "snapd"], elevated=True)
        return CommandResult(
            **{
                "success": result["success"],
                "details": result,
                "message": (
                    "snapd installed"
                    if result["success"]
                    else "Failed to install snapd"
                ),
            }
        )

    def add_repository(self, repo_url: str, name: str | None = None) -> CommandResult:
        add_result = self.run_command(
            ["add-apt-repository", "-y", repo_url], elevated=True
        )
        if add_result["success"]:
            update_result = self.run_command(["apt", "update"], elevated=True)
            return CommandResult(
                **{
                    "success": update_result["success"],
                    "details": [add_result, update_result],
                }
            )
        return add_result

    def install_local_package(self, file_path: str) -> CommandResult:
        if not file_path.endswith(".deb"):
            return CommandResult(**{"success": False, "error": "Not a .deb file"})
        install_result = self.run_command(["dpkg", "-i", file_path], elevated=True)
        if install_result["success"]:
            fix_result = self.run_command(["apt", "install", "-f", "-y"], elevated=True)
            return CommandResult(
                **{
                    "success": fix_result["success"],
                    "details": [install_result, fix_result],
                }
            )
        return install_result

    def search_package(self, query: str):
        result = self.run_command(["apt-cache", "search", query])
        packages: list[dict[str, Any]] = []
        if result["success"]:
            for line in (result.get("stdout") or "").strip().splitlines():
                parts = line.split(" - ", 1)
                if len(parts) == 2:
                    packages.append(
                        {"name": parts[0].strip(), "description": parts[1].strip()}
                    )
        return CommandResult(
            **{
                "success": result["success"],
                "packages": packages,
                "total": len(packages),
            }
        )

    def get_package_info(self, package: str):
        result = self.run_command(["apt-cache", "show", package])
        return CommandResult(
            **{"success": result["success"], "info": result.get("stdout", "")}
        )

    def list_installed_packages(self):
        result = self.run_command(["dpkg", "--get-selections"])
        packages: list[dict[str, Any]] = []
        if result["success"]:
            for line in (result.get("stdout") or "").strip().splitlines():
                parts = line.split()
                if len(parts) >= 2 and parts[1] == "install":
                    packages.append(parts[0])  # type: ignore
        return CommandResult(
            **{
                "success": result["success"],
                "packages": packages,
                "total": len(packages),
            }
        )

    def list_upgradable_packages(self):
        self.run_command(["apt", "update"], elevated=True)
        result = self.run_command(["apt", "list", "--upgradable"])
        packages: list[dict[str, Any]] = []
        if result["success"]:
            for line in (result.get("stdout") or "").strip().splitlines():
                if "/" in line and "Listing" not in line:
                    packages.append(line.split("/")[0])  # type: ignore
        return CommandResult(
            **{
                "success": result["success"],
                "packages": packages,
                "total": len(packages),
            }
        )

    def clean_package_cache(self):
        result = self.run_command(["apt-get", "clean"], elevated=True)
        return CommandResult(
            **{
                "success": result["success"],
                "message": "APT cache cleaned" if result["success"] else "Failed",
            }
        )


class DnfManager(SystemsManagerBase):
    def __init__(
        self,
        host: str | None = None,
        silent: bool = False,
        log_file: str | None = None,
    ):
        super().__init__(host, silent, log_file)
        self.not_found_msg = "Unable to find a match"

    def install_applications(self, apps: list[str]) -> CommandResult:
        results = {
            "natively_installed": [],
            "snap_installed": [],
            "failed": [],
            "success": True,
        }
        update_result = self.run_command(["dnf", "update", "-y"], elevated=True)
        if not update_result["success"]:
            self.logger.warning("dnf update failed before installs")
        for app in apps:
            install_result = self.run_command(
                ["dnf", "install", "-y", app], elevated=True
            )
            if install_result["success"]:
                results["natively_installed"].append(app)  # type: ignore
            else:
                if self.not_found_msg in install_result.get("stderr", ""):
                    if not self.silent:
                        print(f"Falling back to Snap for {app}...", file=sys.stderr)
                    self.logger.info(
                        f"Native install failed for {app}; falling back to Snap..."
                    )
                    snap_result = self.install_via_snap(app)
                    if snap_result["success"]:
                        results["snap_installed"].append(app)  # type: ignore
                    else:
                        results["failed"].append(app)  # type: ignore
                        results["success"] = False
                else:
                    results["failed"].append(app)  # type: ignore
                    results["success"] = False
        return results  # type: ignore

    def update(self) -> CommandResult:
        result = self.run_command(["dnf", "update", "-y"], elevated=True)
        return CommandResult(
            **{
                "success": result["success"],
                "message": "System updated" if result["success"] else "Update failed",
                "details": result,
            }
        )

    def clean(self) -> CommandResult:
        result = self.run_command(["dnf", "clean", "all"], elevated=True)
        return CommandResult(
            **{
                "success": result["success"],
                "message": "Cache cleaned" if result["success"] else "Clean failed",
                "details": result,
            }
        )

    def optimize(self) -> CommandResult:
        result = self.run_command(["dnf", "autoremove", "-y"], elevated=True)
        return CommandResult(
            **{
                "success": result["success"],
                "message": (
                    "Orphans removed" if result["success"] else "Optimize failed"
                ),
                "details": result,
            }
        )

    def install_snapd(self) -> CommandResult:
        result = self.run_command(["dnf", "install", "-y", "snapd"], elevated=True)
        return CommandResult(
            **{
                "success": result["success"],
                "details": result,
                "message": (
                    "snapd installed"
                    if result["success"]
                    else "Failed to install snapd"
                ),
            }
        )

    def add_repository(self, repo_url: str, name: str | None = None) -> CommandResult:
        command = ["dnf", "config-manager", "--add-repo", repo_url]
        add_result = self.run_command(command, elevated=True)
        if add_result["success"]:
            update_result = self.run_command(["dnf", "makecache"], elevated=True)
            return CommandResult(
                **{
                    "success": update_result["success"],
                    "details": [add_result, update_result],
                }
            )
        return add_result

    def install_local_package(self, file_path: str) -> CommandResult:
        if not file_path.endswith(".rpm"):
            return CommandResult(**{"success": False, "error": "Not a .rpm file"})
        return self.run_command(["dnf", "install", "-y", file_path], elevated=True)

    def search_package(self, query: str):
        result = self.run_command(["dnf", "search", query])
        packages: list[dict[str, Any]] = []
        if result["success"]:
            for line in (result.get("stdout") or "").strip().splitlines():
                parts = line.split(" : ", 1)
                if len(parts) == 2 and not line.startswith("="):
                    packages.append(
                        {
                            "name": parts[0].strip().split(".")[0],
                            "description": parts[1].strip(),
                        }
                    )
        return CommandResult(
            **{
                "success": result["success"],
                "packages": packages,
                "total": len(packages),
            }
        )

    def get_package_info(self, package: str):
        result = self.run_command(["dnf", "info", package])
        return CommandResult(
            **{"success": result["success"], "info": result.get("stdout", "")}
        )

    def list_installed_packages(self):
        result = self.run_command(["dnf", "list", "installed"])
        packages: list[dict[str, Any]] = []
        if result["success"]:
            for line in (result.get("stdout") or "").strip().splitlines():
                if not line.startswith("Installed") and not line.startswith("Last"):
                    parts = line.split()
                    if parts:
                        packages.append(parts[0].split(".")[0])  # type: ignore
        return CommandResult(
            **{
                "success": result["success"],
                "packages": packages,
                "total": len(packages),
            }
        )

    def list_upgradable_packages(self):
        result = self.run_command(["dnf", "check-update"])
        packages: list[dict[str, Any]] = []
        if result.get("stdout"):
            for line in result["stdout"].strip().splitlines():
                parts = line.split()
                if len(parts) >= 3 and "." in parts[0]:
                    packages.append(parts[0].split(".")[0])
        return CommandResult(
            **{"success": True, "packages": packages, "total": len(packages)}
        )

    def clean_package_cache(self):
        result = self.run_command(["dnf", "clean", "all"], elevated=True)
        return CommandResult(
            **{
                "success": result["success"],
                "message": "DNF cache cleaned" if result["success"] else "Failed",
            }
        )


class ZypperManager(SystemsManagerBase):
    def __init__(
        self,
        host: str | None = None,
        silent: bool = False,
        log_file: str | None = None,
    ):
        super().__init__(host, silent, log_file)
        self.not_found_msg = "No provider of"

    def install_applications(self, apps: list[str]) -> CommandResult:
        results = {
            "natively_installed": [],
            "snap_installed": [],
            "failed": [],
            "success": True,
        }
        for app in apps:
            install_result = self.run_command(
                ["zypper", "install", "-y", app], elevated=True
            )
            if install_result["success"]:
                results["natively_installed"].append(app)  # type: ignore
            else:
                if self.not_found_msg in install_result.get("stderr", ""):
                    if not self.silent:
                        print(f"Falling back to Snap for {app}...", file=sys.stderr)
                    self.logger.info(
                        f"Native install failed for {app}; falling back to Snap..."
                    )
                    snap_result = self.install_via_snap(app)
                    if snap_result["success"]:
                        results["snap_installed"].append(app)  # type: ignore
                    else:
                        results["failed"].append(app)  # type: ignore
                        results["success"] = False
                else:
                    results["failed"].append(app)  # type: ignore
                    results["success"] = False
        return results  # type: ignore

    def update(self) -> CommandResult:
        result = self.run_command(["zypper", "update", "-y"], elevated=True)
        return CommandResult(
            **{
                "success": result["success"],
                "message": "System updated" if result["success"] else "Update failed",
                "details": result,
            }
        )

    def clean(self) -> CommandResult:
        result = self.run_command(["zypper", "clean", "--all"], elevated=True)
        return CommandResult(
            **{
                "success": result["success"],
                "message": "Cache cleaned" if result["success"] else "Clean failed",
                "details": result,
            }
        )

    def optimize(self) -> CommandResult:
        result = self.run_command(["zypper", "rm", "-u"], elevated=True)
        return CommandResult(
            **{
                "success": result["success"],
                "message": (
                    "Unneeded removed" if result["success"] else "Optimize failed"
                ),
                "details": result,
            }
        )

    def install_snapd(self) -> CommandResult:
        result = self.run_command(["zypper", "install", "-y", "snapd"], elevated=True)
        return CommandResult(
            **{
                "success": result["success"],
                "details": result,
                "message": (
                    "snapd installed"
                    if result["success"]
                    else "Failed to install snapd"
                ),
            }
        )

    def add_repository(self, repo_url: str, name: str | None = None) -> CommandResult:
        if not name:
            name = "custom"
        add_result = self.run_command(
            ["zypper", "addrepo", repo_url, name], elevated=True
        )
        if add_result["success"]:
            refresh_result = self.run_command(["zypper", "refresh"], elevated=True)
            return CommandResult(
                **{
                    "success": refresh_result["success"],
                    "details": [add_result, refresh_result],
                }
            )
        return add_result

    def install_local_package(self, file_path: str) -> CommandResult:
        if not file_path.endswith(".rpm"):
            return CommandResult(**{"success": False, "error": "Not a .rpm file"})
        return self.run_command(["zypper", "install", "-y", file_path], elevated=True)

    def search_package(self, query: str):
        result = self.run_command(["zypper", "search", query])
        packages: list[dict[str, Any]] = []
        if result["success"]:
            for line in (result.get("stdout") or "").strip().splitlines():
                parts = line.split("|")
                if len(parts) >= 3 and parts[0].strip() not in ("S", "-", ""):
                    packages.append(
                        {
                            "name": parts[1].strip(),
                            "description": parts[2].strip() if len(parts) > 2 else "",
                        }
                    )
        return CommandResult(
            **{
                "success": result["success"],
                "packages": packages,
                "total": len(packages),
            }
        )

    def get_package_info(self, package: str):
        result = self.run_command(["zypper", "info", package])
        return CommandResult(
            **{"success": result["success"], "info": result.get("stdout", "")}
        )

    def list_installed_packages(self):
        result = self.run_command(["zypper", "search", "--installed-only"])
        packages: list[dict[str, Any]] = []
        if result["success"]:
            for line in (result.get("stdout") or "").strip().splitlines():
                parts = line.split("|")
                if len(parts) >= 2 and parts[0].strip() == "i":
                    packages.append(parts[1].strip())  # type: ignore
        return CommandResult(
            **{
                "success": result["success"],
                "packages": packages,
                "total": len(packages),
            }
        )

    def list_upgradable_packages(self):
        result = self.run_command(["zypper", "list-updates"])
        packages: list[dict[str, Any]] = []
        if result["success"]:
            for line in (result.get("stdout") or "").strip().splitlines():
                parts = line.split("|")
                if len(parts) >= 3 and parts[0].strip() not in ("S", "-", "", "v"):
                    packages.append(
                        parts[2].strip() if len(parts) > 2 else parts[1].strip()  # type: ignore
                    )
        return CommandResult(
            **{
                "success": result["success"],
                "packages": packages,
                "total": len(packages),
            }
        )

    def clean_package_cache(self):
        result = self.run_command(["zypper", "clean", "--all"], elevated=True)
        return CommandResult(
            **{
                "success": result["success"],
                "message": "Zypper cache cleaned" if result["success"] else "Failed",
            }
        )


class PacmanManager(SystemsManagerBase):
    def __init__(
        self,
        host: str | None = None,
        silent: bool = False,
        log_file: str | None = None,
    ):
        super().__init__(host, silent, log_file)
        self.not_found_msg = "target not found"

    def install_applications(self, apps: list[str]) -> CommandResult:
        results = {
            "natively_installed": [],
            "snap_installed": [],
            "failed": [],
            "success": True,
        }
        for app in apps:
            install_result = self.run_command(
                ["pacman", "-S", "--noconfirm", app], elevated=True
            )
            if install_result["success"]:
                results["natively_installed"].append(app)  # type: ignore
            else:
                if self.not_found_msg in install_result.get("stderr", ""):
                    if not self.silent:
                        print(f"Falling back to Snap for {app}...", file=sys.stderr)
                    self.logger.info(
                        f"Native install failed for {app}; falling back to Snap..."
                    )
                    snap_result = self.install_via_snap(app)
                    if snap_result["success"]:
                        results["snap_installed"].append(app)  # type: ignore
                    else:
                        results["failed"].append(app)  # type: ignore
                        results["success"] = False
                else:
                    results["failed"].append(app)  # type: ignore
                    results["success"] = False
        return results  # type: ignore

    def update(self) -> CommandResult:
        result = self.run_command(["pacman", "-Syu", "--noconfirm"], elevated=True)
        return CommandResult(
            **{
                "success": result["success"],
                "message": "System updated" if result["success"] else "Update failed",
                "details": result,
            }
        )

    def clean(self) -> CommandResult:
        result = self.run_command(["pacman", "-Sc", "--noconfirm"], elevated=True)
        return CommandResult(
            **{
                "success": result["success"],
                "message": "Cache cleaned" if result["success"] else "Clean failed",
                "details": result,
            }
        )

    def optimize(self) -> CommandResult:
        orphans_cmd = ["pacman", "-Rns", "$(pacman -Qdtq)", "--noconfirm"]
        result = self.run_command(orphans_cmd, elevated=True, shell=True)  # nosec
        return CommandResult(
            **{
                "success": result["success"],
                "message": (
                    "Orphans removed" if result["success"] else "Optimize failed"
                ),
                "details": result,
            }
        )

    def install_snapd(self) -> CommandResult:
        result = self.run_command(
            ["pacman", "-S", "--noconfirm", "snapd"], elevated=True
        )
        return CommandResult(
            **{
                "success": result["success"],
                "details": result,
                "message": (
                    "snapd installed"
                    if result["success"]
                    else "Failed to install snapd"
                ),
            }
        )

    def add_repository(self, repo_url: str, name: str | None = None) -> CommandResult:
        if not name:
            name = "custom"
        conf = "/etc/pacman.conf"
        content = f"\n[{name}]\nServer = {repo_url}\n"
        echo_cmd = ["bash", "-c", f"echo '{content}' >> {conf}"]
        add_result = self.run_command(echo_cmd, elevated=True, shell=True)  # nosec
        if add_result["success"]:
            sync_result = self.run_command(
                ["pacman", "-Sy", "--noconfirm"], elevated=True
            )
            return CommandResult(
                **{
                    "success": sync_result["success"],
                    "details": [add_result, sync_result],
                }
            )
        return add_result

    def install_local_package(self, file_path: str) -> CommandResult:
        return self.run_command(
            ["pacman", "-U", "--noconfirm", file_path], elevated=True
        )

    def search_package(self, query: str):
        result = self.run_command(["pacman", "-Ss", query])
        packages: list[dict[str, Any]] = []
        if result["success"]:
            lines = (result.get("stdout") or "").strip().splitlines()
            for i in range(0, len(lines), 2):
                name_line = lines[i].strip()
                desc = lines[i + 1].strip() if i + 1 < len(lines) else ""
                parts = name_line.split("/", 1)
                if len(parts) == 2:
                    pkg_name = parts[1].split()[0]
                    packages.append({"name": pkg_name, "description": desc})
        return CommandResult(
            **{
                "success": result["success"],
                "packages": packages,
                "total": len(packages),
            }
        )

    def get_package_info(self, package: str):
        result = self.run_command(["pacman", "-Si", package])
        if not result["success"]:
            result = self.run_command(["pacman", "-Qi", package])
        return CommandResult(
            **{"success": result["success"], "info": result.get("stdout", "")}
        )

    def list_installed_packages(self):
        result = self.run_command(["pacman", "-Qq"])
        packages: list[dict[str, Any]] = []
        if result["success"]:
            packages = [
                p.strip()  # type: ignore
                for p in (result.get("stdout") or "").strip().splitlines()
                if p.strip()
            ]
        return CommandResult(
            **{
                "success": result["success"],
                "packages": packages,
                "total": len(packages),
            }
        )

    def list_upgradable_packages(self):
        result = self.run_command(["pacman", "-Qu"])
        packages: list[dict[str, Any]] = []
        if result["success"]:
            for line in (result.get("stdout") or "").strip().splitlines():
                parts = line.split()
                if parts:
                    packages.append(parts[0])  # type: ignore
        return CommandResult(
            **{
                "success": result["success"],
                "packages": packages,
                "total": len(packages),
            }
        )

    def clean_package_cache(self):
        result = self.run_command(["pacman", "-Sc", "--noconfirm"], elevated=True)
        return CommandResult(
            **{
                "success": result["success"],
                "message": "Pacman cache cleaned" if result["success"] else "Failed",
            }
        )


class WindowsManager(SystemsManagerBase):
    def __init__(
        self,
        host: str | None = None,
        silent: bool = False,
        log_file: str | None = None,
    ):
        super().__init__(host, silent, log_file)
        self.winget_bin = os.path.expanduser(
            r"~\AppData\Local\Microsoft\WindowsApps\winget.exe"
        )
        if not os.path.exists(self.winget_bin):
            if not self.silent:
                print("Installing Winget...", file=sys.stderr)
            self.logger.info("Installing Winget...")
            register_result = self.run_command(
                [
                    "powershell.exe",
                    "-Command",
                    "Add-AppxPackage -RegisterByFamilyName -MainPackage Microsoft.DesktopAppInstaller_8wekyb3d8bbwe",
                ]
            )
            if not register_result["success"]:
                self.logger.error("Failed to register Winget")

    def install_applications(self, apps: list[str]) -> CommandResult:
        results = {"installed": [], "failed": [], "success": True}
        for app in apps:
            install_cmd = [
                "winget",
                "install",
                "--id",
                app,
                "--silent",
                "--accept-package-agreements",
                "--accept-source-agreements",
            ]
            install_result = self.run_command(install_cmd)
            if install_result["success"]:
                results["installed"].append(app)  # type: ignore
            else:
                results["failed"].append(app)  # type: ignore
                results["success"] = False
                self.logger.error(
                    f"Failed to install {app}: {install_result.get('error')}"
                )
        return results  # type: ignore

    def update(self) -> CommandResult:
        winget_result = self.run_command(
            [
                "winget",
                "upgrade",
                "--all",
                "--silent",
                "--accept-package-agreements",
                "--accept-source-agreements",
            ]
        )
        wu_cmd = [
            "powershell.exe",
            "-Command",
            "if (!(Get-Module -ListAvailable -Name PSWindowsUpdate)) { Install-Module PSWindowsUpdate -Force -Scope CurrentUser }; Import-Module PSWindowsUpdate; Get-WUList | Install-WUUpdate -AcceptAll -AutoReboot:$false",
        ]
        wu_result = self.run_command(wu_cmd, shell=True, elevated=True)  # nosec
        overall_success = winget_result["success"] and wu_result["success"]
        return CommandResult(
            **{
                "success": overall_success,
                "message": (
                    "System and apps updated" if overall_success else "Partial update"
                ),
                "details": {"winget": winget_result, "windows_update": wu_result},
            }
        )

    def clean(self) -> CommandResult:
        result = self.run_command(["cleanmgr", "/lowdisk"], shell=True)  # nosec
        return CommandResult(
            **{
                "success": result["success"],
                "message": (
                    "Cleanup initiated" if result["success"] else "Cleanup failed"
                ),
                "details": result,
            }
        )

    def optimize(self) -> CommandResult:
        clean_result = self.run_command(["cleanmgr", "/lowdisk"], shell=True)  # nosec
        defrag_result = self.run_command(
            ["powershell.exe", "Optimize-Volume", "-DriveLetter", "C", "-Verbose"],
            elevated=True,
        )
        overall_success = clean_result["success"] and defrag_result["success"]
        return CommandResult(
            **{
                "success": overall_success,
                "message": (
                    "System optimized" if overall_success else "Partial optimization"
                ),
                "details": {"cleanup": clean_result, "defrag": defrag_result},
            }
        )

    def list_windows_features(self) -> list[dict]:
        cmd = [
            "powershell.exe",
            "-Command",
            "Get-WindowsOptionalFeature -Online | ConvertTo-Json -Depth 3",
        ]
        result = self.run_command(cmd, shell=True)  # nosec
        if result["success"]:
            try:
                features = json.loads(result["stdout"])
                if isinstance(features, list):
                    return features
                else:
                    return [features]
            except json.JSONDecodeError:
                self.logger.error("Failed to parse features JSON")
                return []
        else:
            self.logger.error("Failed to list features")
            return []

    def enable_windows_features(self, features: list[str]) -> CommandResult:
        results = {"enabled": [], "failed": [], "success": True}
        for feature in features:
            cmd = [
                "powershell.exe",
                "Enable-WindowsOptionalFeature",
                "-Online",
                "-FeatureName",
                feature,
                "-NoRestart",
            ]
            enable_result = self.run_command(cmd, elevated=True)
            if enable_result["success"]:
                results["enabled"].append(feature)  # type: ignore
            else:
                results["failed"].append(feature)  # type: ignore
                results["success"] = False
                self.logger.error(
                    f"Failed to enable {feature}: {enable_result.get('error')}"
                )
        return results  # type: ignore

    def disable_windows_features(self, features: list[str]) -> CommandResult:
        results = {"disabled": [], "failed": [], "success": True}
        for feature in features:
            cmd = [
                "powershell.exe",
                "Disable-WindowsOptionalFeature",
                "-Online",
                "-FeatureName",
                feature,
                "-NoRestart",
            ]
            disable_result = self.run_command(cmd, elevated=True)
            if disable_result["success"]:
                results["disabled"].append(feature)  # type: ignore
            else:
                results["failed"].append(feature)  # type: ignore
                results["success"] = False
                self.logger.error(
                    f"Failed to disable {feature}: {disable_result.get('error')}"
                )
        return results  # type: ignore

    def install_snapd(self) -> CommandResult:
        return CommandResult(
            **{"success": False, "error": "Snap not supported on Windows"}
        )

    def add_repository(self, repo_url: str, name: str | None = None) -> CommandResult:
        return CommandResult(
            **{
                "success": False,
                "error": "Repository addition not supported on Windows",
            }
        )

    def install_local_package(self, file_path: str) -> CommandResult:
        return CommandResult(
            **{
                "success": False,
                "error": "Local package installation not supported on Windows",
            }
        )

    def search_package(self, query: str):
        result = self.run_command(
            [self.winget_bin, "search", query, "--accept-source-agreements"]
        )
        return CommandResult(
            **{"success": result["success"], "output": result.get("stdout", "")}
        )

    def get_package_info(self, package: str):
        result = self.run_command(
            [self.winget_bin, "show", package, "--accept-source-agreements"]
        )
        return CommandResult(
            **{"success": result["success"], "info": result.get("stdout", "")}
        )

    def list_installed_packages(self):
        result = self.run_command(
            [self.winget_bin, "list", "--accept-source-agreements"]
        )
        return CommandResult(
            **{"success": result["success"], "output": result.get("stdout", "")}
        )

    def list_upgradable_packages(self):
        result = self.run_command(
            [self.winget_bin, "upgrade", "--accept-source-agreements"]
        )
        return CommandResult(
            **{"success": result["success"], "output": result.get("stdout", "")}
        )

    def clean_package_cache(self):
        result = self.run_command(
            [
                "powershell.exe",
                "-Command",
                r"Remove-Item -Path $env:LOCALAPPDATA\Packages\Microsoft.DesktopAppInstaller_*\LocalState\DiagOutputDir\* -Recurse -Force -ErrorAction SilentlyContinue",
            ],
            shell=True,  # nosec
        )  # nosec
        return CommandResult(
            **{
                "success": True,
                "message": f"Windows package cache cleaned: \n{result}",
            }
        )


def detect_and_create_manager(
    host: str | None = None,
    silent: bool | None = False,
    log_file: str | None = None,
) -> SystemsManagerBase:
    """
    Detect the current operating system and return the appropriate SystemsManager instance.
    """
    silent_bool = bool(silent)

    if not host:
        host = os.environ.get("SYSTEMS_MANAGER_HOST", None)

    if host:
        from tunnel_manager.tunnel_manager import HostManager

        hm = HostManager()
        if host not in hm.hosts:
            raise ValueError(
                f"Host '{host}' not configured in inventory ({hm.config_file})"
            )
        hinfo = hm.hosts[host]

        hostname = hinfo.get("hostname")
        user = hinfo.get("user", "genius")
        port = hinfo.get("port", 22)
        identity_file = hinfo.get("key_path") or hinfo.get("identity_file")

        # Remote OS detection using SSH
        ssh_cmd = ["ssh", "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=5"]
        if identity_file:
            ssh_cmd.extend(["-i", os.path.expanduser(identity_file)])
        ssh_cmd.extend(
            [
                "-p",
                str(port),
                f"{user}@{hostname}",
                "uname -s && python3 -c 'import distro; print(distro.id())'",
            ]
        )

        try:
            res = subprocess.run(ssh_cmd, capture_output=True, text=True, timeout=6)
            if res.returncode != 0:
                if (
                    res.returncode == 255
                    or "timed out" in res.stderr.lower()
                    or "unreachable" in res.stderr.lower()
                ):
                    raise RuntimeError(
                        f"Host '{host}' is offline or unreachable via SSH: {res.stderr.strip() or 'Connection timed out'}"
                    )
                # Fallback to pure shell detection if python/distro not installed on remote
                ssh_cmd[-1] = "uname -s"
                res = subprocess.run(ssh_cmd, capture_output=True, text=True, timeout=6)
                if res.returncode != 0:
                    raise RuntimeError(
                        f"Host '{host}' is offline or unreachable via SSH: {res.stderr.strip()}"
                    )
                sys_name = res.stdout.strip()
                dist_id = "ubuntu"  # Default fallback for Linux
            else:
                lines = res.stdout.strip().split("\n")
                sys_name = lines[0].strip()
                dist_id = lines[1].strip() if len(lines) > 1 else "ubuntu"
        except subprocess.TimeoutExpired as e:
            raise RuntimeError(
                f"Host '{host}' is offline or connection timed out."
            ) from e
        except Exception as e:
            if isinstance(e, RuntimeError):
                raise
            raise RuntimeError(
                f"Failed to connect to remote host '{host}': {str(e)}"
            ) from e
    else:
        sys_name = platform.system()
        dist_id = distro.id() if sys_name == "Linux" else ""

    if sys_name == "Windows":
        return WindowsManager(host, silent_bool, log_file)
    elif sys_name == "Linux":
        if dist_id in ["ubuntu", "debian"]:
            return AptManager(host, silent_bool, log_file)
        elif dist_id in ["rhel", "ol", "centos"]:
            return DnfManager(host, silent_bool, log_file)
        elif dist_id == "sles":
            return ZypperManager(host, silent_bool, log_file)
        elif dist_id == "arch":
            return PacmanManager(host, silent_bool, log_file)
        else:
            raise NotImplementedError(f"Unsupported Linux distro: {dist_id}")
    else:
        raise NotImplementedError(f"Unsupported OS: {sys_name}")


def setup_sudo():
    """
    Bootstrapping routine executed by standard user to generate sudoers configuration.
    """
    import getpass

    current_user = getpass.getuser()
    helper_name = "systems-manager-helper"
    helper_path = shutil.which(helper_name)

    if not helper_path:
        # If running inside virtualenv, construct path relative to sys.executable
        possible_helper = os.path.join(os.path.dirname(sys.executable), helper_name)
        if os.path.exists(possible_helper):
            helper_path = possible_helper

    if not helper_path:
        # Let's also check default ~/.local/bin or standard paths
        home = os.path.expanduser("~")
        possible_helper = os.path.join(home, ".local", "bin", helper_name)
        if os.path.exists(possible_helper):
            helper_path = possible_helper

    if not helper_path:
        print(
            f"[-] Error: '{helper_name}' executable not found in PATH or standard environment locations.",
            file=sys.stderr,
        )
        print(
            "    Please install systems-manager first using: pip install systems-manager",
            file=sys.stderr,
        )
        sys.exit(1)

    # Clean/resolve absolute path
    helper_path = os.path.abspath(helper_path)

    # Generate the exact sudoers configuration block
    sudoers_rule = f"{current_user} ALL=(ALL) NOPASSWD: {helper_path}\n"

    print("[*] Secure Sudo Wrapper Configuration Detected:", file=sys.stderr)
    print(f"    - Execution User: {current_user}", file=sys.stderr)
    print(f"    - Helper Path:    {helper_path}", file=sys.stderr)
    print(f"    - Rule to Write:  {sudoers_rule.strip()}", file=sys.stderr)
    print(
        "\n[!] To complete the installation, the systems manager requires elevation ONCE to write the configuration:",
        file=sys.stderr,
    )

    temp_path = None
    try:
        # Write temporary file
        fd, temp_path = tempfile.mkstemp()
        with os.fdopen(fd, "w") as f:
            f.write(sudoers_rule)

        print(
            "[*] Requesting temporary sudo access to apply configuration...",
            file=sys.stderr,
        )

        # 1. Copy the sudoers file to /etc/sudoers.d/
        dest_path = f"/etc/sudoers.d/systems-manager-{current_user}"
        cp_cmd = ["sudo", "cp", temp_path, dest_path]
        subprocess.run(cp_cmd, check=True)

        # 2. Set strict permissions (must be 0440 and owned by root)
        subprocess.run(["sudo", "chown", "root:root", dest_path], check=True)
        subprocess.run(["sudo", "chmod", "0440", dest_path], check=True)

        # 3. Use visudo to validate syntax
        visudo_check = subprocess.run(
            ["sudo", "visudo", "-c", "-f", dest_path], capture_output=True, text=True
        )
        if visudo_check.returncode != 0:
            print(
                "[-] Error: visudo syntax check failed. Reverting changes.",
                file=sys.stderr,
            )
            print(f"    visudo output: {visudo_check.stderr.strip()}", file=sys.stderr)
            subprocess.run(["sudo", "rm", "-f", dest_path], check=True)
            sys.exit(1)

        print(
            f"[+] Sudoers rule installed successfully under {dest_path}!",
            file=sys.stderr,
        )
        print(
            "[+] Any agents running in this user space can now execute elevated tools securely.",
            file=sys.stderr,
        )
    except Exception as e:
        print(f"[-] Installation failed: {str(e)}", file=sys.stderr)
        print(
            "[*] Alternatively, ask your system administrator to append this line to /etc/sudoers:",
            file=sys.stderr,
        )
        print(f"    {sudoers_rule.strip()}", file=sys.stderr)
        sys.exit(1)
    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)


def bootstrap_cluster_sudo():
    """
    Automated cluster-wide sudo bootstrapping capability.
    Reads inventory from ~/.config/agent-utilities/inventory.yaml, checks reachable hosts,
    checks if passwordless sudo is already configured, prompts securely once for sudo password,
    and configures passwordless sudo on remote hosts.
    """
    import getpass

    from tunnel_manager.tunnel_manager import HostManager

    print("[*] Starting automated cluster-wide sudo bootstrapping...", file=sys.stderr)
    try:
        hm = HostManager()
    except Exception as e:
        print(f"[-] Error loading host inventory: {str(e)}", file=sys.stderr)
        sys.exit(1)

    print(f"[*] Loaded inventory config file: {hm.config_file}", file=sys.stderr)
    active_hosts = {}

    for alias, hinfo in hm.hosts.items():
        if alias == "gr1080":
            print(
                "[*] Skipping gr1080 (marked offline in environment metadata)",
                file=sys.stderr,
            )
            continue

        hostname = hinfo.get("hostname")
        user = hinfo.get("user", "genius")
        port = hinfo.get("port", 22)
        identity_file = hinfo.get("key_path") or hinfo.get("identity_file")

        # 1. SSH Connection/Reachability Check with BatchMode=yes to prevent hangs
        ssh_cmd = [
            "ssh",
            "-o",
            "StrictHostKeyChecking=no",
            "-o",
            "ConnectTimeout=3",
            "-o",
            "BatchMode=yes",
        ]
        if identity_file:
            ssh_cmd.extend(["-i", os.path.expanduser(identity_file)])
        ssh_cmd.extend(["-p", str(port), f"{user}@{hostname}", "echo reachable"])

        try:
            res = subprocess.run(ssh_cmd, capture_output=True, text=True, timeout=5)
            if res.returncode != 0:
                print(
                    f"[-] Host '{alias}' ({hostname}) is unreachable. Skipping.",
                    file=sys.stderr,
                )
                continue
        except Exception as e:
            print(
                f"[-] Host '{alias}' ({hostname}) connection failed: {str(e)}. Skipping.",
                file=sys.stderr,
            )
            continue

        # 2. Check if passwordless sudo is already active
        sudo_cmd = [
            "ssh",
            "-o",
            "StrictHostKeyChecking=no",
            "-o",
            "ConnectTimeout=3",
            "-o",
            "BatchMode=yes",
        ]
        if identity_file:
            sudo_cmd.extend(["-i", os.path.expanduser(identity_file)])
        sudo_cmd.extend(["-p", str(port), f"{user}@{hostname}", "sudo -n true"])

        try:
            res_sudo = subprocess.run(
                sudo_cmd, capture_output=True, text=True, timeout=5
            )
            if res_sudo.returncode == 0:
                print(
                    f"[+] Passwordless sudo already configured on '{alias}' ({hostname})!",
                    file=sys.stderr,
                )
                continue
        except Exception:
            pass

        print(
            f"[*] Host '{alias}' ({hostname}) is reachable but requires interactive sudo password.",
            file=sys.stderr,
        )
        active_hosts[alias] = hinfo

    if not active_hosts:
        print(
            "[+] All reachable cluster hosts already have passwordless sudo configured. No action needed!",
            file=sys.stderr,
        )
        return

    # 3. Prompt user securely once for the sudo password
    print(
        f"\n[!] Prompting for remote sudo password to configure {len(active_hosts)} hosts.",
        file=sys.stderr,
    )
    password = getpass.getpass("Enter sudo password for remote hosts: ")
    if not password:
        print("[-] Sudo password cannot be empty. Aborting.", file=sys.stderr)
        sys.exit(1)

    # 4. Bootstrap remote sudo configuration
    for alias, hinfo in active_hosts.items():
        hostname = hinfo.get("hostname")
        user = hinfo.get("user", "genius")
        port = hinfo.get("port", 22)
        identity_file = hinfo.get("key_path") or hinfo.get("identity_file")

        print(f"[*] Bootstrapping '{alias}' ({hostname})...", file=sys.stderr)

        # Write helper path rules to a temp file on the remote host via stdin pipe
        helper_rule = (
            f"{user} ALL=(ALL) NOPASSWD: /usr/local/bin/systems-manager-helper, "
            f"/home/{user}/.local/bin/systems-manager-helper\n"
        )

        cat_cmd = [
            "ssh",
            "-o",
            "StrictHostKeyChecking=no",
            "-o",
            "ConnectTimeout=3",
            "-o",
            "BatchMode=yes",
        ]
        if identity_file:
            cat_cmd.extend(["-i", os.path.expanduser(identity_file)])
        cat_cmd.extend(
            [
                "-p",
                str(port),
                f"{user}@{hostname}",
                "cat > /tmp/systems-manager-sudoers",
            ]
        )

        try:
            proc = subprocess.Popen(
                cat_cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            stdout, stderr = proc.communicate(input=helper_rule, timeout=5)
            if proc.returncode != 0:
                print(
                    f"[-] Failed to write temp sudoers file to '{alias}': {stderr.strip()}",
                    file=sys.stderr,
                )
                continue
        except Exception as e:
            print(f"[-] Failed to copy file to '{alias}': {str(e)}", file=sys.stderr)
            continue

        # Install sudoers rule safely with visudo check
        dest_path = f"/etc/sudoers.d/systems-manager-{user}"
        remote_setup_cmd = (
            f"sudo -S -p '' sh -c '"
            f"cp /tmp/systems-manager-sudoers {dest_path} && "
            f"chown root:root {dest_path} && "
            f"chmod 0440 {dest_path} && "
            f"(visudo -c -f {dest_path} || (rm -f {dest_path} && exit 1))"
            f"'"
        )

        ssh_setup = [
            "ssh",
            "-o",
            "StrictHostKeyChecking=no",
            "-o",
            "ConnectTimeout=5",
            "-o",
            "BatchMode=yes",
        ]
        if identity_file:
            ssh_setup.extend(["-i", os.path.expanduser(identity_file)])
        ssh_setup.extend(["-p", str(port), f"{user}@{hostname}", remote_setup_cmd])

        try:
            proc = subprocess.Popen(
                ssh_setup,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            stdout, stderr = proc.communicate(input=password + "\n", timeout=10)

            # Always clean up the temp file
            cleanup_cmd = [
                "ssh",
                "-o",
                "StrictHostKeyChecking=no",
                "-o",
                "BatchMode=yes",
                "-p",
                str(port),
                f"{user}@{hostname}",
                "rm -f /tmp/systems-manager-sudoers",
            ]
            if identity_file:
                cleanup_cmd.insert(2, "-i")
                cleanup_cmd.insert(3, os.path.expanduser(identity_file))
            subprocess.run(cleanup_cmd, capture_output=True)

            if proc.returncode == 0:
                print(
                    f"[+] Successfully configured passwordless sudo on '{alias}' ({hostname})!",
                    file=sys.stderr,
                )
            else:
                print(
                    f"[-] Failed to configure sudo on '{alias}' ({hostname}): {stderr.strip()}",
                    file=sys.stderr,
                )
        except Exception as e:
            print(
                f"[-] Execution error during bootstrap on '{alias}': {str(e)}",
                file=sys.stderr,
            )

    print("[*] Cluster bootstrapping complete.", file=sys.stderr)


def systems_manager():
    print(f"systems_manager v{__version__}", file=sys.stderr)
    parser = argparse.ArgumentParser(
        add_help=False, description="System Manager Utility"
    )
    parser.add_argument(
        "-c", "--clean", action="store_true", help="Clean system resources"
    )
    parser.add_argument(
        "-f", "--fonts", type=str, help="Comma-separated list of fonts to install"
    )
    parser.add_argument(
        "-s", "--silent", action="store_true", help="Run in silent mode"
    )
    parser.add_argument(
        "-u", "--update", action="store_true", help="Update system packages"
    )
    parser.add_argument(
        "-i",
        "--install",
        type=str,
        help="Comma-separated list of applications to install",
    )
    parser.add_argument(
        "-p",
        "--python",
        type=str,
        help="Comma-separated list of Python modules to install",
    )
    parser.add_argument("-o", "--optimize", action="store_true", help="Optimize system")
    parser.add_argument("--os-stats", action="store_true", help="Display OS statistics")
    parser.add_argument(
        "--hw-stats", action="store_true", help="Display hardware statistics"
    )
    parser.add_argument(
        "-e",
        "--enable-features",
        type=str,
        help="Comma-separated list of features to enable (Windows only)",
    )
    parser.add_argument(
        "-d",
        "--disable-features",
        type=str,
        help="Comma-separated list of features to disable (Windows only)",
    )
    parser.add_argument(
        "-l",
        "--list-features",
        action="store_true",
        help="List available features (Windows only)",
    )
    parser.add_argument("--log-file", type=str, help="Specify log file path")
    parser.add_argument(
        "--add-repo", type=str, help="Add upstream repository: url[:name] (Linux only)"
    )
    parser.add_argument(
        "--install-local",
        type=str,
        help="Install local package files, comma-separated (Linux only)",
    )

    parser.add_argument(
        "--setup-sudo",
        action="store_true",
        help="Bootstrap secure sudo wrapper configuration (Linux only)",
    )
    parser.add_argument(
        "--host",
        type=str,
        help="Specify target host from inventory (Linux only)",
    )
    parser.add_argument(
        "--bootstrap-cluster-sudo",
        action="store_true",
        help="Configure passwordless sudo cluster-wide (Linux only)",
    )

    parser.add_argument("--help", action="store_true", help="Show usage")

    args = parser.parse_args()

    if hasattr(args, "help") and args.help:
        parser.print_help()
        sys.exit(0)

    if hasattr(args, "setup_sudo") and args.setup_sudo:
        setup_sudo()
        sys.exit(0)

    if hasattr(args, "bootstrap_cluster_sudo") and args.bootstrap_cluster_sudo:
        bootstrap_cluster_sudo()
        sys.exit(0)

    log_file = args.log_file
    apps = args.install.split(",") if args.install else []
    python_modules = args.python.split(",") if args.python else []
    enable_features_list = (
        args.enable_features.split(",") if args.enable_features else []
    )
    disable_features_list = (
        args.disable_features.split(",") if args.disable_features else []
    )
    fonts = args.fonts.split(",") if args.fonts else ["Hack"]
    install = bool(args.install)
    font = bool(args.fonts)
    update = args.update
    clean = args.clean
    optimize = args.optimize
    install_python = bool(args.python)
    os_stats = args.os_stats
    hw_stats = args.hw_stats
    silent = args.silent
    list_features = args.list_features
    enable_features = bool(args.enable_features)
    disable_features = bool(args.disable_features)
    add_repo = args.add_repo
    install_local = args.install_local

    manager = detect_and_create_manager(
        host=args.host, silent=silent, log_file=log_file
    )

    if update:
        manager.update()
    if install:
        manager.install_applications(apps)
    if install_python:
        manager.install_python_modules(python_modules)
    if font:
        manager.font(fonts)
    if clean:
        manager.clean()
    if optimize:
        manager.optimize()
    if add_repo:
        parts = add_repo.split(":")
        url = parts[0]
        name = parts[1] if len(parts) > 1 else None
        manager.add_repository(url, name)
    if install_local:
        files = [f.strip() for f in install_local.split(",")]
        for f in files:
            manager.install_local_package(f)
    if os_stats:
        print(
            json.dumps(manager.get_os_statistics().model_dump(), indent=2),
            file=sys.stderr,
        )
    if hw_stats:
        print(
            json.dumps(manager.get_hardware_statistics().model_dump(), indent=2),
            file=sys.stderr,
        )
    if list_features:
        if isinstance(manager, WindowsManager):
            features = manager.list_windows_features()
            print(json.dumps(features, indent=2), file=sys.stderr)
        else:
            print("Feature listing is only available on Windows.", file=sys.stderr)
    if enable_features:
        if isinstance(manager, WindowsManager):
            manager.enable_windows_features(enable_features_list)
        else:
            print("Feature enabling is only available on Windows.", file=sys.stderr)
    if disable_features:
        if isinstance(manager, WindowsManager):
            manager.disable_windows_features(disable_features_list)
        else:
            print("Feature disabling is only available on Windows.", file=sys.stderr)

    print("Done!", file=sys.stderr)


main = systems_manager


if __name__ == "__main__":
    systems_manager()
