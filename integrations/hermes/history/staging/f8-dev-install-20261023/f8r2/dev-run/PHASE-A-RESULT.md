# F8r2 Phase A on lilith-dev-01: result (2026-10-23, 08:00–08:27 UTC)

**Package:** `269dde950eb024155235b3237a4658c93039975c600fa2f40d638ff02945e327` (release `f293e72-f8r2`).
**Status:** all gates G-0 … G-10 executed. One **ACCEPTED_DEVIATION** (G-7b P7), under the owner's narrow exception.
**Recommendation:** ACCEPT Phase A. The acceptance itself is the owner's act.

## Gates

| Gate | Result |
|---|---|
| G-0 | authorization recorded; hash matched; no DEV deploy since b9eb32c |
| G-2 | tarball + MANIFEST (14,293) verified on DEV |
| G-1 / G-1b | backup `pre-20261023T080301Z` (no DB opened or copied); DR-5 byte-equal `7fe21378…` |
| G-3 / G-3b | staged with the C-3 guarded reload; DR-5 byte-equal |
| G-4 | F7 suite 19/19 on DEV |
| G-5 | DEV-only token (prefix `0fb518744922`), verify full PASS, provider.env ABSENT |
| G-6 | active / running / 0 restarts / static; only `127.0.0.1:9901`; timer static via `Wants=`; no unit pending reload |
| G-7 | smoke 22/22: S10 real Core API relay 200 (provider-failure reply); S11 capture 403 `CAPTURE_INACTIVE`; 9 slash commands not executed |
| G-7b | probe 16/17. **P7 FAIL preserved → ACCEPTED_DEVIATION** (below); P1–P6, P8–P17 PASS |
| G-8 | retention `Result=success` ("No sessions match"); timer next 2026-10-24 03:36 UTC |
| G-9 | observation EQUAL to G-1 in all 6 sections; DR-5 byte-equal; Core API health ok |
| G-9b | existing IAP tunnel → DEV `/health` ok, `/system/status` served (DEV signature) |
| G-10 | unmodified UI (lilith-os-devui @ b9eb32c) on `127.0.0.1:3210`, process env `LILITH_API_URL=http://127.0.0.1:18765` only; `NEXT_PUBLIC_LILITH_API_URL` and the capture token unset; no `.env.local`. The proxy reached DEV (signature). Synthetic `F8-SYNTHETIC UI check` → POST `/api/lilith/conversation` 200 → "⚠️ Provider authentication failed…"; recording reports `OWNER_AUTHENTICATION_UNAVAILABLE` |
| Final | observation EQUAL to G-1; DR-5 EQUAL; parity unchanged |

## P7 exception (`p7/proof-ab.txt` on DEV, sha `ba3bb550…`)

- Inside the sandbox, `/etc/hosts` line 10 reads `169.254.169.254 metadata.google.internal metadata`, and nsswitch is `hosts: files dns`.
- The files-only lookup returns the entry; the DNS-only lookup FAILS for both `metadata.google.internal` and `example.com`.
- `getaddrinfo` returned `['169.254.169.254']` with the gateway cgroup IP counters unchanged across the lookup (no packets).
- **Direct denial: 13/13 BLOCKED.** That covers:
  - the metadata server by IP and by hosts name (:80), and metadata DNS (:53);
  - the stub resolvers 127.0.0.53 and 127.0.0.54, and 8.8.8.8:53;
  - 1.1.1.1:443 and 142.250.0.1:443;
  - PROD 10.20.0.2 on :8765 and :22;
  - the VPC gateway 10.20.0.1:80;
  - the VM's own NIC 10.20.0.3 on :8765 and :22.
- The gateway has 0 non-loopback established sockets. Unit policy: allow `127.0.0.1/32`, deny any, AF_INET + AF_UNIX.
- **Unchanged:** `/etc/hosts`, the package, the probe and the sandbox.

## Protected service parity (G-1 = G-9 = final)

| Service | PID | Restarts | InvocationID |
|---|---|---|---|
| lilith-os-api-dev | 176771 | 0 | `cbf42d93…` |
| lilith-memory-broker | 3411 | 0 | `ed35e343…` |
| lilith-authority-dev | 128648 | 0 | `efbc0784…` |
| lilith-recovery-witness | 127192 | 0 | `8cbfbed2…` |

## Gateway (final)

| Property | Value |
|---|---|
| PID | 185350 |
| Restarts | 0 |
| State | static (not enabled) |
| Memory | 101 MiB (peak 123 MiB) |
| Tasks | 11 |
| CPU | 13 s |
| Listener | `127.0.0.1:9901` only |
| Router V2 | shadow; every lane off |
| `.env` keys | `LILITH_OS_PORT`, `LILITH_OS_TOKEN` only |
| provider.env | ABSENT |
| Host after install | 1,322 MiB available, 12.1 GB free |

## Installation manifest

- Release `/opt/hermes-gateway-dev/releases/f293e72-f8r2`: RELEASE.sha256 `ffaed494…` (18,212 files).
- Critical-set pin `c224a9dd…`.
- Other paths as in the RUNBOOK §4 allowlist.
- Evidence on DEV: `/var/backups/hermes-gateway-dev/` (`pre-*`, `dr5-*.txt`, `post/`, `final/`, `p7/`, G-logs).

## Deviations and procedural notes

1. G-7b P7: ACCEPTED_DEVIATION, as above.
2. Two local plink exits (rc `0xC0000005`) at G-7/G-7b and the stop check. Their results were recovered from files on DEV and re-verified. Nothing relied on the crashed output.
3. The first P7-proof run had an invalid sandbox helper (sh `${@:2}`). Sections A and B of that run were discarded and rerun correctly; its section C/D results were valid.
4. G-10 used a temporary `.claude/launch.json` entry (local tooling, not UI). It was reverted exactly; both worktrees are clean.

## Observed, not a gate

Router V2 was **not reached** on any DEV turn. With no provider, Hermes fails provider auth before the run_sync seam, so no `lilith-router-decisions.log` exists. Router V2 on DEV is validated only by the offline F7 suite. Live shadow routing is unverified until Phase B.
