# PROD Core API exposure: assessment (offline, PROD not accessed)

**Finding status: public exposure not indicated; current state UNVERIFIED.** The last recorded reads say port 8765 isn't reachable from the internet. They are 3 to 8 days old and were never re-read for this assessment. No request was sent, and no firewall changed.

**Correction:** an earlier report here called reachability "unconfirmed" and treated an outside port test as the next step. That missed the recorded read-only evidence below. An unauthenticated outside test wasn't needed, and isn't proposed.

## Evidence

| Layer | Recorded | Source | Date | Confidence |
|---|---|---|---|---|
| Bind | `uvicorn --host 0.0.0.0 --port 8765` | recovered PROD unit | recovered 10-27 | high for that file; the running process wasn't re-read here |
| Public IP | neither `lilith-01` nor `lilith-dev-01` has an external address | F8 runbook, gcloud reads | 10-23 | medium-high |
| Egress | Cloud NAT, outbound only | same | 10-23 | medium-high |
| Firewall, 8765 | `lilith-api-iap`: tcp:8765 from `35.235.240.0/20` only, **no target tag, so both VMs** | same; repeated in a 10-28 exposure check | 10-23, 10-28 | medium-high |
| Firewall, 22 | `lilith-allow-iap-ssh`: IAP range, tag `lilith-vm` | same | 10-23 | medium-high |
| In-VPC | no allow-internal rule; other VPC sources dropped by implied deny; no network firewall policies | same | 10-23 | medium-high |
| `default` network | permissive rules, but no instances | same | 10-23 | medium-high |
| Reverse proxy, tunnel on the host | nginx, caddy, cloudflared, ngrok, tailscale: **no unit or config in recovered source**; one matching file was not examined | repo search | 10-31 | **low: absence from recovered files proves little** |
| Tunnel accessors | owner `roles/owner`; `github-lilith-deployer@` with `iap.tunnelResourceAccessor` and `osAdminLogin`, project-wide, all ports, both VMs | F8 runbook | 10-23 | medium |
| IAP resource-level IAM; default compute SA's `roles/editor` | **never read** | `INSTALL.md` follow-ups | | **unknown** |
| Firewall changes since | `firewalls.insert` called 5 times in the project's life as of 09-28; later changes not checked | PR-2 inventory | 09-28 | partial |

**An IAP tunnel is itself authenticated:** Google identity plus IAM. So the recorded route in needs a privileged account.

## What reaches it, and what they get

The route in is authenticated by Google. **Core API then adds none:** `519b309` has no owner check on any route, and the conversation relay attaches the trusted token itself, so a caller gets a **trusted-operator turn** with LILITH.

| Caller | Route | Authorized? | Impact | State |
|---|---|---|---|---|
| Owner, via tunnel and Command Center | IAP | yes | intended | |
| `github-lilith-deployer@` | IAP, all ports, PROD too | **wider than needed** | all owner data and a trusted turn. PROD's deploy workflow is dispatch-only | **most realistic risk** |
| Any process on PROD | localhost | not separated | same. **Hermes has full toolsets on Telegram and Discord,** so a chat that reaches a terminal tool reaches 8765 | follows the parity decision |
| A web page on the owner's machine while the tunnel is open | the tunnel's localhost port | no | **not tested.** No CORS middleware, so a cross-site page can't read replies, and JSON POST needs a preflight that fails. DNS rebinding isn't excluded: there's no Host check | theoretical, UNVERIFIED |
| Anyone on the internet | none recorded | no | none, if the record still holds | re-read below |

**Severity:** high impact, low likelihood, as recorded. Not an emergency on this evidence, but not cosmetic: the fix is already written, in #306.

## Why a loopback bind isn't the fix

IAP forwards to the NIC address, never to loopback. Binding `127.0.0.1` would cut Command Center off. This reverses a stage in the first version of the auth design.

| Option | Effect | Cost |
|---|---|---|
| **A. Keep the tunnel; add auth; tag the rule to each VM; limit the deployer's tunnel to port 22 and DEV** | Stops unauthenticated use by every accessor, local process included | IAM and firewall change, owner approval |
| B. SSH forwarding over IAP, then bind loopback and delete `lilith-api-iap` | Closes 8765 to the network entirely | Changes how Command Center reaches the backend |

**Recommendation: A at migration, B considered after.** Auth is needed under either, because of local processes.

## Minimal read-only PROD preflight (PREPARED, NOT RUN, needs owner approval)

`prod_exposure_preflight.sh`, beside this file. Cloud reads only, from the owner's gcloud: no SSH, no connection to 8765, no IAP tunnel, no change.

| Read | Answers |
|---|---|
| `instances describe lilith-01`, network interfaces only | Is there an external address? |
| `firewall-rules list`, `lilith-vpc` and `default` | Any rule beyond the recorded ones? |
| `networks describe`, forwarding rules, target proxies | Any load balancer or forwarding? |
| `network-firewall-policies list` | Any policy? |
| `projects get-iam-policy`, tunnel-related roles only | Who can tunnel? |
| IAP `get-iam-policy` on the instance | The binding never read |

**It can't answer:** what runs on the host. A second, separately approved step would run `ss -ltnp` and a list of units on PROD: nothing else.

**Verdict rule:** `NOT_PUBLIC_CONFIRMED` needs no external address, no forwarding rule and no rule allowing 8765 from outside the IAP range. Anything else is `EXPOSED_INVESTIGATE`, which goes to the owner the same day.
