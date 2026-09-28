# Slice 15B2b-B1b-3e — PR-1A Acceptance: DEV_SYNTHETIC Inert Installation

Status:

- **ACCEPTED** (owner acceptance, 2026-09-28)
- **SCOPE: DEV_SYNTHETIC INERT INSTALLATION ONLY**
- **LIVE_MUTATION = NONE** (this record is documentation only)
- **PR-1B NOT AUTHORIZED**; **B1b-3e LIVE REHEARSAL NOT AUTHORIZED**; **FIRST MEMORY NOT AUTHORIZED**

```text
PR-1A          = ACCEPTED
FINAL_MATURITY = P1A-9
AUTHORITY_BOUNDARY = PASS L1c.3
LIVE_MUTATION  = NONE
```

This record closes the PR-1A inert-installation phase of the
[PR-1 live install preflight](slice-15b2b-b1b3e-pr1-live-install-preflight.md)
(§5, §27). It follows the [PR-1S source](slice-15b2b-b1b3e-pr1s-runtime-wiring.md)
and every PR-1A evidence record listed in §2.

```text
PR-1A acceptance      != custody readiness
installed release     != activation
directory existence   != custody state
account existence     != witness authority
unit files installed  != service running
build attestation     != authority
```

## 1. Pinned identities

| Identity | Value |
| --- | --- |
| `PAYLOAD_SOURCE_SHA` | `aee323e94412accbe321bc84eae78c5b8cf95afc` |
| `CONTROL_SHA` | `c1eb56842d464f6690b7d55a1f6915d54618e006` |
| `ARTIFACT_SHA256` | `25f1ff03f9915c19ef5835e15ff4be6d90e27d45f23e909b2a1f8bdc81a0250a` |
| `ATTESTATION_SHA256` | `86ed2659a1e8040c43bc560aeb526a5a13842314ce92f917c8868d277f65c683` |
| installed authority release | `aee323e94412accbe321bc84eae78c5b8cf95afc` |
| retired predecessor | `9ac7de22bf977385ceb954624677e33f0bae062b` (removed at M-A6) |

`origin/main` at acceptance is `8a14ea5`. Between `CONTROL_SHA` and
`8a14ea5` only `docs/` changed, so every live stage ran the reviewed
`CONTROL_SHA` installer (`fe10d9a3…5487`).

## 2. Basis of acceptance

| Basis | Result | Record |
| --- | --- | --- |
| reproducible build / attestation | `PR1A_BUILD_ATTESTATION_PASS` | [build attestation](slice-15b2b-b1b3e-pr1a-build-attestation.md) |
| read-only live preflight | `PR1A_PREFLIGHT_PASS` | [read-only preflight](slice-15b2b-b1b3e-pr1a-readonly-preflight.md) |
| final read-only gate (stored artifact check + fresh baseline) | `PR1A_FINAL_GATE_PASS` | [final gate](slice-15b2b-b1b3e-pr1a-final-readonly-gate.md) |
| M-A1 `upgrade-stage` | `M_A1_PASS` | [M-A1](slice-15b2b-b1b3e-pr1a-ma1-stage-release.md) |
| M-A2 `upgrade-select` | `M_A2_PASS` | [M-A2](slice-15b2b-b1b3e-pr1a-ma2-select-release.md) |
| M-A3 `upgrade-units` | `M_A3_PASS` | [M-A3](slice-15b2b-b1b3e-pr1a-ma3-install-units.md) |
| M-A4 daemon-reload | **skipped, not required** (`UNITS_RELOADED`, `NeedDaemonReload=no`, no reload pending) | [M-A5](slice-15b2b-b1b3e-pr1a-ma5-install-clis.md) §2 |
| M-A5 `upgrade-cli` | `M_A5_PASS` | [M-A5](slice-15b2b-b1b3e-pr1a-ma5-install-clis.md) |
| M-A6 `upgrade-retire-old` | `M_A6_PASS` (`status --expect L2b.2 aee323e…` PASS) | [M-A6](slice-15b2b-b1b3e-pr1a-ma6-retire-predecessor.md) |
| transport cleanup | `PR1A_TRANSPORT_CLEANUP_PASS` | [transport cleanup](slice-15b2b-b1b3e-pr1a-transport-cleanup.md) |
| M-A7 `custody` (L2c / P1A-7) | `M_A7_PASS` | [M-A7](slice-15b2b-b1b3e-pr1a-ma7-custody-root.md) |
| M-A8 `witness-account` (P1A-8a) | `M_A8_PASS` | [M-A8](slice-15b2b-b1b3e-pr1a-ma8-witness-account.md) |
| M-A9 `witness-units` (P1A-8b) | `M_A9_PASS` | [M-A9](slice-15b2b-b1b3e-pr1a-ma9-witness-units.md) |
| P1A-8c daemon-reload | **satisfied without explicit daemon-reload** (witness units `loaded`, `NeedDaemonReload=no`) | [M-A10](slice-15b2b-b1b3e-pr1a-ma10-skeleton.md) §1 |
| M-A10 `skeleton` (P1A-9) | `M_A10_PASS` (`status --expect P1A-9` PASS) | [M-A10](slice-15b2b-b1b3e-pr1a-ma10-skeleton.md) |

Invariants held across every stage. Each was checked by the reviewed
observer, the installer `status`/`upgrade-status`, the broker
`preservation` verifier, and the activation verifier, before and after
each mutation:

- **CURRENT unchanged.** Path
  `/etc/credstore.encrypted/lilith-authority-dev.owner-actor.cred`,
  `root:root 0600`, device 2049, inode 1738, size 219, `mtimeNs` =
  `ctimeNs` = `1790493331258019177`, SHA-256
  `6a61c350e848a833868f4573982fca9c75e2af79ccc9bd3716ae0303c26973f3`.
  Never decrypted. The credstore held exactly CURRENT throughout.
- **Host key.** Stat-identical throughout, and never opened.
- **Authority service.** `lilith-authority-dev.service` and `.socket` stayed
  inactive and never started (`InvocationID` empty, `NRestarts=0`).
- **Recovery-witness units.** Inactive and never enabled from their
  installation at M-A9.
- **No daemon-reload.** None was executed during PR-1A. PID 1's last
  reload is the accepted 2026-09-27 L1c.2 reload
  (`UnitsLoadTimestamp=2026-09-27 06:25:33 UTC`).
- **Activation.** `ACTIVATION=NOT_ACCEPTED reason=GRANT_ABSENT` throughout.
- **Broker.** `BROKER_PRESERVATION=PASS` throughout: incarnation
  `42af2691b8d24ee5a92a286197c5444c`, PID 132976, start ticks 108213277,
  `NRestarts=0`, baseline candidate `35495854…`, boot
  `24d1771d-e1b5-4e5f-816d-da08ad8b367a`, no reboot.
- **Routine deployments.** No routine deployment ran between
  `upgrade-stage` and `upgrade-retire-old` (preflight §9 freeze).

## 3. Routine-deployer boundary progression (DR-5)

Every result below is from the real routine deployment on `main`, run as
the deployer `sa_112096412008414111981`. They were observed read-only from
GitHub. The base ladder stayed `AUTHORITY_BOUNDARY_PROOF=PASS
maturity=L1c.3` throughout.

| Run | Main | After | `PR1_AUTHORITY_BOUNDARY` |
| --- | --- | --- | --- |
| `36432097677` | `d7f9f06` | before M-A1 | `PR1_ABSENT` |
| `36443835331` | `0621f26` | M-A6 (CLIs installed) | `P1A-5` |
| `36447743322` | `38c5adf` | M-A7 | `P1A-7` |
| `36450019253` | `a9737d9` | M-A8 | `P1A-8a` |
| `36453920293` | `96fed73` | M-A9 | `P1A-8b` |
| `36457144642` | `8a14ea5` | M-A10 | **`P1A-9`** |

**Final (run `36457144642`, `17:18:08Z`–`17:23:48Z`):**

```text
PR1_AUTHORITY_BOUNDARY maturity=P1A-9
AUTHORITY_BOUNDARY_PROOF=PASS maturity=L1c.3
```

The denials in that run are non-vacuous:

- `test -w` on `/etc/lilith-authority-dev` and on `trust/`, `registry/`,
  and `owner/`;
- `test -r`, `-w`, `-x` on `/etc/lilith-recovery-witness`,
  `/var/lib/lilith-authority-custody`, and (since P1A-7)
  `/etc/lilith-authority-custody`;
- `sudo -u lilith-recovery-witness`, every witness unit verb, and every new
  CLI (since P1A-5 / P1A-8a / P1A-8b).

Paths beneath root-only roots are reported `UNOBSERVABLE_BY_DESIGN`, never
"denied":

- `…/prepared`, `…/retired`;
- `…/credentials/lilith-recovery-witness.witness.cred`;
- `…/holds`.

## 4. Accepted live properties

These are as observed by the reviewed tooling at the M-A10 POST
(2026-09-28 `17:10:20Z`). The deployer boundary is the P1A-9 run in §3. This
acceptance made no further DEV contact.

| Property | Accepted value |
| --- | --- |
| installed authority releases | exactly one: `/opt/lilith-authority-dev/releases/aee323e94412accbe321bc84eae78c5b8cf95afc` |
| selector | `current -> releases/aee323e94412accbe321bc84eae78c5b8cf95afc` |
| release tree | manifest `1d578ca707a95134dab218c826408b4380e7af0b5839160f47ede37232b94e8f` = attested; tree `675c9482…` = attested archive; 0 mismatched or extra; venv (drift reference) `530c1453…` |
| authority unit assets | service `11b6d00f…`, socket `bff5e927…`, tmpfiles `2a1891ef…`, all equal to the attestation |
| six fixed CLIs | keygen `1fa50327…`, ledger `fda779cd…`, hold `ad3fbc94…`, verify `bc331636…`, recovery `ad928f8d…`, witness-owner `9fce2e46…`, all equal to the attestation and `root:root 0755` |
| custody root | `/etc/lilith-authority-custody` `root:root 0700`, holding exactly `prepared`, `retired` |
| `prepared/`, `retired/` | exist, `root:root 0700`, **empty**, same `st_dev` as the credstore |
| recovery-witness principal | user and group `lilith-recovery-witness` uid 994 / gid 984: system account, locked password, `/usr/sbin/nologin`, home `/nonexistent` (absent), no supplementary groups, no sudo, in no sensitive group |
| witness unit assets | service `9f78130c…`, owner socket `d260917f…`, signer socket `ad345d18…`, tmpfiles `c3491d51…`, all equal to the attestation and `root:root 0644` |
| witness units | `loaded`, `inactive`, `static`, not enabled, never started |
| `/etc/lilith-authority-dev` skeleton | `0755`, holding exactly `owner`, `registry`, `trust`, each **empty** |
| `/etc/lilith-recovery-witness/credentials` | exists (`0700`, under a `0700` parent), **empty** |
| `/var/lib/lilith-authority-custody/holds` | exists (`0700`, under a `0700` parent), **empty** |
| CURRENT | unchanged (§2) |
| K-WIT | absent |
| authority ledger | absent (no `/var/lib/lilith-authority-dev`) |
| witness state | absent (no `/var/lib/lilith-recovery-witness`) |
| registry content | absent (`registry/`, `trust/` empty) |
| owner register content | absent (`owner/` empty) |
| RecoveryEpoch | absent |
| hold records | absent (`holds/` empty) |
| activation | `ACTIVATION=NOT_ACCEPTED reason=GRANT_ABSENT` |
| installer status | `status --expect P1A-9 aee323e…` = PASS |

## 5. Explicit nonclaims

PR-1A acceptance does **not** establish any of the following:

- real authority readiness, or any `FULL_READINESS`;
- K-WIT custody: no K-WIT exists;
- K-ROOT authorization;
- registry publication, or registry-head authority;
- an owner register, including the owner genesis pin;
- an authority ledger;
- witness genesis, or any witness chain or state;
- INITIAL_CUSTODY `HELD` or `RELEASED`;
- owner acceptance of custody;
- proof-of-possession (RR-14a), and L2 U5 (HEALTH fingerprint): the signer
  has never loaded K-ACT;
- whole-host or snapshot rollback resistance. PR-2 is not completed, and
  the snapshot inventory is unresolved;
- the owner off-host register (PR-3), which is not completed;
- PROD authority of any kind;
- PR-1B;
- the B1b-3e live rehearsal;
- First Memory.

Known open items carried forward unchanged: DR-3 (the `ubuntu` account is
root-equivalent via `sudo`/`lxd`) and the pending kernel reboot
(`/var/run/reboot-required`). A reboot or broker restart invalidates the
current baseline, and a fresh read-only preflight is required before any
later live step.

## 6. Decision

```text
PR-1A = ACCEPTED
SCOPE = DEV_SYNTHETIC INERT INSTALLATION ONLY
FINAL_MATURITY = P1A-9
AUTHORITY_BOUNDARY = PASS L1c.3
LIVE_MUTATION (this record) = NONE
```

The next phases stay separately gated in the accepted order (preflight
§20). **PR-2** (snapshot inventory) and **PR-3** (the owner off-host
register) come before any **PR-1B** step (K-WIT, registry v1, ledger, V2
genesis, INITIAL_CUSTODY). None of them is authorized by this record.

## Explicitly not done

```text
PR-1A ACCEPTED
SCOPE DEV_SYNTHETIC INERT INSTALLATION ONLY
FINAL MATURITY P1A-9
AUTHORITY BOUNDARY PASS L1c.3
NO K-WIT
NO REGISTRY
NO LEDGER
NO WITNESS STATE
NO HOLD RECORD
NO RECOVERY EPOCH
ACTIVATION STILL DARK
PR-1B NOT AUTHORIZED
B1b-3e LIVE REHEARSAL NOT AUTHORIZED
FIRST MEMORY NOT AUTHORIZED
```
