---
name: systems-manager-cron-management
description: A skill for managing scheduled tasks using cron on Linux systems.
tags: [cron, cron-management]
---

# Cron Job Management Skill

This skill allows the agent to schedule, list, and remove cron jobs on Linux systems.

## Tools

### `list_cron_jobs`
Lists all cron jobs for the current user (or a specified user if running as root).

**Usage:**
```python
# List current user's cron jobs
list_cron_jobs()

# List specific user's cron jobs (requires root)
list_cron_jobs(user="username")
```

### `add_cron_job`
Adds a new cron job.

**Parameters:**
- `schedule`: The cron schedule expression (e.g., `* * * * *`).
- `command`: The command to execute.
- `user`: (Optional) The user to add the cron job for.

**Best Practices:**
- Always include a comment in the command to make it easier to identify and remove later.
- Use absolute paths for commands and files.

**Example:**
```python
# Run a backup every day at 3 AM
add_cron_job(schedule="0 3 * * *", command="/usr/local/bin/backup.sh # daily-backup")
```

### `remove_cron_job`
Removes cron jobs matching a specific pattern.

**Parameters:**
- `pattern`: A string to match against the cron job line. AND this pattern will be used to remove the job.
- `user`: (Optional) The user to remove the cron job for.

**Example:**
```python
# Remove the daily backup job
remove_cron_job(pattern="daily-backup")
```

## Common Schedules
- `* * * * *` - Every minute
- `0 * * * *` - Every hour
- `0 0 * * *` - Every day at midnight
- `0 0 * * 0` - Every Sunday at midnight
- `*/5 * * * *` - Every 5 minutes

## Heartbeat Example
To create a heartbeat that logs a message every minute:
```python
add_cron_job(schedule="* * * * *", command="echo 'Heartbeat' >> /tmp/heartbeat.log # agent-heartbeat")
```
