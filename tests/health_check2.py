from systems_manager.systems_manager import detect_and_create_manager
import json

manager = detect_and_create_manager(silent=True)
health = manager.system_health_check()
if health.get("success"):
    print(f"✅ Overall Status: {health.get('status').title()}")
    print(f"Uptime: {health.get('uptime_human')}")
    print(f"CPU Usage: {health.get('cpu_percent')}%")
    print(f"Memory Usage: {health.get('memory_percent')}% ({health.get('memory_available_gb')} GB available)")
    print(f"Swap Usage: {health.get('swap_percent')}%")
    print("\nLoad Average:")
    if health.get("load_average"):
        print(f"1 min: {health.get('load_average')[0]}")
        print(f"5 min: {health.get('load_average')[1]}")
        print(f"15 min: {health.get('load_average')[2]}")
else:
    print(f"Health check failed: {health.get('error')}")

logs = manager.get_system_logs(lines=5)
if logs.get("success"):
    print("\nRecent Logs:")
    print(logs.get("logs"))
else:
    print(f"\nFailed to get logs: {logs.get('error', 'Unknown error')}")
