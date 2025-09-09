#!/usr/bin/env python
# coding: utf-8

import sys
import getopt
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
from typing import List, Dict
from abc import ABC, abstractmethod


class SystemsManagerBase(ABC):
    def __init__(self, silent: bool = False, log_file: str = None):
        self.silent = silent
        self.result = None
        self.setup_logging(log_file)

    def setup_logging(self, log_file: str):
        if not log_file:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            log_file = os.path.join(script_dir, "systems_manager.log")
        logging.basicConfig(
            filename=log_file,
            level=logging.INFO,
            format="%(asctime)s - %(levelname)s - %(message)s",
        )
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"Logging initialized to {log_file}")

    def log_command(
        self,
        command: List[str],
        result: subprocess.CompletedProcess = None,
        error: Exception = None,
    ):
        self.logger.info(f"Running command: {' '.join(command)}")
        if result:
            self.logger.info(f"Return code: {result.returncode}")
            self.logger.info(f"Stdout: {result.stdout}")
            self.logger.info(f"Stderr: {result.stderr}")
        if error:
            self.logger.error(f"Error: {str(error)}")

    def run_command(
        self, command: List[str], elevated: bool = False, shell: bool = False
    ) -> subprocess.CompletedProcess:
        if elevated and platform.system() == "Linux":
            command = ["sudo"] + command
        elif elevated and platform.system() == "Windows":
            command = [
                "powershell.exe",
                "Start-Process",
                "powershell",
                "-Verb",
                "runAs",
                "-ArgumentList",
                f"'{ ' '.join(command) }'",
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
            self.log_command(command, result)
            return result
        except subprocess.CalledProcessError as e:
            self.log_command(command, error=e)
            print(f"Error: {e.stderr}")
            raise
        except Exception as e:
            self.log_command(command, error=e)
            raise

    @abstractmethod
    def install_applications(self, apps: List[str]):
        pass

    @abstractmethod
    def update(self):
        pass

    @abstractmethod
    def clean(self):
        pass

    @abstractmethod
    def optimize(self):
        pass

    @abstractmethod
    def install_snapd(self):
        pass

    def install_via_snap(self, app: str):
        if shutil.which("snap") is None:
            self.logger.info("Snap not found; installing snapd...")
            self.install_snapd()
            self.run_command(
                ["systemctl", "enable", "--now", "snapd.socket"], elevated=True
            )
            # Optional: For distros needing /snap symlink (e.g., Fedora)
            self.run_command(
                ["ln", "-s", "/var/lib/snapd/snap", "/snap"], elevated=True
            )
        self.run_command(
            ["snap", "install", app], elevated=True
        )  # Add --classic if app requires it (check via snap info)

    def install_python_modules(self, modules: List[str]):
        commands = [["python", "-m", "pip", "install", "--upgrade", "pip"]]
        for module in modules:
            commands.append(["python", "-m", "pip", "install", "--upgrade", module])
        for cmd in commands:
            self.run_command(cmd)

    def font(self, fonts: List[str] = None):
        if not fonts:
            fonts = ["Hack"]
        api_url = "https://api.github.com/repos/ryanoasis/nerd-fonts/releases/latest"
        response = requests.get(api_url).json()
        tag = response["tag_name"]
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
            raise ValueError(f"No matching fonts found for {fonts}")

        if platform.system() == "Linux":
            font_dir = os.path.expanduser("~/.local/share/fonts")
            os.makedirs(font_dir, exist_ok=True)
            extract_path = font_dir
            elevated = True  # For fc-cache
        elif platform.system() == "Windows":
            font_dir = r"C:\Windows\Fonts"
            extract_path = "."
            elevated = True  # May need admin for copying to system fonts
        else:
            raise NotImplementedError("Unsupported OS for font installation")

        for asset in assets:
            zip_name = asset["name"]
            url = asset["browser_download_url"]
            self.logger.info(f"Downloading {zip_name} from {url}")
            if not self.silent:
                print(f"Downloading {zip_name} from {url}")
            r = requests.get(url)
            with open(zip_name, "wb") as f:
                f.write(r.content)
            with zipfile.ZipFile(zip_name, "r") as zip_ref:
                zip_ref.extractall(extract_path)
            os.remove(zip_name)

        # Collect and install fonts
        font_files = glob.glob(
            os.path.join(extract_path, "**/*.ttf"), recursive=True
        ) + glob.glob(os.path.join(extract_path, "**/*.otf"), recursive=True)
        if platform.system() == "Windows":
            for font in font_files:
                dest = os.path.join(font_dir, os.path.basename(font))
                self.logger.info(f"Moving {font} to {dest}")
                if not self.silent:
                    print(f"Moving {font} to {dest}")
                shutil.move(font, dest)  # May require elevation
        elif platform.system() == "Linux":
            self.run_command(["fc-cache", "-fv"], elevated=elevated)

    def get_os_stats(self) -> Dict:
        return {
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "load_avg": os.getloadavg() if platform.system() != "Windows" else "N/A",
        }

    def get_hardware_stats(self) -> Dict:
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

    def install_applications(self, apps: List[str]):
        self.run_command(["apt", "update"], elevated=True)
        for app in apps:
            try:
                self.run_command(["apt", "install", "-y", app], elevated=True)
            except subprocess.CalledProcessError as e:
                if self.not_found_msg in e.stderr:
                    if not self.silent:
                        print(f"Falling back to Snap for {app}...")
                    self.logger.info(
                        f"Native install failed for {app}; falling back to Snap..."
                    )
                    self.install_via_snap(app)
                else:
                    raise  # Re-raise for other errors

    def update(self):
        self.run_command(["apt", "update"], elevated=True)
        self.run_command(["apt", "upgrade", "-y"], elevated=True)

    def clean(self):
        self.run_command(["apt", "install", "-y", "trash-cli"], elevated=True)
        self.run_command(["trash-empty"])

    def optimize(self):
        self.run_command(["apt", "autoremove", "-y"], elevated=True)
        self.run_command(["apt", "autoclean"], elevated=True)

    def install_snapd(self):
        self.run_command(["apt", "install", "-y", "snapd"], elevated=True)


class DnfManager(SystemsManagerBase):  # Red Hat, Oracle Linux
    def __init__(self, silent: bool = False, log_file: str = None):
        super().__init__(silent, log_file)
        self.not_found_msg = "Unable to find a match"

    def install_applications(self, apps: List[str]):
        for app in apps:
            try:
                self.run_command(["dnf", "install", "-y", app], elevated=True)
            except subprocess.CalledProcessError as e:
                if self.not_found_msg in e.stderr:
                    if not self.silent:
                        print(f"Falling back to Snap for {app}...")
                    self.logger.info(
                        f"Native install failed for {app}; falling back to Snap..."
                    )
                    self.install_via_snap(app)
                else:
                    raise  # Re-raise for other errors

    def update(self):
        self.run_command(["dnf", "update", "-y"], elevated=True)

    def clean(self):
        self.run_command(["dnf", "clean", "all"], elevated=True)

    def optimize(self):
        self.run_command(["dnf", "autoremove", "-y"], elevated=True)

    def install_snapd(self):
        self.run_command(["dnf", "install", "-y", "snapd"], elevated=True)


class ZypperManager(SystemsManagerBase):  # SLES
    def __init__(self, silent: bool = False, log_file: str = None):
        super().__init__(silent, log_file)
        self.not_found_msg = "No provider of"

    def install_applications(self, apps: List[str]):
        for app in apps:
            try:
                self.run_command(["zypper", "install", "-y", app], elevated=True)
            except subprocess.CalledProcessError as e:
                if self.not_found_msg in e.stderr:
                    if not self.silent:
                        print(f"Falling back to Snap for {app}...")
                    self.logger.info(
                        f"Native install failed for {app}; falling back to Snap..."
                    )
                    self.install_via_snap(app)
                else:
                    raise  # Re-raise for other errors

    def update(self):
        self.run_command(["zypper", "update", "-y"], elevated=True)

    def clean(self):
        self.run_command(["zypper", "clean", "--all"], elevated=True)

    def optimize(self):
        self.run_command(["zypper", "rm", "-u"], elevated=True)  # Remove unneeded

    def install_snapd(self):
        self.run_command(["zypper", "install", "-y", "snapd"], elevated=True)


class PacmanManager(SystemsManagerBase):  # Arch
    def __init__(self, silent: bool = False, log_file: str = None):
        super().__init__(silent, log_file)
        self.not_found_msg = "target not found"

    def install_applications(self, apps: List[str]):
        for app in apps:
            try:
                self.run_command(["pacman", "-S", "--noconfirm", app], elevated=True)
            except subprocess.CalledProcessError as e:
                if self.not_found_msg in e.stderr:
                    if not self.silent:
                        print(f"Falling back to Snap for {app}...")
                    self.logger.info(
                        f"Native install failed for {app}; falling back to Snap..."
                    )
                    self.install_via_snap(app)
                else:
                    raise  # Re-raise for other errors

    def update(self):
        self.run_command(["pacman", "-Syu", "--noconfirm"], elevated=True)

    def clean(self):
        self.run_command(["pacman", "-Sc", "--noconfirm"], elevated=True)

    def optimize(self):
        self.run_command(
            ["pacman", "-Rns", "$(pacman -Qdtq)", "--noconfirm"],
            elevated=True,
            shell=True,
        )

    def install_snapd(self):
        self.run_command(["pacman", "-S", "--noconfirm", "snapd"], elevated=True)


class WindowsManager(SystemsManagerBase):
    def __init__(self, silent: bool = False, log_file: str = None):
        super().__init__(silent, log_file)
        # Ensure winget is available (simplified)
        winget_path = os.path.expanduser(
            r"~\AppData\Local\Microsoft\WindowsApps\winget.exe"
        )
        if not os.path.exists(winget_path):
            print("Installing Winget...")
            self.run_command(
                [
                    "powershell.exe",
                    "Invoke-WebRequest",
                    "-Uri",
                    "https://aka.ms/getwinget",
                    "-OutFile",
                    "winget.msixbundle",
                ]
            )
            self.run_command(
                ["powershell.exe", "Add-AppPackage", "-Path", "winget.msixbundle"]
            )

    def install_applications(self, apps: List[str]):
        for app in apps:
            self.run_command(
                [
                    "winget",
                    "install",
                    "--id",
                    app,
                    "--silent",
                    "--accept-package-agreements",
                    "--accept-source-agreements",
                ]
            )

    def update(self):
        self.run_command(
            [
                "winget",
                "upgrade",
                "--all",
                "--silent",
                "--accept-package-agreements",
                "--accept-source-agreements",
            ]
        )
        self.run_command(
            ["powershell.exe", "Install-Module", "PSWindowsUpdate", "-Force"]
        )
        self.run_command(
            ["powershell.exe", "Install-WindowsUpdate", "-AcceptAll", "-AutoReboot"]
        )

    def clean(self):
        self.run_command(["cleanmgr", "/lowdisk"])

    def optimize(self):
        self.run_command(["cleanmgr", "/lowdisk"])
        self.run_command(["defrag", "C:", "/O"])

    def list_windows_features(self) -> List[Dict]:
        result = self.run_command(
            ["powershell.exe", "Get-WindowsOptionalFeature", "-Online"], shell=True
        )
        features = []
        lines = result.stdout.splitlines()
        current_feature = {}
        for line in lines:
            if line.strip() == "":
                if current_feature:
                    features.append(current_feature)
                current_feature = {}
            elif ":" in line:
                key, value = line.split(":", 1)
                current_feature[key.strip()] = value.strip()
        if current_feature:
            features.append(current_feature)
        print(json.dumps(features, indent=2))
        self.logger.info(f"Listed Windows features: {json.dumps(features)}")
        return features

    def enable_windows_features(self, features: List[str]):
        for feature in features:
            self.run_command(
                [
                    "powershell.exe",
                    "Enable-WindowsOptionalFeature",
                    "-Online",
                    "-FeatureName",
                    feature,
                    "-NoRestart",
                ],
                elevated=True,
            )

    def disable_windows_features(self, features: List[str]):
        for feature in features:
            self.run_command(
                [
                    "powershell.exe",
                    "Disable-WindowsOptionalFeature",
                    "-Online",
                    "-FeatureName",
                    feature,
                    "-NoRestart",
                ],
                elevated=True,
            )

    def install_snapd(self):
        raise NotImplementedError("Snap not supported on Windows")


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
    print(
        """
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

Example:
systems-manager --fonts Hack,Meslo --update --clean --python geniusbot --install python3,git --enable-features Microsoft-Hyper-V-All,Containers --log-file /path/to/log.log
"""
    )


def main(argv):
    log_file = None
    apps = []
    python_modules = []
    enable_features_list = []
    disable_features_list = []
    fonts = ["Hack"]  # Default to Hack
    install = False
    font = False
    update = False
    clean = False
    optimize = False
    install_python = False
    os_stats = False
    hw_stats = False
    silent = False
    list_features = False
    enable_features = False
    disable_features = False

    try:
        opts, _ = getopt.getopt(
            argv,
            "hcfsi:p:uoeld:",
            [
                "help",
                "clean",
                "fonts=",
                "silent",
                "update",
                "install=",
                "python=",
                "optimize",
                "os-stats",
                "hw-stats",
                "enable-features=",
                "disable-features=",
                "list-features",
                "log-file=",
            ],
        )
    except getopt.GetoptError:
        usage()
        sys.exit(2)

    for opt, arg in opts:
        if opt in ("-h", "--help"):
            usage()
            sys.exit()
        elif opt in ("-c", "--clean"):
            clean = True
        elif opt in ("-f", "--fonts"):
            font = True
            fonts = arg.split(",")
        elif opt in ("-i", "--install"):
            install = True
            apps = arg.split(",")
        elif opt in ("-p", "--python"):
            install_python = True
            python_modules = arg.split(",")
        elif opt in ("-s", "--silent"):
            silent = True
        elif opt in ("-u", "--update"):
            update = True
        elif opt in ("-o", "--optimize"):
            optimize = True
        elif opt == "--os-stats":
            os_stats = True
        elif opt == "--hw-stats":
            hw_stats = True
        elif opt in ("-e", "--enable-features"):
            enable_features = True
            enable_features_list = arg.split(",")
        elif opt in ("-d", "--disable-features"):
            disable_features = True
            disable_features_list = arg.split(",")
        elif opt in ("-l", "--list-features"):
            list_features = True
        elif opt == "--log-file":
            log_file = arg

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
    if os_stats:
        print(json.dumps(manager.get_os_stats(), indent=2))
    if hw_stats:
        print(json.dumps(manager.get_hardware_stats(), indent=2))
    if list_features:
        if isinstance(manager, WindowsManager):
            manager.list_windows_features()
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
    if len(sys.argv) < 2:
        usage()
        sys.exit(2)
    main(sys.argv[1:])
