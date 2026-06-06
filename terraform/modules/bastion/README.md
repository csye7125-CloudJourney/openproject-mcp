# modules/bastion

Hardened t3.nano in a public subnet. Exists for the cases where a
plain ssh hop is the simplest answer (debugging the NAT gateway,
poking at a stuck node, etc).

Tailscale is the primary access path; the bastion is the boring
fallback when the tailnet is unreachable. Compared side by side:

| | Tailscale | Bastion |
|--|--|--|
| Public attack surface | Tailnet-only | Open SSH 22 to `allowed_ssh_cidr` |
| Auth | OAuth/SSO + device approval | SSH key file |
| Audit | Tailscale admin console | CloudWatch + ec2 instance logs |
| Key rotation | Tailscale handles it | Manual via this module |

Keep `allowed_ssh_cidr` tight (your laptop IP, not `0.0.0.0/0`) and
lean on tailscale for the daily path.

## user_data

The instance bootstraps itself with:
- `apt-get install fail2ban`
- `PermitRootLogin no` + `PasswordAuthentication no` in `sshd_config`
- IMDSv2 required

Ansible's `playbooks/bootstrap-bastion.yml` covers the rest
(tailscale install, ssh keys, etc) once it's reachable.
