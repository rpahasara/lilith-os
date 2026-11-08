# G2 result, 2026-10-31

**Created once, under manifest `b4a1840b...`.** Written after the run, outside the manifest.

**The sealed verifier reported `VERIFY FAIL`, and that stays on record.** Its one failure was the probe's `access_config` check, which treated any listing as an address. Read directly on the VM, the metadata server lists one placeholder, `access-configs/0`, type `ONE_TO_ONE_NAT`, with an **empty** `external-ip`. The cloud API shows no access config. So the failure was the check, not the VM. Every other check passed.

**The sealed package and `verify\VERIFY-RESULT.json` are unchanged.** The copy of the probe in PR #311 carries a corrected check for any later run. It doesn't alter this result.

| Resource | Name | Id |
|---|---|---|
| Network | `lilith-rehearsal` | `<id>` |
| Subnet | `lilith-rehearsal-sn`, `<private-ip>`, Private Google Access off | `<id>` |
| Egress rule | `rehearsal-deny-all-egress`, priority 100 | `<id>` |
| Ingress rule | `rehearsal-allow-iap-ssh`, tcp:22 from `35.235.240.0/20`, tag only | `<id>` |
| VM | `lilith-rehearsal-01`, e2-medium, `<private-ip>` | `<id>` |
| Boot disk | `lilith-rehearsal-01`, 60 GB pd-balanced | `<id>` |
| Synthetic disk | `lilith-rehearsal-synthetic`, 10 GB pd-balanced | `<id>` |

**Image:** `ubuntu-2404-noble-amd64-v20261024`.

## Isolation, independently verified

| Check | Result |
|---|---|
| External IP | **none:** API shows no access config, IPv4 only; metadata `external-ip` empty |
| Service account | **none attached;** metadata token 404, none listed |
| Peering, router, NAT | none on this network |
| Direct egress | blocked: public HTTPS and DNS, a resolved public address, PROD and DEV by address, Google APIs |
| Disks | no disk or image built from the snapshot |
| Read-only mount | refuses writes |

## Metadata-server exception

**The metadata server is not blocked by VPC firewall rules, and none of these resources blocks it.** `169.254.169.254` stayed reachable with deny-all egress in place:

- **HTTP:** works. It holds instance metadata. With no service account, it issues no token.
- **DNS:** works. `example.com` resolved. **DNS queries are an outbound path this network doesn't close.** Direct connection to the resolved address was blocked.

**Isolation is therefore not complete at the network layer.** G3-A adds a guest firewall rule for DNS, which must pass before real data arrives.
