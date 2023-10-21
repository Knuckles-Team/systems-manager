#!/usr/bin/env python
# coding: utf-8

import sys
import getopt
import subprocess
import os
import platform
import requests
import zipfile
import glob
import json
import shutil

try:
    from systems_manager.version import __version__, __author__, __credits__
except:
    from version import __version__, __author__, __credits__


class SystemsManager:
    def __init__(self, silent=False):
        self.system = platform.system()
        self.release = platform.release()
        self.version = platform.version()
        self.operating_system = None
        self.result = None
        self.get_operating_system()
        self.silent = silent
        self.applications = None
        self.bash_profile = ""
        self.ubuntu_install_command = []
        self.windows_install_command = []
        self.set_applications(self.applications)
        self.ubuntu_update_command = [['apt', 'update'], ['apt', 'upgrade', '-y'], ['apt', 'autoremove', '-y']]
        if os.path.isfile(os.path.expanduser("~\AppData\Local\Microsoft\WindowsApps\winget.exe")):
            self.windows_update_command = [
                ['winget', 'upgrade', '--all', '--silent', '--accept-package-agreements', '--accept-source-agreements'],
                ["powershell.exe", 'Install-Module', 'PSWindowsUpdate', 'Force'],
                ["powershell.exe", 'Get-WindowsUpdate'], ["powershell.exe", 'Install-WindowsUpdate']
            ]
        else:
            self.windows_update_command = [
                ["powershell.exe", 'Start-Process', '"ms-appinstaller:?source=https://aka.ms/getwinget"'],
                ["powershell.exe", '$nid', '=', '(Get-Process AppInstaller).Id'],
                ["powershell.exe", 'Wait-Process', '-Id', '$nid'], ['winget', 'upgrade', '--all'],
                ["powershell.exe", 'Install-Module', 'PSWindowsUpdate', 'Force'],
                ["powershell.exe", 'Get-WindowsUpdate'],
                ["powershell.exe", 'Install-WindowsUpdate']
            ]
        self.windows_features = None
        self.script_path = os.path.normpath(os.path.dirname(__file__))
        self.enable_windows_features_command = [['powershell.exe', 'Set-ExecutionPolicy', '-ExecutionPolicy', 'RemoteSigned', '-Scope', 'CurrentUser']]
        self.set_features(features=self.windows_features)
        self.ubuntu_clean_command = [['apt', 'install', '-y', 'trash-cli'], ['trash-empty']]
        self.windows_clean_command = [['cleanmgr', '/lowdisk']]
        self.ubuntu_optimize_command = [['apt', 'autoremove', '-y'], ['apt', 'autoclean']]
        self.windows_optimize_command = [['cleanmgr', '/lowdisk']]
        self.python_modules = None
        self.install_python_modules_command = [['python', '-m', 'pip', 'install', '--upgrade', 'pip']]
        self.set_python_modules(self.python_modules)
        if self.operating_system == "Ubuntu":
            self.install_command = self.ubuntu_install_command
            self.update_command = self.ubuntu_update_command
            self.clean_command = self.ubuntu_clean_command
            self.optimize_command = self.ubuntu_optimize_command
        elif self.operating_system == "Windows":
            self.install_command = self.windows_install_command
            self.update_command = self.windows_update_command
            self.clean_command = self.windows_clean_command
            self.optimize_command = self.windows_optimize_command

    def install_applications(self):
        if self.install_command:
            print(f"FULL COMMAND: {self.install_command}")
            for install_single_command in self.install_command:
                print(f"Single: {install_single_command}")
                self.run_command(install_single_command)
                if 'Try "snap install' in self.result.stdout:
                    install_single_command[0] = "snap"
                    install_single_command.remove('-y')
                    self.run_command(install_single_command)
                print(self.result.returncode, self.result.stdout, self.result.stderr)

    def install_python_modules(self):
        if self.install_python_modules_command:
            for install_single_python_module_command in self.install_python_modules_command:
                self.run_command(install_single_python_module_command)
                print(self.result.returncode, self.result.stdout, self.result.stderr)

    def update(self):
        if self.update_command:
            for update_single_command in self.update_command:
                self.run_command(update_single_command)
                print(self.result.returncode, self.result.stdout, self.result.stderr)

    def clean(self):
        if self.clean_command:
            for clean_single_command in self.clean_command:
                self.run_command(clean_single_command)
                print(self.result.returncode, self.result.stdout, self.result.stderr)

    def enable_windows_features(self):
        if self.enable_windows_features_command:
            for enable_windows_features_single_command in self.enable_windows_features_command:
                self.run_command(enable_windows_features_single_command)
                print(self.result.returncode, self.result.stdout, self.result.stderr)

    def optimize(self):
        if self.optimize_command:
            for optimize_single_command in self.optimize_command:
                self.run_command(optimize_single_command)
                print(self.result.returncode, self.result.stdout, self.result.stderr)

    def font(self):
        if self.operating_system == "Ubuntu":
            install_dependencies_command = ['sudo', 'apt', 'install', '-y', 'fontconfig']
            self.run_command(command=install_dependencies_command)
            font_path = os.path.expanduser('~/.fonts')
            extract_path = font_path
            if not os.path.exists(font_path):
                os.makedirs(font_path)
            meslo_file_name = 'Meslo.zip'
            url = 'https://github.com/ryanoasis/nerd-fonts/releases/download/v2.1.0/' + meslo_file_name
            r = requests.get(url)
            try:
                open(meslo_file_name, 'wb').write(r.content)
            except Exception as e:
                meslo_file_name = os.path.expanduser('~/Downloads/Meslo.zip')
                open(meslo_file_name, 'wb').write(r.content)
            with zipfile.ZipFile(meslo_file_name, 'r') as zip_ref:
                zip_ref.extractall(extract_path)
            hack_file_name = 'Hack.zip'
            url = 'https://github.com/ryanoasis/nerd-fonts/releases/download/v2.1.0/' + hack_file_name
            r = requests.get(url)

            try:
                open(hack_file_name, 'wb').write(r.content)
            except Exception as e:
                hack_file_name = os.path.expanduser('~/Downloads/Hack.zip')
                open(hack_file_name, 'wb').write(r.content)
            with zipfile.ZipFile(hack_file_name, 'r') as zip_ref:
                zip_ref.extractall(extract_path)

            font_command = ['fc-cache', '-fv']
            self.run_command(font_command)
            print(self.result.returncode, self.result.stdout, self.result.stderr)

        elif self.operating_system == "Windows":
            font_path = os.path.expanduser(r'C:\Windows\Fonts')
            extract_path = "."
            if not os.path.exists(font_path):
                os.makedirs(font_path)
            meslo_file_name = 'Meslo.zip'
            url = 'https://github.com/ryanoasis/nerd-fonts/releases/download/v3.0.0/' + meslo_file_name
            r = requests.get(url)
            open(meslo_file_name, 'wb').write(r.content)
            with zipfile.ZipFile(meslo_file_name, 'r') as zip_ref:
                zip_ref.extractall(extract_path)
            hack_file_name = 'Hack.zip'
            url = 'https://github.com/ryanoasis/nerd-fonts/releases/download/v3.0.0/' + hack_file_name
            r = requests.get(url)
            open(hack_file_name, 'wb').write(r.content)
            with zipfile.ZipFile(hack_file_name, 'r') as zip_ref:
                zip_ref.extractall(extract_path)
            font_files = glob.glob('./*.ttf')
            font_files = font_files + glob.glob('./*/*.ttf')
            print(f"All font files: {font_files}")
            for font_file in font_files:
                print(f"Moving font {os.path.normpath(font_file)} "
                      f"to: {os.path.normpath(os.path.join(font_path, os.path.basename(font_file)))}")
                shutil.move(os.path.normpath(font_file),
                            os.path.normpath(os.path.join(font_path, os.path.basename(font_file))))
            os.remove(meslo_file_name)
            os.remove(hack_file_name)

    def theme(self):
        if self.operating_system == "Ubuntu":
            install_dependencies_command = ['sudo', 'apt', 'install', '-y', 'fontconfig', 'unzip']
            self.run_command(command=install_dependencies_command)
            oh_my_posh_file = '/usr/local/bin/oh-my-posh'
            url = "https://github.com/JanDeDobbeleer/oh-my-posh/releases/latest/download/posh-linux-amd64"
            r = requests.get(url)
            open(oh_my_posh_file, 'wb').write(r.content)
            themes_file = os.path.expanduser(r'~/.poshthemes/themes.zip')
            theme_path = os.path.expanduser(r'~/.poshthemes')
            extract_path = theme_path
            if not os.path.exists(theme_path):
                os.makedirs(theme_path)
            url = "https://github.com/JanDeDobbeleer/oh-my-posh/releases/latest/download/themes.zip"
            r = requests.get(url)
            open(themes_file, 'wb').write(r.content)
            with zipfile.ZipFile(themes_file, 'r') as zip_ref:
                zip_ref.extractall(extract_path)
            os.remove(themes_file)
            self.bash_profile = os.path.expanduser(r'~/.bashrc')
            with open(self.bash_profile, "r+") as file:
                for line in file:
                    if 'eval "$(oh-my-posh --init --shell bash --config ' in line:
                        break
                else:
                    file.write('eval "$(oh-my-posh --init --shell bash --config ~/.poshthemes/takuya.omp.json)"')
            theme_commands = [['chmod', '+x', '/usr/local/bin/oh-my-posh'],
                              ['chmod', 'u+rw', '~/.poshthemes/*.json'],
                              ['source', '~/.bashrc']]
            for theme_command in theme_commands:
                self.run_command(theme_command)
                print(self.result.returncode, self.result.stdout, self.result.stderr)

        elif self.operating_system == "Windows":
            theme_commands = [
                ['powershell.exe', 'Install-PackageProvider', '-Name', 'NuGet', '-Force'],
                ['winget', 'install', '--accept-package-agreements', '--accept-source-agreements', 'JanDeDobbeleer.OhMyPosh', '-s', 'winget'],
                ['winget', 'install', '--accept-package-agreements', '--accept-source-agreements', 'fzf'],
                ['powershell.exe', 'Install-Module', 'Terminal-Icons', '-Repository', 'PSGallery', '-Force'],
                ['powershell.exe', 'Install-Module', '-Name', 'z', '-Force', '-AllowClobber'],
                ['powershell.exe', 'Install-Module', '-Name', 'PSReadLine', '-Force', '-SkipPublisherCheck'],
                ['powershell.exe', 'Install-Module', '-Name', 'PSFzf', '-Force'],
                ['powershell.exe', 'New-Item', '-ItemType', 'SymbolicLink', '-Path', '(Join-Path', '-Path',
                 '$Env:USERPROFILE', '-ChildPath', 'Documents)', '-Name', 'PowerShell', '-Target', '(Join-Path',
                 '-Path', '$Env:USERPROFILE', '-ChildPath', 'Documents\WindowsPowerShell)']]
            for theme_command in theme_commands:
                self.run_command(theme_command)
                print(self.result.returncode, self.result.stdout, self.result.stderr)
            config_path = os.path.normpath(os.path.expanduser("~/.config"))
            if not os.path.exists(config_path):
                os.makedirs(config_path)
                os.makedirs(config_path + "/powershell")

            user_profile_file = os.path.normpath(os.path.join(config_path, "powershell", "user_profile.ps1"))
            user_profile_content = r'''# set PowerShell to UTF-8
[console]::InputEncoding = [console]::OutputEncoding = New-Object System.Text.UTF8Encoding
$omp_config = Join-Path $PSScriptRoot ".\takuya.omp.json"
oh-my-posh init pwsh --config $omp_config | Invoke-Expression
Import-Module -Name Terminal-Icons
# PSReadLine
Set-PSReadLineOption -EditMode Emacs
Set-PSReadLineOption -BellStyle None
Set-PSReadLineKeyHandler -Chord "Ctrl+d" -Function DeleteChar
Set-PSReadLineOption -PredictionSource History
# Fzf
Import-Module PSFzf
Set-PsFzfOption -PSReadlineChordProvider "Ctrl+f" -PSReadlineChordReverseHistory "Ctrl+r"
# Env
$env:GIT_SSH = "C:\Windows\system32\OpenSSH\ssh.exe"
# Alias'
Set-Alias -Name vim -Value nvim
Set-Alias ll ls
Set-Alias g git
Set-Alias grep findstr
Set-Alias tig "C:\Program Files\Git\usr\bin\tig.exe"
Set-Alias less "C:\Program Files\Git\usr\bin\less.exe"
# Utilities
function which ($command) {
Get-Command -Name $command -ErrorAction SilentlyContinue |
Select-Object -ExpandProperty Path -ErrorAction SilentlyContinue
}'''

            print(f"Set User Profile: {user_profile_file}")
            with open(user_profile_file, "w") as outfile:
                outfile.write(user_profile_content)

            takuya_omp_data = {
                "$schema": "https://raw.githubusercontent.com/JanDeDobbeleer/oh-my-posh/main/themes/schema.json",
                "blocks": [
                    {
                        "alignment": "left",
                        "segments": [
                            {
                                "background": "#0077c2",
                                "foreground": "#ffffff",
                                "leading_diamond": "\u256d\u2500\ue0b6",
                                "style": "diamond",
                                "template": " {{ .Name }} ",
                                "type": "shell"
                            },
                            {
                                "background": "#ef5350",
                                "foreground": "#FFFB38",
                                "properties": {
                                    "root_icon": "\uf292"
                                },
                                "style": "diamond",
                                "template": "<parentBackground>\ue0b0</> \uf0e7 ",
                                "type": "root"
                            },
                            {
                                "background": "#444444",
                                "foreground": "#E4E4E4",
                                "powerline_symbol": "\ue0b0",
                                "properties": {
                                    "style": "full"
                                },
                                "style": "powerline",
                                "template": " {{ .Path }} ",
                                "type": "path"
                            },
                            {
                                "background": "#FFFB38",
                                "background_templates": [
                                    "{{ if or (.Working.Changed) (.Staging.Changed) }}#ffeb95{{ end }}",
                                    "{{ if and (gt .Ahead 0) (gt .Behind 0) }}#c5e478{{ end }}",
                                    "{{ if gt .Ahead 0 }}#C792EA{{ end }}",
                                    "{{ if gt .Behind 0 }}#C792EA{{ end }}"
                                ],
                                "foreground": "#011627",
                                "powerline_symbol": "\ue0b0",
                                "properties": {
                                    "branch_icon": "\ue725 ",
                                    "fetch_status": True,
                                    "fetch_upstream_icon": True
                                },
                                "style": "powerline",
                                "template": " {{ .HEAD }} {{ if .Working.Changed }}{{ .Working.String }}{{ end }}"
                                            "{{ if and (.Working.Changed) (.Staging.Changed) }} "
                                            "|{{ end }}{{ if .Staging.Changed }}<#ef5350> \uf046 "
                                            "{{ .Staging.String }}</>{{ end }} ",
                                "type": "git"
                            }
                        ],
                        "type": "prompt"
                    },
                    {
                        "alignment": "right",
                        "segments": [
                            {
                                "background": "#303030",
                                "foreground": "#3C873A",
                                "leading_diamond": " \ue0b6",
                                "properties": {
                                    "fetch_package_manager": True,
                                    "npm_icon": " <#cc3a3a>\ue5fa</> ",
                                    "yarn_icon": " <#348cba>\uf61a</>"
                                },
                                "style": "diamond",
                                "template": "\ue718 {{ if .PackageManagerIcon }}{{ .PackageManagerIcon }} "
                                            "{{ end }}{{ .Full }}",
                                "trailing_diamond": "\ue0b4",
                                "type": "node"
                            },
                            {
                                "background": "#40c4ff",
                                "foreground": "#ffffff",
                                "invert_powerline": True,
                                "leading_diamond": " \ue0b6",
                                "style": "diamond",
                                "template": " \uf5ef {{ .CurrentDate | date .Format }} ",
                                "trailing_diamond": "\ue0b4",
                                "type": "time"
                            }
                        ],
                        "type": "prompt"
                    },
                    {
                        "alignment": "left",
                        "newline": True,
                        "segments": [
                            {
                                "foreground": "#21c7c7",
                                "style": "plain",
                                "template": "\u2570\u2500",
                                "type": "text"
                            },
                            {
                                "foreground": "#e0f8ff",
                                "foreground_templates": [
                                    "{{ if gt .Code 0 }}#ef5350{{ end }}"
                                ],
                                "properties": {
                                    "always_enabled": True
                                },
                                "style": "plain",
                                "template": "\u276f{{ if gt .Code 0 }}\uf00d{{ else }}\uf42e{{ end }} ",
                                "type": "exit"
                            }
                        ],
                        "type": "prompt"
                    }
                ],
                "osc99": True,
                "version": 2
            }

            with open(config_path + "/powershell/takuya.omp.json", 'w') as f:
                json.dump(takuya_omp_data, f, indent=4)

            windows_terminal_settings_file = None
            settings_file = "~\AppData\Local\Packages\Microsoft.WindowsTerminal_*\LocalState\settings.json"
            for file in glob.glob(os.path.expanduser(settings_file)):
                windows_terminal_settings_file = file

            if not windows_terminal_settings_file:
                print(f"File was not found: {windows_terminal_settings_file}")
                return
            with open(windows_terminal_settings_file, 'r') as f:
                windows_terminal_settings_json = json.load(f)

            smooth_blues_data = {
                "background": "#001B26",
                "black": "#282C34",
                "blue": "#61AFEF",
                "brightBlack": "#5A6374",
                "brightBlue": "#61AFEF",
                "brightCyan": "#56B6C2",
                "brightGreen": "#98C379",
                "brightPurple": "#C678DD",
                "brightRed": "#E06C75",
                "brightWhite": "#DCDFE4",
                "brightYellow": "#E5C07B",
                "cursorColor": "#FFFFFF",
                "cyan": "#56B6C2",
                "foreground": "#DCDFE4",
                "green": "#98C379",
                "name": "Smooth Blues",
                "purple": "#C678DD",
                "red": "#E06C75",
                "selectionBackground": "#FFFFFF",
                "white": "#DCDFE4",
                "yellow": "#E5C07B"
            }

            windows_terminal_settings_json['schemes'].append(smooth_blues_data)
            windows_terminal_settings_json['profiles']['defaults']['colorScheme'] = "Smooth Blues"
            windows_terminal_settings_json['profiles']['defaults']['font'] = {'face': 'Hack Nerd Font'}
            windows_terminal_settings_json['profiles']['defaults']['opacity'] = 35
            windows_terminal_settings_json['profiles']['defaults']['useAcrylic'] = True

            with open(windows_terminal_settings_file, 'w') as f:
                json.dump(windows_terminal_settings_json, f, indent=4)

            user_profile_file = '~\Documents\WindowsPowerShell\Microsoft.PowerShell_profile.ps1'
            with open(os.path.expanduser(user_profile_file), "w") as file:
                try:
                    for line in file:
                        if r'. $env:USERPROFILE\.config\powershell\user_profile.ps1' in line:
                            break
                    else:
                        file.write(r'. $env:USERPROFILE\.config\powershell\user_profile.ps1')
                except Exception as e:
                    try:
                        file.write(r'. $env:USERPROFILE\.config\powershell\user_profile.ps1')
                    except Exception as f:
                        print(f"Error Saving Profile: \nError 1: {e} \nError 2: {f}")

    def set_startup_programs(self):
        if self.operating_system == "Ubuntu":
            self.run_command(command=['echo', 'Set Startup Program?'])
            print(self.result.returncode, self.result.stdout, self.result.stderr)
        elif self.operating_system == "Windows":
            self.run_command(command=['powershell.exe', 'Copy-Item',
                                       'C:\ProgramData\Microsoft\Windows\Start Menu\Programs\System Tools\Task Manager',
                                       '-Destination',
                                       '%SystemDrive%\ProgramData\Microsoft\Windows\Start Menu\Programs\Startup'])
            print(self.result.returncode, self.result.stdout, self.result.stderr)

    def run_command(self, command):
        try:
            if self.silent:
                self.result = subprocess.run(command, stdout=open(os.devnull, 'wb'), stderr=open(os.devnull, 'wb'))
            else:
                print("Running Command: ", command)
                self.result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                             universal_newlines=True)
        except subprocess.CalledProcessError as e:
            print(e.output)

    def get_operating_system(self):
        if "ubuntu" in str(self.version).lower() or "smp" in str(self.version).lower():
            self.operating_system = "Ubuntu"
        elif "windows" in str(self.system).lower() and ("10" in self.release or "11" in self.release):
            self.operating_system = "Windows"
        return self.operating_system

    def get_silent(self):
        return self.silent

    def set_silent(self, silent=False):
        self.silent = silent

    def get_applications(self):
        return self.applications

    def set_applications(self, applications):
        if applications is None or len(applications) == 0:
            if self.operating_system == "Ubuntu":
                self.applications = ["discord", "dos2unix", "python3"]
            elif self.operating_system == "Windows":
                self.applications = ["Python.Python.3"]
            else:
                self.applications = ["dos2unix", "python3"]
        elif applications == "all" or "all" in applications:
            if self.operating_system == "Ubuntu":
                print("Set all apps")
                self.applications = [
                    "atomicparsley", "audacity", "curl", "dialog", "discord", "docker", "dos2unix", "enscript",
                    "ffmpeg", "fstab", "gimp", "git",
                    "gnome-shell", "rustc",
                    "ubuntu-gnome-desktop", "gnome-theme", "gnucobol", "ghostscript", "gparted", "gramps", "jq", "k3s",
                    "kexi",
                    "kvm", "lm-sensors", "mediainfo", "mkvtoolnix", "neofetch", "nfs-common", "nfs-kernel-server",
                    "net-tools",
                    "openjdk-8-jdk", "nmap", "openssh-server", "openvpn", "preload", "poppler-utils", "python3",
                    "python3-is-python", "pycharm", "rygel", "samba", "samba-common", "smbclient samba-common-bin",
                    "smbclient", "cifs-utils", "scrcpy", "sysstat", "net-tools", "numactl",
                    "linux-tools-common", "steam", "startup-disk-creator", "update-manager", "synaptic", "telegram",
                    "tesseract", "tigervnc", "tmux", "transmission", "translate-shell", "trash-cli", "tree", "unzip",
                    "udisks2", "vlc", "wine", "wireshark", "wget", "xdotool", "xpaint", "xsel", "yq"
                ]
            elif self.operating_system == "Windows":
                self.applications = [
                    "Git.Git", "oh-my-posh", "Discord.Discord", "Microsoft.VCRedist.2015+.x64",
                    "Microsoft.VCRedist.2015+.x86", "WireGuard.WireGuard",
                    "Microsoft.VCRedist.2013.x64", "Microsoft.VisualStudioCode", "TheDocumentFoundation.LibreOffice",
                    "Adobe.Acrobat.Reader.64-bit", "Audacity.Audacity", "Google.Chrome", "Balena.Etcher",
                    "Mozilla.Firefox",
                    "GIMP.GIMP", "AdoptOpenJDK.OpenJDK.8", "AdoptOpenJDK.OpenJDK.16", "Oracle.JDK.18",
                    "JetBrains.Toolbox", "OpenJS.NodeJS", "OpenJS.NodeJS.LTS", "clsid2.mpc-hc", "Notepad++.Notepad++",
                    "Microsoft.PowerToys", "PuTTY.PuTTY", "7zip.7zip", "Rustlang.Rust.MSVC",
                    "Microsoft.WindowsTerminal",
                    "Rustlang.Rust.GNU", "VideoLAN.VLC", "VSCodium.VSCodium", "BlenderFoundation.Blender",
                    "Element.Element",
                    "mRemoteNG.mRemoteNG", "TechPowerUp.NVstall", "OBSProject.OBSStudio", "Obsidian.Obsidian",
                    "RevoUninstaller.RevoUninstaller", "Valve.Steam", "WiresharkFoundation.Wireshark",
                    "Emulationstation.Emulationstation", "Libretro.RetroArch"
                ]
            else:
                print("Set all apps")
                self.applications = [
                    "atomicparsley", "audacity", "curl", "dialog", "discord", "docker", "dos2unix", "enscript",
                    "ffmpeg", "fstab", "gimp", "git",
                    "gnome-shell", "rustc",
                    "ubuntu-gnome-desktop", "gnome-theme", "gnucobol", "ghostscript", "gparted", "gramps", "jq", "kexi",
                    "kvm", "lm-sensors", "mediainfo", "mkvtoolnix", "neofetch", "nfs-common", "nfs-kernel-server",
                    "net-tools",
                    "openjdk-8-jdk", "nmap", "openssh-server", "openvpn", "preload", "poppler-utils", "python3",
                    "python3-is-python", "pycharm", "rygel", "samba", "samba-common", "smbclient samba-common-bin",
                    "smbclient", "cifs-utils", "scrcpy", "sysstat", "net-tools", "numactl",
                    "linux-tools-common", "steam", "startup-disk-creator", "update-manager", "synaptic", "telegram",
                    "tesseract", "tigervnc", "tmux", "transmission", "translate-shell", "trash-cli", "tree", "unzip",
                    "udisks2", "vlc", "wine", "wireshark", "wget", "xdotool", "xpaint", "xsel", "yq"
                ]
        else:
            self.applications = applications

        for application in self.applications:
            ubuntu_install_commands = [['apt', 'install', '-y', f'{application}']]
            if application.lower() == "docker" and self.operating_system == "Ubuntu":
                ubuntu_install_commands = [
                    ['apt', 'remove', 'docker', 'docker-engine', 'docker.io', 'containerd', 'runc'],
                    ['apt', 'update'],
                    ['apt', 'install', '-y', 'ca-certificates', 'curl', 'gnupg'],
                    ['install', '-m', '0755', '-d', '/etc/apt/keyrings'],
                    ['curl', '-fsSL', 'https://download.docker.com/linux/ubuntu/gpg', '|', 'gpg', '--dearmor', '-o',
                     '/etc/apt/keyrings/docker.gpg'],
                    ['chmod', 'a+r', '/etc/apt/keyrings/docker.gpg'],
                    ['echo',
                     '"deb [arch="$(dpkg --print-architecture)" signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME")" stable"',
                     '|', 'tee', '/etc/apt/sources.list.d/docker.list', '>', '/dev/null'],
                    ['apt', 'update'],
                    ['apt', 'install', '-y', 'docker-ce', 'docker-ce-cli', 'containerd.io', 'docker-buildx-plugin',
                     'docker-compose-plugin']]
            if application.lower() == "k3s" and self.operating_system == "Ubuntu":
                    ubuntu_install_commands = [
                        ['wget', '-O', f'{self.script_path}/k3s.sh', 'https://get.k3s.io'],
                        ['bash', f'{self.script_path}/k3s.sh', '--write-kubeconfig-mode', '644'],
                        ['rm', '-f', f'{self.script_path}/k3s.sh']
                    ]
            elif application.lower() == "wireshark" and self.operating_system == "Ubuntu":
                ubuntu_install_commands = [
                    ['echo', '"wireshark-common wireshark-common/install-setuid boolean true"', '|',
                     'debconf-set-selections'],
                    ['DEBIAN_FRONTEND=noninteractive', 'apt', '-y', 'install', 'wireshark']]
            elif self.operating_system == "Ubuntu":
                ubuntu_install_commands = [['apt', 'install', '-y', f'{application}']]

            for ubuntu_install_command in ubuntu_install_commands:
                self.ubuntu_install_command.append(ubuntu_install_command)
            self.windows_install_command.append(
                ['winget', 'install', '--accept-package-agreements', '--accept-source-agreements', f'{application}'])

    def get_features(self):
        return self.windows_features

    def set_features(self, features):
        if features is None or len(features) == 0:
            self.windows_features = [
                "Microsoft-Hyper-V-All", "Microsoft-Hyper-V", "Microsoft-Hyper-V-Management-PowerShell",
                "Microsoft-Hyper-V-Hypervisor", "Microsoft-Hyper-V-Management-Clients", "Microsoft-Hyper-V-Services",
                "Microsoft-Hyper-V-Tools-All", "ServicesForNFS-ClientOnly", "ClientForNFS-Infrastructure",
                "NFS-Administration", "TFTP", "Containers", "SmbDirect", "SMB1Protocol", "SMB1Protocol-Client",
                "SMB1Protocol-Server", "SMB1Protocol-Deprecation", "Containers-DisposableClientVM",
                "HypervisorPlatform", "VirtualMachinePlatform", "Microsoft-Windows-Subsystem-Linux",
                "MicrosoftWindowsPowerShellV2", "MicrosoftWindowsPowerShellV2Root"]
        elif features == "all":
            self.windows_features = [
                "Microsoft-Hyper-V-All", "Microsoft-Hyper-V", "Microsoft-Hyper-V-Management-PowerShell",
                "Microsoft-Hyper-V-Hypervisor", "Microsoft-Hyper-V-Management-Clients", "Microsoft-Hyper-V-Services",
                "Microsoft-Hyper-V-Tools-All", "ServicesForNFS-ClientOnly", "ClientForNFS-Infrastructure",
                "NFS-Administration", "TFTP", "Containers", "SmbDirect", "SMB1Protocol", "SMB1Protocol-Client",
                "SMB1Protocol-Server", "SMB1Protocol-Deprecation", "Containers-DisposableClientVM",
                "HypervisorPlatform", "VirtualMachinePlatform", "Microsoft-Windows-Subsystem-Linux",
                "MicrosoftWindowsPowerShellV2", "MicrosoftWindowsPowerShellV2Root"]
        else:
            self.windows_features = features

        for feature in self.windows_features:
            self.enable_windows_features_command.append(
                ['powershell.exe', 'Enable-WindowsOptionalFeature', '-Online', '-FeatureName', f'{feature}', '-NoRestart'])

    def set_python_modules(self, modules):
        if modules is None or len(modules) == 0:
            self.python_modules = ["geniusbot"]
        elif modules == "all":
            self.python_modules = ["geniusbot", "repository-manager", "subshift", "webarchiver", "report-manager",
                                   "media-downloader", "media-manager"]
        else:
            self.python_modules = modules

        for module in self.python_modules:
            self.install_python_modules_command.append(['python', '-m', 'pip', 'install', '--upgrade', f'{module}'])


def usage():
    print(f'Systems-Manager: A tool to manage your systems software!\n'
          f'Version: {__version__}\n'
          f'Author: {__author__}\n'
          f'Credits: {__credits__}\n'
          f"\nUsage: \n"
          f"-h | --help            [ See usage for script ]\n"
          f"-c | --clean           [ Clean Recycle/Trash bin ]\n"
          f"-e | --enable-features [ Enable Window Features ]\n"
          f"-f | --font            [ Install 'Hack Nerd Font' ]\n"
          f"-i | --install         [ Install applications ]\n"
          f"-p | --python          [ Install Python Modules ]\n"
          f"-s | --silent          [ Don't print to stdout ]\n"
          f"-t | --theme           [ Apply Takuyuma Terminal Theme ]\n"
          f"-u | --update          [ Update your applications and Operating System ]\n"
          f"\nExample: \n"
          f"systems-manager --font --update --clean --theme --python 'geniusbot' --install 'python3'\n")


def systems_manager(argv):
    system_manager_instance = SystemsManager()
    applications = []
    features = []
    python_modules = []
    install = False
    enable_features = False
    silent = False
    font = False
    theme = False
    update = False
    clean = False
    install_python_modules = False
    optimize = False
    start_up = False
    try:
        opts, args = getopt.getopt(argv, "hcfstue:i:p:",
                                   ["help", "clean", "font", "silent", "theme", "update",
                                    "enable-features=", "install=", "python="])
    except getopt.GetoptError:
        usage()
        print(f"Applications Available: {system_manager_instance.get_applications()}")
        print(f"Windows Features Available: {system_manager_instance.get_features()}")
        sys.exit(2)
    for opt, arg in opts:
        if opt in ("-h", "--help"):
            usage()
            print(f"Applications Available: {system_manager_instance.get_applications()}")
            print(f"Windows Features Available: {system_manager_instance.get_features()}")
            sys.exit()
        elif opt in ("-c", "--clean"):
            clean = True
        elif opt in ("-e", "--enable-features"):
            enable_features = True
            features = arg.lower()
            features = features.replace(" ", "")
            features = features.split(",")
        elif opt in ("-i", "--install"):
            install = True
            applications = arg.lower()
            applications = applications.replace(" ", "")
            applications = applications.split(",")
        elif opt in ("-f", "--font"):
            font = True
        elif opt in ("-p", "--python"):
            install_python_modules = True
            python_modules = arg.lower()
            python_modules = python_modules.replace(" ", "")
            python_modules = python_modules.split(",")
        elif opt in ("-s", "--silent"):
            silent = True
        elif opt in ("-u", "--update"):
            update = True
        elif opt in ("-t", "--theme"):
            theme = True

    if silent:
        print("Setting Silent...")
        system_manager_instance.set_silent(silent=silent)

    if update:
        print("Performing Update...")
        system_manager_instance.update()

    if enable_features:
        print(f"Setting features: {features}")
        system_manager_instance.set_features(features=features)
        print("Enabling Windows Features...")
        system_manager_instance.enable_windows_features()

    if install:
        print(f"Setting applications: {applications}")
        system_manager_instance.set_applications(applications=applications)
        print("Installing...")
        system_manager_instance.install_applications()

    if install_python_modules:
        print(f"Setting Python Modules: {python_modules}")
        system_manager_instance.set_python_modules(modules=python_modules)
        print("Installing Python Modules...")
        system_manager_instance.install_python_modules()

    if font:
        print("Setting Hack Font")
        system_manager_instance.font()

    if theme:
        print("Setting Theme")
        system_manager_instance.theme()

    if optimize:
        print("Optimize")
        system_manager_instance.optimize()

    if start_up:
        print("Setting Start Up Applications")
        system_manager_instance.set_startup_programs()

    if clean:
        print("Cleaning Recycle/Trash Bin")
        system_manager_instance.clean()

    print("Done!")


def main():
    if len(sys.argv) < 2:
        usage()
        sys.exit(2)
    systems_manager(sys.argv[1:])


if __name__ == "__main__":
    if len(sys.argv) < 2:
        usage()
        sys.exit(2)
    systems_manager(sys.argv[1:])
