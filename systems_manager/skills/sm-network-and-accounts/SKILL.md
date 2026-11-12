---
name: sm-network-and-accounts
skill_type: skill
description: >-
  Diagnose the network and manage firewall rules, cron jobs and accounts through systems-manager: interfaces, open ports, ping, DNS lookup, firewall status and rules, cron list and removal, users and groups. Use for reachability, exposure and scheduled-job questions.
---

# sm-network-and-accounts

Network probes and account reads are sensitive; honor the deployment gates.

## Network

- `sm_network_list_network_interfaces`: interfaces
- `sm_network_list_open_ports`: listening ports
- `sm_network_ping_host`: ping
- `sm_network_dns_lookup`: DNS lookup

## Firewall

- `sm_firewall_get_firewall_status`: status and rules
- `sm_firewall_add_firewall_rule`: add a rule
- `sm_firewall_remove_firewall_rule`: remove a rule

## Cron

- `sm_cron_list_cron_jobs`: list jobs
- `sm_cron_remove_cron_job`: remove a job

## Accounts

- `sm_user_list_users`: list users
- `sm_user_list_groups`: list groups

## Rules

- Read the state before a change and again after it.
- A destructive tool needs the requester's explicit confirmation (`confirm=true`).
- A policy denial is final; never route around it with another tool.
