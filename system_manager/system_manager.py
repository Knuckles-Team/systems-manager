#!/usr/bin/env python
# coding: utf-8

import sys
import getopt
import subprocess
import os
import platform


class SystemManager:
    def __init__(self, silent=False, applications=None):
        self.system = platform.system()
        self.release = platform.release()
        self.version = platform.version()
        self.operating_system = None
        self.result = None
        self.get_operating_system()
        self.silent = silent
        self.applications = applications
        self.ubuntu_install_command = []
        self.windows_install_command = []
        self.set_applications(applications)
        self.ubuntu_update_command = [['apt', 'update'], ['apt', 'upgrade', '-y'], ['apt', 'autoremove', '-y']]
        self.windows_update_command = [['winget', 'upgrade', '--all']]
        self.ubuntu_clean_command = [['trash-empty']]
        self.windows_clean_command = [['cleanmgr', '/lowdisk']]
        if self.operating_system == "Ubuntu":
            self.install_command = self.ubuntu_install_command
            self.update_command = self.ubuntu_update_command
            self.clean_command = self.ubuntu_clean_command
        elif self.operating_system == "Windows":
            self.install_command = self.windows_install_command
            self.update_command = self.windows_update_command
            self.clean_command = self.windows_clean_command

    def install_applications(self):
        if self.install_command:
            for install_single_command in self.install_command:
                self.run_command(install_single_command)
                if 'Try "snap install' in self.result.stdout:
                    install_single_command[0] = "snap"
                    install_single_command.remove('-y')
                    self.run_command(install_single_command)
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

    def run_command(self, command):
        try:
            if self.silent:
                self.result = subprocess.run(command, stdout=open(os.devnull, 'wb'), stderr=open(os.devnull, 'wb'))
            else:
                print("Running Command: ", command)
                self.result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        except subprocess.CalledProcessError as e:
            print(e.output)

    def get_operating_system(self):
        if "ubuntu" in str(self.version).lower():
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
                self.applications = ["python"]
        elif applications == "all":
            if self.operating_system == "Ubuntu":
                self.applications = \
                    [
                        "atomicparsley", "audacity", "curl", "dialog", "discord", "containerd", "docker.io", "docker-compose",
                        "dos2unix", "enscript", "ffmpeg", "fstab", "gimp", "git", "gnome-shell", "ubuntu-gnome-desktop",
                        "gnome-theme", "gnucobol", "ghostscript", "gparted", "gramps", "jq", "kexi", "kvm", "mediainfo",
                        "mkvtoolnix", "neofetch", "nfs-common", "nfs-kernel-server", "net-tools", "openjdk-8-jdk",
                        "nmap", "openssh-server", "openvpn", "preload", "poppler-utils", "python3", "pycharm", "rygel",
                        "scrcpy", "sysstat", "net-tools", "numactl", "linux-tools-common", "steam",
                        "startup-disk-creator", "update-manager", "synaptic", "telegram", "tesseract", "tigervnc",
                        "tmux", "transmission", "translate-shell", "trash-cli", "tree", "unzip", "udisks2", "vlc",
                        "wine", "wireshark", "wget", "xdotool", "xsel", "yq"
                    ]
            elif self.operating_system == "Windows":
                self.applications = ["Git.Git", "oh-my-posh"]
        else:
            self.applications = applications

        for application in self.applications:
            self.ubuntu_install_command.append(['apt', 'install', '-y', f'{application}'])
            self.windows_install_command.append(['winget', 'install', '-y', f'{application}'])


def usage():
    print(f"Usage: \n"
          f"-h | --help         [ See usage for script ]\n"
          f"-a | --applications [ Applications to install ]\n"
          f"-c | --clean        [ Clean Recycle/Trash bin ]\n"
          f"-f | --file         [ File of applications to install ]\n"
          f"-i | --install      [ Install applications ]\n"
          f"-s | --silent       [ Don't print to stdout ]\n"
          f"-u | --update       [ Update your applications and Operating System ]\n"
          f"Example: \n"
          f"system-manager --file apps.txt --update --clean --install --applications 'python3'\n")


def system_manager(argv):
    system_manager_instance = SystemManager()
    applications = []
    install = False
    silent = False
    update = False
    clean = False
    try:
        opts, args = getopt.getopt(argv, "hcisua:f:", ["help", "clean", "install", "silent", "update", "applications=", "file="])
    except getopt.GetoptError:
        usage()
        sys.exit(2)
    for opt, arg in opts:
        if opt in ("-h", "--help"):
            usage()
            sys.exit()
        elif opt in ("-a", "--applications"):
            applications = arg.lower()
            applications = applications.replace(" ", "")
            applications = applications.split(",")
        elif opt in ("-c", "--clean"):
            clean = True
        elif opt in ("-i", "--install"):
            install = True
        elif opt in ("-f", "--file"):
            file = arg
            applications = file
        elif opt in ("-s", "--silent"):
            silent = True
            system_manager_instance.set_silent(silent=silent)
        elif opt in ("-u", "--update"):
            update = True

    if update:
        print("Performing Update...")
        system_manager_instance.update()

    if install:
        print(f"Setting applications: {applications}")
        system_manager_instance.set_applications(applications=applications)
        print("Installing...")
        system_manager_instance.install_applications()

    if clean:
        print("Cleaning Recycle/Trash Bin")
        system_manager_instance.clean()

    print("Done!")


def main():
    if len(sys.argv) < 2:
        usage()
        sys.exit(2)
    system_manager(sys.argv[1:])


if __name__ == "__main__":
    if len(sys.argv) < 2:
        usage()
        sys.exit(2)
    system_manager(sys.argv[1:])
