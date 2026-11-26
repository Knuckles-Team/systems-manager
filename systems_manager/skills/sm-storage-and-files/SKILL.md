---
name: sm-storage-and-files
skill_type: skill
description: >-
  Review disks, storage health and files through systems-manager: disks, usage and space report, SMART, RAID and drive faults, listing, searching, grepping and managing files under the managed root. Use for capacity and drive-failure questions and controlled file edits.
---

# sm-storage-and-files

Storage and file work stays inside the managed filesystem root.

## Steps

1. List the disks with `sm_disk_list_disks` and verify the device you care about is present in the result.
2. Measure capacity with `sm_disk_get_disk_usage` for one path and `sm_disk_get_disk_space_report` for the whole host, and verify the percentage used is returned.
3. Check drive health with `sm_storage_health_report`, drilling into `sm_storage_health_smart`, `sm_storage_health_raid` or `sm_storage_health_faults`, and verify the health status field for each drive.
4. Locate files with `sm_file_list_files`, `sm_file_search_files` or `sm_file_grep_files` and verify every returned path is under the managed root.
5. Change one file with `sm_file_manage_file` only after reading it, passing `confirm=true` for a delete, and verify by reading the file again.

## Failure recovery

| Failure | Cause | Recovery |
|---|---|---|
| `sm_storage_health_smart` returns no data | The drive does not expose SMART or the tool is not installed on the host | Use `sm_storage_health_report` for the combined view and report the gap to the requester |
| `sm_file_manage_file` is refused for a path | The path is outside the managed filesystem root | Choose a path under the root listed by `sm_file_list_files` |
| A delete is rejected | `confirm=true` was not supplied | Ask the requester to confirm, and pass `confirm=true` on the same call |
| A write is denied by policy | Managed-file writes are not enabled for this deployment | Report the denial and stop, because a policy denial is final |

## Disks

- `sm_disk_list_disks`: list disks
- `sm_disk_get_disk_usage`: usage of a path
- `sm_disk_get_disk_space_report`: space report

## Storage health

- `sm_storage_health_report`: combined report
- `sm_storage_health_smart`: SMART data
- `sm_storage_health_raid`: RAID arrays
- `sm_storage_health_faults`: drive faults

## Files

- `sm_file_list_files`: list files
- `sm_file_search_files`: search by name
- `sm_file_grep_files`: search contents
- `sm_file_manage_file`: read, create, update or delete one file

## Rules

- Read the state before a change and again after it.
- A destructive tool needs the requester's explicit confirmation (`confirm=true`).
- A policy denial is final; never route around it with another tool.
