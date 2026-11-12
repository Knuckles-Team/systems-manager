---
name: sm-storage-and-files
skill_type: skill
description: >-
  Review disks, storage health and files through systems-manager: disks, usage and space report, SMART, RAID and drive faults, listing, searching, grepping and managing files under the managed root. Use for capacity and drive-failure questions and controlled file edits.
---

# sm-storage-and-files

Storage and file work stays inside the managed filesystem root.

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
