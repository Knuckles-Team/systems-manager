---
name: sm-network-and-accounts
skill_type: skill
description: >-
  Diagnose the network and manage firewall rules, cron jobs and accounts through systems-manager: interfaces, open ports, ping, DNS lookup, firewall status and rules, cron list and removal, users and groups. Use for reachability, exposure and scheduled-job questions.
---

# sm-network-and-accounts

Network probes and account reads are sensitive; honor the deployment gates.

## Steps

1. Inventory the interfaces with `sm_network_list_network_interfaces` and verify the interface of interest is listed with an address.
2. Read exposure with `sm_network_list_open_ports` and `sm_firewall_get_firewall_status`, and verify the status output names the rules in force.
3. Probe reachability with `sm_network_ping_host` or `sm_network_dns_lookup` and verify the response carries a latency or resolved address.
4. Change one firewall rule with `sm_firewall_add_firewall_rule` or `sm_firewall_remove_firewall_rule`, and verify by calling `sm_firewall_get_firewall_status` again.
5. Review scheduled jobs and accounts with `sm_cron_list_cron_jobs`, `sm_user_list_users` and `sm_user_list_groups`, removing a job with `sm_cron_remove_cron_job` only on confirmation, and verify the job is gone from the list.

## Failure recovery

| Failure | Cause | Recovery |
|---|---|---|
| A probe tool is denied | The network-probe gate is closed for this deployment | Report the denial and stop, because a policy denial is final |
| `sm_firewall_remove_firewall_rule` finds no matching rule | The rule text differs from the one in the status output | Copy the rule exactly from `sm_firewall_get_firewall_status` and call the tool again with that text |
| `sm_cron_remove_cron_job` is rejected | `confirm=true` was not supplied | Obtain the requester's confirmation and pass `confirm=true` |
| `sm_user_list_users` is refused | Sensitive account reads are not enabled | Report the denial to the requester and do not use another tool to read accounts |

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
