import argparse
import json
import os
import subprocess
import sys

# Strictly define what services & packages can be touched by root
ALLOWED_SERVICES = {
    "nginx",
    "caddy",
    "docker",
    "ssh",
    "fail2ban",
    "snapd.socket",
    "snapd",
}
ALLOWED_PACKAGES = {
    "curl",
    "git",
    "htop",
    "rsync",
    "ufw",
    "trash-cli",
    "snapd",
    "nginx",
    "caddy",
    "docker.io",
    "fail2ban",
}


def run_cmd(cmd):
    try:
        # Enforce shell=False, strict PATH, and disable interactive pagers
        res = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            shell=False,
            env={"SYSTEMD_PAGER": "cat", "PATH": "/usr/bin:/usr/sbin:/bin:/sbin"},
        )
        return {
            "success": res.returncode == 0,
            "returncode": res.returncode,
            "stdout": res.stdout.strip(),
            "stderr": res.stderr.strip(),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def handle_service(action, name):
    if name not in ALLOWED_SERVICES:
        print(
            json.dumps(
                {
                    "success": False,
                    "error": f"Service '{name}' is not in the secure helper whitelist.",
                }
            )
        )
        sys.exit(1)

    cmd = ["/usr/bin/systemctl", action, name]
    print(json.dumps(run_cmd(cmd)))


def handle_package(action, name=None):
    if action in ["install", "remove"]:
        if not name:
            print(
                json.dumps(
                    {
                        "success": False,
                        "error": f"Package name is required for action '{action}'.",
                    }
                )
            )
            sys.exit(1)
        if name not in ALLOWED_PACKAGES:
            print(
                json.dumps(
                    {
                        "success": False,
                        "error": f"Package '{name}' is not in the secure helper whitelist.",
                    }
                )
            )
            sys.exit(1)

        if action == "install":
            cmd = ["/usr/bin/apt-get", "install", "-y", name]
        else:
            cmd = ["/usr/bin/apt-get", "remove", "-y", name]
    elif action == "update":
        cmd = ["/usr/bin/apt-get", "update"]
    elif action == "upgrade":
        cmd = ["/usr/bin/apt-get", "upgrade", "-y"]
    elif action == "autoremove":
        cmd = ["/usr/bin/apt-get", "autoremove", "-y"]
    elif action == "autoclean":
        cmd = ["/usr/bin/apt-get", "autoclean"]
    else:
        print(
            json.dumps(
                {"success": False, "error": f"Unsupported package action '{action}'."}
            )
        )
        sys.exit(1)

    print(json.dumps(run_cmd(cmd)))


def main():
    # Double check we are running as root
    if os.getuid() != 0:
        print(
            json.dumps(
                {
                    "success": False,
                    "error": "This helper script must be executed with sudo / root privileges.",
                }
            )
        )
        sys.exit(1)

    parser = argparse.ArgumentParser(
        description="Secure Systems Manager PyPI Root Helper"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Service commands
    svc = subparsers.add_parser("service")
    svc.add_argument(
        "action", choices=["start", "stop", "restart", "status", "enable", "disable"]
    )
    svc.add_argument("name", type=str)

    # Package commands
    pkg = subparsers.add_parser("package")
    pkg.add_argument(
        "action",
        choices=["install", "remove", "update", "upgrade", "autoremove", "autoclean"],
    )
    pkg.add_argument("name", type=str, nargs="?", default=None)

    args = parser.parse_args()
    if args.command == "service":
        handle_service(args.action, args.name)
    elif args.command == "package":
        handle_package(args.action, args.name)


if __name__ == "__main__":
    main()
