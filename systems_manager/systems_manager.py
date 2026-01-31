#!/usr/bin/env python
# coding: utf-8

import argparse
import subprocess
import os
import platform
import json
import shutil
import zipfile
import glob
import requests
import logging
import distro
import psutil
from typing import List, Dict, Union
from abc import ABC, abstractmethod

__version__ = "1.1.25"


def setup_logging(
    is_mcp_server: bool = False, log_file: str = "systems_manager_mcp.log"
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


class SystemsManagerBase(ABC):
    def __init__(self, silent: bool = False, log_file: str = None):
        self.silent = silent
        self.logger = setup_logging(log_file)

    def log_command(
        self,
        command: Union[List[str], str],
        result: subprocess.CompletedProcess = None,
        error: Exception = None,
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

    def run_command(
        self,
        command: Union[List[str], str],
        elevated: bool = False,
        shell: bool = False,
    ) -> Dict:
        if isinstance(command, str):
            command = command.split()
        if elevated and platform.system() == "Linux":
            command = ["sudo"] + command
        elif elevated and platform.system() == "Windows":
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
                result = subprocess.run(
                    command,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    shell=shell,
                    check=True,
                )
                stdout = None
                stderr = None
            else:
                print(f"Running: {' '.join(command)}")
                result = subprocess.run(
                    command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    shell=shell,
                    check=True,
                )
                stdout = result.stdout
                stderr = result.stderr
            self.log_command(command, result)
            return {
                "success": True,
                "returncode": result.returncode,
                "stdout": stdout,
                "stderr": stderr,
            }
        except subprocess.CalledProcessError as e:
            self.log_command(command, result=e, error=e)
            if not self.silent:
                print(f"Error: {e.stderr}")
            return {
                "success": False,
                "returncode": e.returncode,
                "stdout": e.stdout,
                "stderr": e.stderr,
                "error": str(e),
            }
        except Exception as e:
            self.log_command(command, error=e)
            return {"success": False, "error": str(e)}

    @abstractmethod
    def install_applications(self, apps: List[str]) -> Dict:
        pass

    @abstractmethod
    def update(self) -> Dict:
        pass

    @abstractmethod
    def clean(self) -> Dict:
        pass

    @abstractmethod
    def optimize(self) -> Dict:
        pass

    @abstractmethod
    def install_snapd(self) -> Dict:
        pass

    @abstractmethod
    def add_repository(self, repo_url: str, name: str = None) -> Dict:
        pass

    @abstractmethod
    def install_local_package(self, file_path: str) -> Dict:
        pass

    def install_via_snap(self, app: str) -> Dict:
        snap_bin = shutil.which("snap")
        if snap_bin is None:
            self.logger.info("Snap not found; installing snapd...")
            snapd_result = self.install_snapd()
            if not snapd_result["success"]:
                return {
                    "success": False,
                    "error": "Failed to install snapd",
                    "details": snapd_result,
                }
            enable_result = self.run_command(
                ["systemctl", "enable", "--now", "snapd.socket"], elevated=True
            )
            if not enable_result["success"]:
                self.logger.warning("Failed to enable snapd.socket")
            # Optional symlink
            symlink_result = self.run_command(
                ["ln", "-s", "/var/lib/snapd/snap", "/snap"], elevated=True
            )
            if not symlink_result["success"]:
                self.logger.warning("Failed to create /snap symlink")
        install_result = self.run_command(["snap", "install", app], elevated=True)
        return {
            "success": install_result["success"],
            "details": install_result,
            "app": app,
        }

    def install_python_modules(self, modules: List[str]) -> Dict:
        results = {
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

    def font(self, fonts: List[str] = None) -> Dict:
        if not fonts:
            fonts = ["Hack"]
        api_url = "https://api.github.com/repos/ryanoasis/nerd-fonts/releases/latest"
        response = requests.get(api_url).json()
        all_assets = [
            a
            for a in response["assets"]
            if a["name"].endswith(".zip") and "FontPatcher" not in a["name"]
        ]

        # Check for "all" (case-insensitive)
        if any(f.lower() == "all" for f in fonts):
            assets = all_assets
        else:
            # Filter assets to match requested fonts (case-insensitive)
            assets = [
                a
                for a in all_assets
                if any(f.lower() in a["name"].lower() for f in fonts)
            ]

        if not assets:
            return {"success": False, "error": f"No matching fonts found for {fonts}"}

        if platform.system() == "Linux":
            font_dir = os.path.expanduser("~/.local/share/fonts")
            os.makedirs(font_dir, exist_ok=True)
            extract_path = font_dir
        elif platform.system() == "Windows":
            font_dir = r"C:\Windows\Fonts"
            extract_path = "."
        else:
            return {"success": False, "error": "Unsupported OS for font installation"}

        successful_downloads = []
        for asset in assets:
            zip_name = asset["name"]
            url = asset["browser_download_url"]
            self.logger.info(f"Downloading {zip_name} from {url}")
            if not self.silent:
                print(f"Downloading {zip_name} from {url}")
            try:
                r = requests.get(url)
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

        # Collect font files after all extractions
        font_files = glob.glob(
            os.path.join(extract_path, "**/*.ttf"), recursive=True
        ) + glob.glob(os.path.join(extract_path, "**/*.otf"), recursive=True)

        installed_fonts = []
        if platform.system() == "Windows":
            for font in font_files:
                dest = os.path.join(font_dir, os.path.basename(font))
                self.logger.info(f"Moving {font} to {dest}")
                if not self.silent:
                    print(f"Moving {font} to {dest}")
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
        return {
            "success": overall_success,
            "requested_fonts": fonts,
            "downloaded": successful_downloads,
            "installed_fonts": installed_fonts,
            "total_fonts": len(font_files),
            "os": platform.system(),
        }

    def get_os_statistics(self) -> Dict:
        return {
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "load_avg": os.getloadavg() if platform.system() != "Windows" else "N/A",
        }

    def get_hardware_statistics(self) -> Dict:
        return {
            "cpu_percent": psutil.cpu_percent(interval=1),
            "cpu_count": psutil.cpu_count(),
            "memory": psutil.virtual_memory()._asdict(),
            "disk_usage": psutil.disk_usage("/")._asdict(),
            "network": psutil.net_io_counters()._asdict(),
        }


class AptManager(SystemsManagerBase):  # Ubuntu/Debian
    def __init__(self, silent: bool = False, log_file: str = None):
        super().__init__(silent, log_file)
        self.not_found_msg = "Unable to locate package"

    def install_applications(self, apps: List[str]) -> Dict:
        results = {
            "natively_installed": [],
            "snap_installed": [],
            "failed": [],
            "success": True,
        }
        update_result = self.run_command(["apt", "update"], elevated=True)
        if not update_result["success"]:
            results["success"] = False
            results["update_error"] = update_result.get("error")
            self.logger.error("apt update failed")
        for app in apps:
            install_result = self.run_command(
                ["apt", "install", "-y", app], elevated=True
            )
            if install_result["success"]:
                results["natively_installed"].append(app)
            else:
                if self.not_found_msg in install_result.get("stderr", ""):
                    if not self.silent:
                        print(f"Falling back to Snap for {app}...")
                    self.logger.info(
                        f"Native install failed for {app}; falling back to Snap..."
                    )
                    snap_result = self.install_via_snap(app)
                    if snap_result["success"]:
                        results["snap_installed"].append(app)
                    else:
                        results["failed"].append(app)
                        results["success"] = False
                        self.logger.error(
                            f"Snap install failed for {app}: {snap_result.get('error')}"
                        )
                else:
                    results["failed"].append(app)
                    results["success"] = False
                    self.logger.error(
                        f"Native install failed for {app}: {install_result.get('error')}"
                    )
        return results

    def update(self) -> Dict:
        try:
            update_result = self.run_command(["apt", "update"], elevated=True)
            if not update_result["success"]:
                return {
                    "success": False,
                    "error": "apt update failed",
                    "details": update_result,
                }
            upgrade_result = self.run_command(["apt", "upgrade", "-y"], elevated=True)
            if not upgrade_result["success"]:
                return {
                    "success": False,
                    "error": "apt upgrade failed",
                    "details": upgrade_result,
                }
            return {"success": True, "message": "System and packages updated"}
        except Exception as e:
            self.logger.error(f"Unexpected error in update: {e}")
            return {"success": False, "error": str(e)}

    def clean(self) -> Dict:
        install_result = self.run_command(
            ["apt", "install", "-y", "trash-cli"], elevated=True
        )
        if not install_result["success"]:
            self.logger.warning("Failed to install trash-cli")
        empty_result = self.run_command(["trash-empty"])
        if empty_result["success"]:
            return {"success": True, "message": "Trash emptied"}
        else:
            return {
                "success": False,
                "error": "Failed to empty trash",
                "details": empty_result,
            }

    def optimize(self) -> Dict:
        autoremove_result = self.run_command(["apt", "autoremove", "-y"], elevated=True)
        autoclean_result = self.run_command(["apt", "autoclean"], elevated=True)
        overall_success = autoremove_result["success"] and autoclean_result["success"]
        return {
            "success": overall_success,
            "message": (
                "System optimized" if overall_success else "Partial optimization"
            ),
            "details": {"autoremove": autoremove_result, "autoclean": autoclean_result},
        }

    def install_snapd(self) -> Dict:
        result = self.run_command(["apt", "install", "-y", "snapd"], elevated=True)
        return {
            "success": result["success"],
            "details": result,
            "message": (
                "snapd installed" if result["success"] else "Failed to install snapd"
            ),
        }

    def add_repository(self, repo_url: str, name: str = None) -> Dict:
        add_result = self.run_command(
            ["add-apt-repository", "-y", repo_url], elevated=True
        )
        if add_result["success"]:
            update_result = self.run_command(["apt", "update"], elevated=True)
            return {
                "success": update_result["success"],
                "details": [add_result, update_result],
            }
        return add_result

    def install_local_package(self, file_path: str) -> Dict:
        if not file_path.endswith(".deb"):
            return {"success": False, "error": "Not a .deb file"}
        install_result = self.run_command(["dpkg", "-i", file_path], elevated=True)
        if install_result["success"]:
            fix_result = self.run_command(["apt", "install", "-f", "-y"], elevated=True)
            return {
                "success": fix_result["success"],
                "details": [install_result, fix_result],
            }
        return install_result


class DnfManager(SystemsManagerBase):  # Red Hat, Oracle Linux
    def __init__(self, silent: bool = False, log_file: str = None):
        super().__init__(silent, log_file)
        self.not_found_msg = "Unable to find a match"

    def install_applications(self, apps: List[str]) -> Dict:
        results = {
            "natively_installed": [],
            "snap_installed": [],
            "failed": [],
            "success": True,
        }
        # Optional: update repos before install
        update_result = self.run_command(["dnf", "update", "-y"], elevated=True)
        if not update_result["success"]:
            self.logger.warning("dnf update failed before installs")
        for app in apps:
            install_result = self.run_command(
                ["dnf", "install", "-y", app], elevated=True
            )
            if install_result["success"]:
                results["natively_installed"].append(app)
            else:
                if self.not_found_msg in install_result.get("stderr", ""):
                    if not self.silent:
                        print(f"Falling back to Snap for {app}...")
                    self.logger.info(
                        f"Native install failed for {app}; falling back to Snap..."
                    )
                    snap_result = self.install_via_snap(app)
                    if snap_result["success"]:
                        results["snap_installed"].append(app)
                    else:
                        results["failed"].append(app)
                        results["success"] = False
                else:
                    results["failed"].append(app)
                    results["success"] = False
        return results

    def update(self) -> Dict:
        result = self.run_command(["dnf", "update", "-y"], elevated=True)
        return {
            "success": result["success"],
            "message": "System updated" if result["success"] else "Update failed",
            "details": result,
        }

    def clean(self) -> Dict:
        result = self.run_command(["dnf", "clean", "all"], elevated=True)
        return {
            "success": result["success"],
            "message": "Cache cleaned" if result["success"] else "Clean failed",
            "details": result,
        }

    def optimize(self) -> Dict:
        result = self.run_command(["dnf", "autoremove", "-y"], elevated=True)
        return {
            "success": result["success"],
            "message": "Orphans removed" if result["success"] else "Optimize failed",
            "details": result,
        }

    def install_snapd(self) -> Dict:
        result = self.run_command(["dnf", "install", "-y", "snapd"], elevated=True)
        return {
            "success": result["success"],
            "details": result,
            "message": (
                "snapd installed" if result["success"] else "Failed to install snapd"
            ),
        }

    def add_repository(self, repo_url: str, name: str = None) -> Dict:
        command = ["dnf", "config-manager", "--add-repo", repo_url]
        add_result = self.run_command(command, elevated=True)
        if add_result["success"]:
            update_result = self.run_command(["dnf", "makecache"], elevated=True)
            return {
                "success": update_result["success"],
                "details": [add_result, update_result],
            }
        return add_result

    def install_local_package(self, file_path: str) -> Dict:
        if not file_path.endswith(".rpm"):
            return {"success": False, "error": "Not a .rpm file"}
        return self.run_command(["dnf", "install", "-y", file_path], elevated=True)


class ZypperManager(SystemsManagerBase):  # SLES
    def __init__(self, silent: bool = False, log_file: str = None):
        super().__init__(silent, log_file)
        self.not_found_msg = "No provider of"

    def install_applications(self, apps: List[str]) -> Dict:
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
                results["natively_installed"].append(app)
            else:
                if self.not_found_msg in install_result.get("stderr", ""):
                    if not self.silent:
                        print(f"Falling back to Snap for {app}...")
                    self.logger.info(
                        f"Native install failed for {app}; falling back to Snap..."
                    )
                    snap_result = self.install_via_snap(app)
                    if snap_result["success"]:
                        results["snap_installed"].append(app)
                    else:
                        results["failed"].append(app)
                        results["success"] = False
                else:
                    results["failed"].append(app)
                    results["success"] = False
        return results

    def update(self) -> Dict:
        result = self.run_command(["zypper", "update", "-y"], elevated=True)
        return {
            "success": result["success"],
            "message": "System updated" if result["success"] else "Update failed",
            "details": result,
        }

    def clean(self) -> Dict:
        result = self.run_command(["zypper", "clean", "--all"], elevated=True)
        return {
            "success": result["success"],
            "message": "Cache cleaned" if result["success"] else "Clean failed",
            "details": result,
        }

    def optimize(self) -> Dict:
        result = self.run_command(["zypper", "rm", "-u"], elevated=True)
        return {
            "success": result["success"],
            "message": "Unneeded removed" if result["success"] else "Optimize failed",
            "details": result,
        }

    def install_snapd(self) -> Dict:
        result = self.run_command(["zypper", "install", "-y", "snapd"], elevated=True)
        return {
            "success": result["success"],
            "details": result,
            "message": (
                "snapd installed" if result["success"] else "Failed to install snapd"
            ),
        }

    def add_repository(self, repo_url: str, name: str = None) -> Dict:
        if not name:
            name = "custom"
        add_result = self.run_command(
            ["zypper", "addrepo", repo_url, name], elevated=True
        )
        if add_result["success"]:
            refresh_result = self.run_command(["zypper", "refresh"], elevated=True)
            return {
                "success": refresh_result["success"],
                "details": [add_result, refresh_result],
            }
        return add_result

    def install_local_package(self, file_path: str) -> Dict:
        if not file_path.endswith(".rpm"):
            return {"success": False, "error": "Not a .rpm file"}
        return self.run_command(["zypper", "install", "-y", file_path], elevated=True)


class PacmanManager(SystemsManagerBase):  # Arch
    def __init__(self, silent: bool = False, log_file: str = None):
        super().__init__(silent, log_file)
        self.not_found_msg = "target not found"

    def install_applications(self, apps: List[str]) -> Dict:
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
                results["natively_installed"].append(app)
            else:
                if self.not_found_msg in install_result.get("stderr", ""):
                    if not self.silent:
                        print(f"Falling back to Snap for {app}...")
                    self.logger.info(
                        f"Native install failed for {app}; falling back to Snap..."
                    )
                    snap_result = self.install_via_snap(app)
                    if snap_result["success"]:
                        results["snap_installed"].append(app)
                    else:
                        results["failed"].append(app)
                        results["success"] = False
                else:
                    results["failed"].append(app)
                    results["success"] = False
        return results

    def update(self) -> Dict:
        result = self.run_command(["pacman", "-Syu", "--noconfirm"], elevated=True)
        return {
            "success": result["success"],
            "message": "System updated" if result["success"] else "Update failed",
            "details": result,
        }

    def clean(self) -> Dict:
        result = self.run_command(["pacman", "-Sc", "--noconfirm"], elevated=True)
        return {
            "success": result["success"],
            "message": "Cache cleaned" if result["success"] else "Clean failed",
            "details": result,
        }

    def optimize(self) -> Dict:
        orphans_cmd = ["pacman", "-Rns", "$(pacman -Qdtq)", "--noconfirm"]
        result = self.run_command(orphans_cmd, elevated=True, shell=True)
        return {
            "success": result["success"],
            "message": "Orphans removed" if result["success"] else "Optimize failed",
            "details": result,
        }

    def install_snapd(self) -> Dict:
        result = self.run_command(
            ["pacman", "-S", "--noconfirm", "snapd"], elevated=True
        )
        return {
            "success": result["success"],
            "details": result,
            "message": (
                "snapd installed" if result["success"] else "Failed to install snapd"
            ),
        }

    def add_repository(self, repo_url: str, name: str = None) -> Dict:
        if not name:
            name = "custom"
        conf = "/etc/pacman.conf"
        content = f"\n[{name}]\nServer = {repo_url}\n"
        echo_cmd = ["bash", "-c", f"echo '{content}' >> {conf}"]
        add_result = self.run_command(echo_cmd, elevated=True, shell=True)
        if add_result["success"]:
            sync_result = self.run_command(
                ["pacman", "-Sy", "--noconfirm"], elevated=True
            )
            return {
                "success": sync_result["success"],
                "details": [add_result, sync_result],
            }
        return add_result

    def install_local_package(self, file_path: str) -> Dict:
        return self.run_command(
            ["pacman", "-U", "--noconfirm", file_path], elevated=True
        )


class WindowsManager(SystemsManagerBase):
    def __init__(self, silent: bool = False, log_file: str = None):
        super().__init__(silent, log_file)
        # Ensure winget is available (simplified)
        winget_path = os.path.expanduser(
            r"~\AppData\Local\Microsoft\WindowsApps\winget.exe"
        )
        if not os.path.exists(winget_path):
            if not self.silent:
                print("Installing Winget...")
            self.logger.info("Installing Winget...")
            download_result = self.run_command(
                [
                    "powershell.exe",
                    "Invoke-WebRequest",
                    "-Uri",
                    "https://aka.ms/getwinget",
                    "-OutFile",
                    "winget.msixbundle",
                ]
            )
            if download_result["success"]:
                install_result = self.run_command(
                    ["powershell.exe", "Add-AppPackage", "-Path", "winget.msixbundle"]
                )
                if install_result["success"]:
                    os.remove("winget.msixbundle")
                else:
                    self.logger.error("Failed to install Winget")
            else:
                self.logger.error("Failed to download Winget")

    def install_applications(self, apps: List[str]) -> Dict:
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
                results["installed"].append(app)
            else:
                results["failed"].append(app)
                results["success"] = False
                self.logger.error(
                    f"Failed to install {app}: {install_result.get('error')}"
                )
        return results

    def update(self) -> Dict:
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
        # For Windows updates, use PSWindowsUpdate
        wu_cmd = [
            "powershell.exe",
            "-Command",
            "if (!(Get-Module -ListAvailable -Name PSWindowsUpdate)) { Install-Module PSWindowsUpdate -Force -Scope CurrentUser }; Import-Module PSWindowsUpdate; Get-WUList | Install-WUUpdate -AcceptAll -AutoReboot:$false",
        ]
        wu_result = self.run_command(wu_cmd, shell=True, elevated=True)
        overall_success = winget_result["success"] and wu_result["success"]
        return {
            "success": overall_success,
            "message": (
                "System and apps updated" if overall_success else "Partial update"
            ),
            "details": {"winget": winget_result, "windows_update": wu_result},
        }

    def clean(self) -> Dict:
        # cleanmgr runs GUI, may not be ideal for automation; consider alternatives like Dism
        result = self.run_command(["cleanmgr", "/lowdisk"], shell=True)
        return {
            "success": result["success"],
            "message": "Cleanup initiated" if result["success"] else "Cleanup failed",
            "details": result,
        }

    def optimize(self) -> Dict:
        clean_result = self.run_command(["cleanmgr", "/lowdisk"], shell=True)
        defrag_result = self.run_command(
            ["powershell.exe", "Optimize-Volume", "-DriveLetter", "C", "-Verbose"],
            elevated=True,
        )
        overall_success = clean_result["success"] and defrag_result["success"]
        return {
            "success": overall_success,
            "message": (
                "System optimized" if overall_success else "Partial optimization"
            ),
            "details": {"cleanup": clean_result, "defrag": defrag_result},
        }

    def list_windows_features(self) -> List[Dict]:
        cmd = [
            "powershell.exe",
            "-Command",
            "Get-WindowsOptionalFeature -Online | ConvertTo-Json -Depth 3",
        ]
        result = self.run_command(cmd, shell=True)
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

    def enable_windows_features(self, features: List[str]) -> Dict:
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
                results["enabled"].append(feature)
            else:
                results["failed"].append(feature)
                results["success"] = False
                self.logger.error(
                    f"Failed to enable {feature}: {enable_result.get('error')}"
                )
        return results

    def disable_windows_features(self, features: List[str]) -> Dict:
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
                results["disabled"].append(feature)
            else:
                results["failed"].append(feature)
                results["success"] = False
                self.logger.error(
                    f"Failed to disable {feature}: {disable_result.get('error')}"
                )
        return results

    def install_snapd(self) -> Dict:
        return {"success": False, "error": "Snap not supported on Windows"}

    def add_repository(self, repo_url: str, name: str = None) -> Dict:
        return {
            "success": False,
            "error": "Repository addition not supported on Windows",
        }

    def install_local_package(self, file_path: str) -> Dict:
        return {
            "success": False,
            "error": "Local package installation not supported on Windows",
        }


def detect_and_create_manager(
    silent: bool = False, log_file: str = None
) -> SystemsManagerBase:
    sys_name = platform.system()
    if sys_name == "Windows":
        return WindowsManager(silent, log_file)
    elif sys_name == "Linux":
        dist_id = distro.id()
        if dist_id in ["ubuntu", "debian"]:
            return AptManager(silent, log_file)
        elif dist_id in ["rhel", "ol", "centos"]:  # Red Hat, Oracle, CentOS
            return DnfManager(silent, log_file)
        elif dist_id == "sles":
            return ZypperManager(silent, log_file)
        elif dist_id == "arch":
            return PacmanManager(silent, log_file)
        else:
            raise NotImplementedError(f"Unsupported Linux distro: {dist_id}")
    else:
        raise NotImplementedError(f"Unsupported OS: {sys_name}")


def usage():
    print("""
Systems-Manager: A tool to manage your systems software!

Usage:
-h | --help            [ See usage for script ]
-c | --clean           [ Clean system ]
-e | --enable-features <features> [ Enable Windows features (Windows only), comma-separated ]
-d | --disable-features <features> [ Disable Windows features (Windows only), comma-separated ]
-l | --list-features   [ List all Windows features and their status (Windows only) ]
-f | --fonts <fonts>   [ Install Nerd Fonts, comma-separated (e.g., Hack,Meslo) or 'all'; default: Hack ]
-i | --install <apps>  [ Install apps, comma-separated (e.g., python3,git) ]
-p | --python <mods>   [ Install Python modules, comma-separated ]
-s | --silent          [ Suppress output ]
-u | --update          [ Update system and apps ]
-o | --optimize        [ Optimize system (autoremove, clean cache) ]
--os-stats             [ Print OS stats ]
--hw-stats             [ Print hardware stats ]
--log-file <path>      [ Log to specified file (default: systems_manager.log in script dir) ]
--add-repo <url[:name]> [ Add upstream repository (Linux only) ]
--install-local <files> [ Install local package files, comma-separated (Linux only) ]

Example:
systems-manager --fonts Hack,Meslo --update --clean --python geniusbot --install python3,git --enable-features Microsoft-Hyper-V-All,Containers --log-file /path/to/log.log --add-repo ppa:graphics-drivers/ppa --install-local /path/to/package.deb
""")


def systems_manager():
    print(f"systems_manager v{__version__}")
    parser = argparse.ArgumentParser(description="System Manager Utility")
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

    args = parser.parse_args()

    log_file = args.log_file
    apps = args.install.split(",") if args.install else []
    python_modules = args.python.split(",") if args.python else []
    enable_features_list = (
        args.enable_features.split(",") if args.enable_features else []
    )
    disable_features_list = (
        args.disable_features.split(",") if args.disable_features else []
    )
    fonts = args.fonts.split(",") if args.fonts else ["Hack"]  # Default to Hack
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

    manager = detect_and_create_manager(silent, log_file)

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
        print(json.dumps(manager.get_os_statistics(), indent=2))
    if hw_stats:
        print(json.dumps(manager.get_hardware_statistics(), indent=2))
    if list_features:
        if isinstance(manager, WindowsManager):
            features = manager.list_windows_features()
            print(json.dumps(features, indent=2))
        else:
            print("Feature listing is only available on Windows.")
    if enable_features:
        if isinstance(manager, WindowsManager):
            manager.enable_windows_features(enable_features_list)
        else:
            print("Feature enabling is only available on Windows.")
    if disable_features:
        if isinstance(manager, WindowsManager):
            manager.disable_windows_features(disable_features_list)
        else:
            print("Feature disabling is only available on Windows.")

    print("Done!")


if __name__ == "__main__":
    systems_manager()
