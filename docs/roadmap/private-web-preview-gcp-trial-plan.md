# LILITH private web preview: two-VM GCP trial plan

Status: **PREPARED, NOT EXECUTED** (2026-11-12). Nothing here is provisioned, activated, purchased or configured. Live exposure is blocked on security gate W-SEC-1 (§5a).

Each step below needs separate owner authorization. The backend migration is owned by the separate cognition and infrastructure workstream, and this plan follows it.

## 0. Gate: trial eligibility (owner, before anything else)

Google's Free Trial terms ([Free Cloud features](https://docs.cloud.google.com/free/docs/free-cloud-features), checked 2026-11-12) provide **$300 of credit for 90 days**. Eligibility requires:
- *"You've never been a paying user of Google Cloud, Google Maps Platform, or Firebase"*;
- *"You haven't previously signed up for the Free Trial."*

These conditions describe **the customer**, not a Google account. A second trial by the same person may therefore **not** be eligible. Google also states that access "may be limited to prevent abuse". A trial that is refused or later suspended would stop the backend mid-migration.

Before activating, the owner must:
1. Read the current Free Trial terms and confirm the second account is genuinely eligible: a different customer, a never-paid account and an unused trial. Do not proceed on an assumption.
2. After sign-up, record the **actual** credit amount and the **expiry date** from *Billing → Credits*. Every date in this plan derives from that.
3. Note the end-of-trial behaviour: if the account is not upgraded, resources are **stopped** when the credit or the 90 days run out, then deleted after a 30-day grace period. Migration off the trial must finish before the expiry (§6).
4. If eligibility is doubtful, choose instead a paid billing account with a hard budget, or the target VPS (§7). The VM and network design below does not change.

## 1. Architecture (new project, one VPC, one region, one zone)

```
                     owner browser
                          │ HTTPS
              Cloudflare Access (owner email only)
                          │ Cloudflare Tunnel (outbound from VM 2)
 ┌────────────── VPC lilith, asia-southeast1-b, NO external IPs ───────────────┐
 │ VM 2  lilith-web  (e2-micro)            VM 1  lilith-core  (e2-small, as today)│
 │  cloudflared → 127.0.0.1:3000           Hermes, Router, Core API :8765,        │
 │  lilith-web.service (Next standalone)   canonical memory/goals, scheduling     │
 │  H1 auth + server-side tokens ──────────▶ :8765 (internal IP only; tokens      │
 │                                           enforced; loopback trust = router)  │
 │            Cloud NAT (outbound only) ◀── both VMs; IAP TCP for admin SSH      │
 └───────────────────────────────────────────────────────────────────────────────┘
```

- **Hosts:** VM 1 holds the backend; VM 2 holds the web frontend.
- **Never co-host the frontend with the Core API:** with `LILITH_OS_TRUST_LOOPBACK=1`, a loopback caller on VM 1 bypasses the read and write tokens.
- **Same zone:** internal VM-to-VM traffic in one zone is free and has the lowest latency.
- **No public IPs:** outbound access goes through Cloud NAT, and admin access through IAP TCP forwarding. That leaves no public IP to scan or attack.

**Firewall** (VPC rules; no `0.0.0.0/0` ingress anywhere):

| Rule | Source | Target | Port |
|---|---|---|---|
| `allow-iap-ssh` | `35.235.240.0/20` (IAP) | both VMs | tcp:22 |
| `allow-web-to-core` | service account `lilith-web@…` (or tag `lilith-web`) | VM 1 (tag `lilith-core`) | tcp:8765 |
| implicit | — | all | deny all other ingress |

**Changes the backend migration must provide** (infrastructure chat; separately authorized):
- **Reachable Core API:** VM 1's Core API reachable on its **internal** IP. It is reached today over IAP, so it already listens on the NIC; re-verify in the new project.
- **Tokens enforced:** `LILITH_OS_READ_AUTH=enforced` and `LILITH_OS_WRITE_AUTH=enforced`, with **dedicated** read and write tokens for the web VM, minted by the owner and never reused elsewhere.
- **Loopback trust unchanged:** `LILITH_OS_TRUST_LOOPBACK` stays as it is, for the on-host router only.

## 2. Sizing (measured)

| | Measured | Decision |
|---|---|---|
| **Next server** | about 63 MB idle; **117 MB** peak working set / 103 MB private under 20 concurrent page loads plus 3 parallel avatar downloads. Startup 1–4 s. | **e2-micro** (1 GB, 2 shared vCPUs). With cloudflared (about 30–50 MB) and the OS, the total is about 0.4–0.5 GB. The single-owner CPU load is RS256 verification (well under 1 ms), small SSR pages and file streaming, all within the e2-micro burst budget. Move to **e2-small** only if CPU throttling is observed. |
| **Artifact** | 181 MB, of which 27 MB is runtime dependencies | 10 GB balanced disk |
| **Avatar** | 35.9 MB on the wire (gzip). Revalidation is 304 with 0 bytes. Cached privately only. | Each uncached load costs about 36 MB of egress. S1 (avatar ≤20 MB) cuts this further. |
| **VM 1** | unchanged from today (e2-small, 2 GB) | as decided by the migration |

## 3. Estimated monthly credit consumption (asia-southeast1)

Prices are **approximate** third-party and list figures. Verify them in the Google Cloud pricing calculator before relying on them.

| Item | Estimate / month |
|---|---|
| VM 1 e2-small (730 h) | about $15 |
| VM 2 e2-micro (730 h) | about $7.5 |
| Disks: 20 GB + 10 GB balanced PD | about $3.5 |
| Cloud NAT: 2 VMs (gateway hours) plus data processing (about $0.045/GB on a few GB) | about $2–4 |
| Internet egress (about $0.12/GB): web pages plus avatar (2–12 GB), backend APIs and Telegram (1–3 GB) | about $0.5–2 |
| Snapshots for verified backups (VM 1 and VM 2, incremental) | about $1–2 |
| Cloudflare Tunnel and Access (Free, up to 50 users) | $0 |
| **Total** | **about $30–34 / month**, of which the web preview is about $10–12 |

Over 90 days that is about **$90–100 of the $300 credit**. Nothing is out of pocket while the trial credit lasts and the account stays a Free Trial.

**Cheapest safe networking:** Cloud NAT with no external IPs, at about $2–4 a month for both VMs. The alternative is ephemeral public IPs on both VMs with a deny-all firewall, at about $7.3 a month, which also creates a public attack surface. **Not used:** load balancers, static IPs, Cloud Armor, Secret Manager, managed instance groups.

## 4. Budget alerts and stop plan
- **Budget alert:** create a Billing budget on the trial billing account at **$40/month**, alerting at 50%, 90% and 100% to the owner email. Budgets alert only; they do not stop spending. During the trial, overspend is impossible because the account stops at the end of the credit.
- **Credits check:** check *Billing → Credits* weekly. Record the remaining credit and days in the infrastructure log.
- **Expiry timeline:**

  | When | Action |
  |---|---|
  | T-21 days | Choose the next host (the VPS in §7, or a paid account). |
  | T-14 days | Verified backups: VM 1 canonical memory, goals and state DBs, plus the web env file. Export them off GCP. |
  | T-7 days | Migrate and accept on the new host. |
  | T-1 day | Stop both VMs. |

  After expiry, Google stops the resources. Do not upgrade the trial billing account unless that is decided deliberately.
- **Emergency stop of the web preview only:**
  1. Disable the Access application, or set its policy to deny all.
  2. Run `systemctl disable --now lilith-web lilith-web-health.timer cloudflared` on VM 2.
  3. Optionally remove the DNS CNAME.

  The backend is unaffected.

## 5. Deployment sequence (after the backend migration is accepted)
Every step needs separate authorization. Steps marked *(owner)* need the owner's own accounts or credentials.

0. **Preconditions:**
   - trial eligibility confirmed (§0);
   - the backend migration accepted in the new project (infrastructure chat);
   - #430 merged (done 2026-11-12, `f5be340`), and its `main` runs green;
   - **security gate W-SEC-1 satisfied (§5a).** Until then the web service is not exposed: `cloudflared` is not started and no DNS route is created.
1. **Create VM 2 `lilith-web`:** e2-micro, Ubuntu 24.04 LTS or Debian 12, in the same zone and VPC as VM 1, **no external IP**, Shielded VM, OS Login, and its own service account with **no project roles** (logging only if wanted).
2. **Networking:** Cloud Router plus Cloud NAT for the subnet; the firewall rules in §1. Verify from VM 2 that `curl http://<vm1-internal>:8765/health` returns 200 and that nothing else on VM 1 is reachable.
3. **VM 2 packages:** Node.js 22 at `/usr/bin/node`, and `cloudflared` from Cloudflare's apt repository.
4. **Secrets** *(owner)*:
   - mint dedicated read and write tokens of 32+ characters;
   - set them in VM 1's Core API env, with `READ_AUTH` and `WRITE_AUTH` enforced (infrastructure chat);
   - write `/etc/lilith-web/env` from the template on VM 2, including the optional voice keys. No owner-capture token.
5. **Cloudflare** *(owner)*:
   - **zone:** the domain's zone is active on Cloudflare (nameservers);
   - **Zero Trust team:** create it at `<team>.cloudflareaccess.com`;
   - **Access application:** a self-hosted app for `os.<domain>`, with one Allow policy for the owner email(s), a session of 24 h or less, and no Bypass or Service Auth rules;
   - **settings:** copy the **AUD tag** and the team domain into the env file;
   - **DNS plan:** `cloudflared tunnel create lilith-web`, then `cloudflared tunnel route dns lilith-web os.<domain>`, which creates a proxied CNAME `os` → `<tunnel-id>.cfargotunnel.com`. That is the only DNS change; no A records and no other hostnames.
6. **Install the release** on VM 2: copy the artifact tarball over IAP (`gcloud compute scp --tunnel-through-iap`), then run `sudo ./bin/install-release.sh ./lilith-web`. That script runs readiness, switches atomically, checks health and rolls back on failure.
7. **Tunnel config:** write `/etc/cloudflared/config.yml` from the template, re-run the readiness check including `--cloudflared`, and start `cloudflared` **only after** the Access application exists, so the hostname is never reachable without Access.
8. **Acceptance tests** (owner plus agent, recorded):

   | Test | Expected |
   |---|---|
   | Signed-out browser | Cloudflare login. Non-owner email: denied. |
   | `curl https://os.<domain>/` and `/api/lilith/system/status` with no cookie | redirect to the Access login, never app content |
   | Owner signed in | The capsule shows Online with a measured latency; TODAY/NEXT show the live agenda in the owner timezone; a conversation turn works; Stop, Retry and Ask again work; voice on/off works. **Hsin renders and speaks**, and her presence goes thinking → speaking → idle. |
   | Avatar | `/avatar/hsin-<version>.vrm` is `Content-Encoding: gzip` and `Cache-Control: private, immutable`, served on a fresh device only after login. Nothing is cached at the edge: `cf-cache-status` is not `HIT`. |
   | On VM 2 | `healthcheck.sh` returns 0; `ss` shows only `127.0.0.1:3000`; the readiness check passes; there is no external IP. |
   | VM 1 | `:8765` is not reachable from outside the VPC; the Core API logs show token-authenticated (not loopback) requests from VM 2. |
9. **Rollback and recovery:**
   - **Web release:** `sudo /opt/lilith-web/current/bin/rollback.sh`.
   - **Web preview off:** the emergency stop in §4.
   - **VM 2 lost:** recreate it from steps 1–7. It holds no LILITH state; only the env file and the tunnel credentials, both re-creatable by the owner.
   - **Backend:** only the infrastructure chat's procedures apply. Nothing here changes VM 1 beyond step 4's token settings.

## 5a. Security gate W-SEC-1: no unauthenticated serving window (owner requirement, 2026-11-12)
**Requirement:** before any live web deployment, a verified startup preflight (or equivalent protection) must prevent the web server from serving even one unauthenticated request when `LILITH_HOSTED` is disabled or misconfigured. The web service is not exposed until W-SEC-1 is accepted.

**Gap in the #430 package:**
- A *misconfigured* hosted setting already fails closed: the Proxy returns 503 to every request.
- `LILITH_HOSTED` unset or `0` is **local mode**, which deliberately passes every request through.
- The unit's only check is `ExecStartPost=healthcheck.sh`, which runs *after* `ExecStart`. In local mode the server serves unauthenticated on `127.0.0.1:3000` until the check fails and systemd stops it.
- `Restart=on-failure` repeats that window up to `StartLimitBurst=5` times. A running `cloudflared` would forward Internet traffic during each window.

**Required protection** (all three; implemented as one small PR, reviewed and authorized separately):

1. **Pre-start gate, before the server ever binds.** Add `ExecStartPre=` that runs the bundled `bin/check-readiness.mjs --env-only` against the same `EnvironmentFile`. It exits non-zero unless the resolved config is `mode: hosted` with every setting valid. A failing `ExecStartPre` means `ExecStart` never runs, so there is no window.
2. **The app refuses local mode in a hosted release.** The unit sets `Environment=LILITH_REQUIRE_HOSTED=1`; it is in the unit, not the editable env file. With it set, `loadEdgeAuthConfig` treats local mode as *misconfigured*, so the Proxy and every API guard return 503. This covers a server started by hand or by a future unit edit that drops `ExecStartPre`.
3. **The tunnel depends on a verified web unit.** A `cloudflared` drop-in adds `Requires=lilith-web.service`, `After=lilith-web.service` and `BindsTo=lilith-web.service`. Because `ExecStartPost` must pass before `lilith-web` counts as started, the tunnel starts only after the auth check succeeds and stops whenever the web unit stops or fails.

**Acceptance evidence** (CI e2e on the ephemeral runner plus a recorded check on VM 2 before `cloudflared` is first started):

| Case | Expected |
|---|---|
| env file with `LILITH_HOSTED` removed | `ExecStartPre` fails; the server never binds `:3000` (`ss` shows nothing); unit `failed`; `cloudflared` not started |
| `LILITH_HOSTED=0` | same as above |
| `LILITH_HOSTED=1` with a missing AUD or team | same as above |
| unit edited to drop `ExecStartPre`, `LILITH_HOSTED` unset | the server binds, but every path, including `/`, `/api/*` and `/avatar/*`, returns 503; zero 200s |
| `node server.js` started by hand with `LILITH_REQUIRE_HOSTED=1` and no hosted config | 503 on every path |
| valid hosted config | starts; unauthenticated requests are refused (401/403); `cloudflared` starts after `lilith-web` is active |
| `systemctl stop lilith-web` | `cloudflared` stops with it |

## 5b. Next operational steps (prepared, none executed)
Each line is its own authorization. Order matters: no exposure happens before step N-6.

| # | Step | Who | Gate |
|---|---|---|---|
| N-1 | W-SEC-1 PR (§5a): `ExecStartPre` gate, `LILITH_REQUIRE_HOSTED`, `cloudflared` drop-in, e2e cases, then merge | agent, then owner merge | owner review; DEV deploy expected (server-side web code) |
| N-2 | Confirm second-trial eligibility (§0) and activate it | owner | owner only |
| N-3 | Backend migration to VM 1 in the new project, then acceptance | infrastructure chat | separately gated |
| N-4 | Create VM 2, networking, packages (§5 steps 1–3) | agent | after N-1, N-2, N-3 accepted |
| N-5 | Tokens, env file, Cloudflare zone, Access app, tunnel (§5 steps 4–5); no `cloudflared` start | owner (+ agent for VM 2 files) | Access app must exist first |
| N-6 | Install the release, verify the W-SEC-1 acceptance table on VM 2, **then** start `cloudflared` (§5 steps 6–7) | agent | first exposure; separate authorization |
| N-7 | Acceptance tests (§5 step 8), recorded | owner + agent | — |

## 6. Coordination with the backend migration (infrastructure chat)
- The two-VM design needs no change to the migration itself, only that VM 1 is in a VPC and zone that VM 2 can join, plus §1's token and reachability items.
- Before the migration, merge #430 in a window when nothing is running on DEV, because it triggers one same-code DEV Core API restart.
- The web preview deploys **after** the backend is accepted in the new project, never during the migration.

## 7. Long-term hosting (after the trial; not implemented)
- **Target:** one always-on VPS of about $10/month (2 vCPU, 2–4 GB) running the private web preview and lightweight services. The same `install-release.sh`, systemd units, `cloudflared` and Cloudflare Access apply unchanged, because none of this package depends on GCP.
- **Later:** a Mac mini for heavier cognition, local models and embeddings, connected to the VPS over a private overlay (WireGuard or Tailscale). Neither machine exposes a public port; Cloudflare Tunnel stays the only public entry.
- **Portability rules:**
  - no GCP-only managed services in the data path (no Cloud SQL, no Secret Manager dependency, no IAP for app traffic);
  - secrets in env files or systemd credentials, re-encrypted per host;
  - canonical memory, owner identity and authority moved only through their existing verified backup and restore procedures, never by copying live state ad hoc;
  - each migration ends with a verified restore test.
