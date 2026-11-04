# Canonical memory P3: the DEV signer/witness transition to the OWNER_PROD release

Status: PREPARED (source and offline evidence only). Nothing here has run on a host. Each mutating step needs its own
owner go; this record authorizes nothing.

Mode: `UPGRADE_OWNER_PROD_PROFILE_DEV_SYNTHETIC`, lilith-dev-01 only. Previous records:
[P3 release preparation](canonical-memory-p3-release-preparation.md),
[P2 OWNER_PROD profile](canonical-memory-p2-owner-prod-profile.md),
[FM-2 DEV activation](personal-memory-fm2-dev-activation.md).

    contract != authorization;  a staged release != a selected release != an accepted incarnation;  DEV F7 != PROD

## 1. The release

OLD is the installed FM-2 release `d82f7dac669f37c494beebf9bbb99dffdb6c23f5` (archive `9588c85b…`). NEW is the
independently attested build of the #312 merge into main, `88a1168bd41797109772ffce7df7352c1ae40e4c`. The build
used the accepted V3 builder and wheelhouse on Windows (A, a fresh clone) and WSL Ubuntu-24.04 (B).

| | Value |
| --- | --- |
| Archive | `53ae457b8b907e12282ed468da0387620b7a376a46ab1c450709b67540b43c07`, 5391582 bytes (A = B) |
| Manifest | `072001af671feca6564906d3d685f89bfc608f9d595aed58bae0f72a25777684` |
| Builder stamp | `05346fc48dc473f477168fcb43661cc45f66adb64cf068cd6e2a98eec83111af` |
| Identity | `1dafd1c9bb2045443f7579d28d496bf7dbe8a5015ff6c30a70c83a040248553a` |
| Attestation | REPRODUCED `b2f08910794cdd585c15b53c3568136a8ee0a67e7791ebf484609e1e08204f90`; `check` PASS on both archives |
| Recipe | `baa80670562d019a5aaed943604397754368e4cee040dbac75434774a12b3aa0` |
| Release digests | authority `4067cd5da8380fa8278c6942b08fdc66b021ab818d32de463010ccdef3c0de12`; witness `ccc9c5bfed6e2fcba0b584d364deb578232d4429bfbb8657eb4049ac3ec6c790` |
| Evidence | `EVIDENCE-SHA256SUMS` `ef5ee745abea9a65c3f1ecd72b06ea0ebd95132f1bc8b274d8b355d72697aabc` (owner workstation, not in Git) |

**Delta against OLD.** Exactly the 18 members of `owner_prod_signer_upgrade.PAYLOAD_DELTA`, plus the release
manifest. Nothing is added or removed. Units, tmpfiles, CLIs, the lock and the wheels are byte-identical, so archive
layout v3 and `install_authority_dev_v3` apply unchanged. The NEW payload is byte-identical to the rehearsal build of
the P3 source (`706873c`, archive `f22bf71b…`). Only the manifest, which names the candidate, differs.

Two members are recovery-witness code: `lilith_recovery_witness/credential.py` and `server.py`. The witness therefore
restarts from NEW, under its own go.

**No PROD.** The DEV host has no `/etc/lilith-authority-dev/deployment.json`, so NEW runs DEV_SYNTHETIC there, and
every DEV value is byte-identical (P2 DEV-values comparison). The P3 tools contain no PROD name, path, key ID or
environment variable (test-proven). No key, credential, custody record, registry or ledger is created or changed.

## 2. The tools

| File | Role |
| --- | --- |
| `tools/owner_prod_signer_upgrade.py` | the contract: OLD, NEW, attestation record, the 18-member delta, `ready_to_transition()` True |
| `tools/owner_prod_release_stages.py` | `p3-status` / `p3-stage` / `p3-select` / `p3-retire-old` (root on DEV, BOOT-bundled) |
| `tools/owner_prod_operator.py` | the owner-laptop operator: pins, status, preflight, render, the seven steps, verify, accept |
| `tests/owner_prod_transform.py` | the complete difference from the FM-2 tools |

The stage tool and the operator are the accepted FM-2 tools moved by `owner_prod_transform`; the FM-2 files are
byte-unchanged. The transform does exactly this:

- it renames the three FM-2 module names to the P3 modules, and every other `FM2` / `fm2` / `FM-2` name to `P3`;
- it sets the ending incarnations to the FM-2 owner-accepted replacements, signer
  `c32457250aff4155bce1f54f1648945f` / `309023` and witness `1089ad88e0eb4c55b167a48cdb898aa1` / `308690`
  ([FM-2 record §7](personal-memory-fm2-dev-activation.md));
- it states the delta wording as 18 changed members;
- it adds the FM-2 contract to the operator's pins and BOOT bundle, because the P3 contract imports it for OLD;
- it reworks the witness go and acceptance wording, because the witness payload changes;
- it starts with no adjudicated step.

Reused unchanged:
- the E-22 / E-23 transport (pinned plink route, hostname-guarded);
- the single-use attempt markers written before the one remote invocation;
- the canonical go and acceptance texts bound to the latest status digest;
- the F-phase re-judgement;
- the one-clean-re-read rule for the known plink exit crash `0xC0000005`;
- the K-WIT / K-PAN / anchor / witness-unit STOPs;
- the retire guard (no process on OLD).

`scripts/classify_dev_deployment.py` admits exactly these files and this record as CONTROL_ONLY_NO_DEPLOY, so this
merge never restarts the DEV Core API, whose incarnation is part of the transition baseline.

## 3. Baseline (fresh read-only DEV status, 2026-11-04T15:07Z, boot `cb0d71da`)

Equal to the Stage B baseline apart from times.

| Item | State |
| --- | --- |
| Authority release | `d82f7da` only; `current` -> `d82f7da`; installed `protocol.py` `8a082a12…` |
| Signer | `c32457250aff4155bce1f54f1648945f` / 309023, NRestarts 0 |
| Witness | `1089ad88e0eb4c55b167a48cdb898aa1` / 308690, NRestarts 0 |
| Broker | 3411 (since 2026-10-09); Core API `f65f5d6a…` / 444736 at `88a1168`; gateway 442539; provider gate exhausted |
| Privacy | freshness marker PRESENT; FORGET intents 0, none in progress; Privacy DB `fc2f1ee9…` |
| Canonical memories | L04 `553bce4d…`; config DISABLED `4fa82ae6…`; context probe: `lilith_os` codename + origin (`047de4a8…`), `telegram` codename only |
| No-write check | `cm1_window.sh check`: every digest EQUAL; signer / witness / broker state equal; the note appears 0 times |
| Host tree | `/opt/lilith-first-memory-dev/current` 96 files, manifest `d79c061804d037e4c2840c5e448ab3a104d20673d58e797d3fa1a7402dcdf185`, root-owned, none writable; `previous-fm1-e2324a5` kept |
| FORGET copy | the five frozen Core API modules EQUAL the deployed `88a1168` modules; executor.json `82f8567b…` |
| PROD marker | `deployment.json` absent |

## 4. The ladder

Each mutating step has one canonical go, rendered by `render` from the latest status. A step consumes its marker
before its one remote invocation and is followed by one read-only post status. Any other phase is a STOP: no retry,
no automatic stop, start or repair.

| Step | Effect | Pre -> post |
| --- | --- | --- |
| T0 transfer | the archive and builder stamp to `~/lilith-p3-transfer` (one scp, verified) | — |
| preflight | read-only; records the baseline | F0 EXACT |
| STAGE | `p3-stage`: NEW beside OLD from the attested archive | F0 -> F1 |
| SIGNER_STOP | the signer stop (service + socket) | F1 -> F2 |
| WITNESS_STOP | the witness stop (service + both sockets) | F2 -> F3 |
| SELECT | `p3-select`: `current` -> NEW | F3 -> F4 |
| WITNESS_START | one witness start from NEW (one K-WIT, one K-PAN load) | F4 -> F5 |
| verify + accept WITNESS | read-only verify; the owner's verbatim acceptance | F5 |
| SIGNER_START | one signer service start (one K-ACT load) | F5 -> F6 |
| verify + accept SIGNER | read-only verify; the owner's verbatim acceptance | F6 |
| RETIRE | `p3-retire-old`: OLD removed; both accepted replacements named; no process on OLD | F6 -> F7 |

**Outage.** The signer is down from SIGNER_STOP to SIGNER_START, and the witness from WITNESS_STOP to WITNESS_START.
While the signer is down, DEV owner proofs and the context route fail closed: a Hermes turn gets no personal context.
Nothing else stops. The deploy freeze (no Core API, Hermes or broker deploy or restart) lasts until F7 or a STOP.

## 5. Return (owner-adjudicated, no automatic return)

A STOP never rolls back by itself. Every return uses the reviewed unit commands, under its own owner go after a
read-only re-observation. A return ends the ladder: the returned units are new incarnations on OLD, so no later step
can run, and a new transition would need a new contract with new ending incarnations. `ReturnTests` rehearse the
F1 to F5 rows on the synthetic host.

| Stopped at | Return |
| --- | --- |
| F1 | nothing runs from NEW. The staged `releases/<NEW>` may be removed under its own go. The units are untouched |
| F2 / F3 | `current` is still OLD. The reviewed witness start, then signer start, bring both back from OLD |
| F4 | both units stopped. The inverse selector change (`current` -> OLD, symlink + rename), then witness and signer start from OLD |
| F5 | the NEW witness stop, then as F4 |
| F6 | stop both, then as F4 |
| F7 | OLD restaged from its attested archive `9588c85b…` (FM-2 build evidence), then as F4 |

Data is never part of a return: the ladder writes no memory, Privacy, ledger, custody or anchor byte.

## 6. After F7: host tree, FORGET copy, Privacy, acceptance

1. **Host tree.** One go. Build the tree with the accepted FM-1/FM-2 rule (every tracked `.py` of the six packages
   plus `first_memory_dev_host.py`, `first_memory_l04_migration.py`, `relationship_origin_l04_migration.py` and
   `relationship_origin_forget_dev.py`) at `88a1168`. Result: 96 files, tar
   `2b8d28e27d5ec65e9c519faf05c790edd2f87ec516026babb47db3555746e6a2`, manifest
   `af8140a81ab4029d723a0983b0174d5a7c1008d34ef10b3396de46a83fefe444`. It differs from the installed tree
   (`d79c0618…`) in exactly 24 files: the 18 release members, plus `privacy_forget_runner.py`,
   `privacy_freshness_host.py`, `first_memory_conversation.py`, `owner_acceptance.py`, `owner_freshness.py` and
   `first_memory_dev_host.py`. The same rule reproduces the installed tree from `fda4fb7`
   (`6defd601…` / `d79c0618…`). Install it as FM-2 did: stage beside `current`, verify every hash and the
   trusted-tree rule, then swap, keeping the old tree as `previous-fm2-d82f7da`. No migration: the L04 schema is
   already v3.
2. **FORGET executor copy.** No re-pin. The five copied modules (`__init__`, `canonical_contracts`,
   `memory_action_v2`, `canonical_authority`, `privacy_governance`) are byte-identical in `d82f7da` and `88a1168`,
   and the read-only check shows the copy EQUAL to the deployed Core API. The acceptance re-reads that equality.
   `install_f9c.sh --repin` runs only if it ever differs.
3. **Privacy READY.** There is no reboot, so the boot-bound freshness marker stays valid. The check is
   `privacy_freshness_host status` READY, with FORGET idle. If DEV reboots at any point, the owner's Privacy unlock
   comes first (D-4).
4. **No-write acceptance** (read-only):
   - DR-5 target re-derived on NEW;
   - `cm1_window.sh check` with every digest EQUAL to §3 (L04, Privacy, Core API DBs, Hermes memories, request
     dumps);
   - the context probe returns `lilith_os` codename + origin (`047de4a8…`) and `telegram` codename only;
   - `deployment.json` absent;
   - the signer, witness and broker states.
5. **One bounded recall turn** (one provider request, its own approval) on the `lilith_os` channel.

**The grant.** The DEV v2 grant expires `2026-11-07T08:30:11Z`. After that, the probe returns the codename only (fail
closed) and step 5 cannot recall the origin. If acceptance falls later, renew it with one owner go that writes only
`/etc/lilith-first-memory-dev/hermes-owner-channel.json` (same channel `lilith_os`, same scope, new expiry). Nothing
renews it automatically.

## 7. Owner windows (fewer interruptions, same authority)

The operator already supports a bounded run: each go is the canonical render of the latest status, so a driver can
render, write and run the steps in order. It stops at the first result that is not `REACHED` or `VERIFIED`, and it
never retries, returns or repairs. The owner's authority is unchanged: one explicit window approval covers its named
steps, and the two acceptances stay the owner's own verbatim statements.

| Window | Owner message | Steps run | Ends at |
| --- | --- | --- | --- |
| A | approve window A | T0, preflight, STAGE, SIGNER_STOP, WITNESS_STOP, SELECT, WITNESS_START, verify WITNESS | F5 VERIFIED, or the first STOP |
| B | the rendered witness acceptance + approve window B | accept WITNESS, SIGNER_START, verify SIGNER | F6 VERIFIED |
| C | the rendered signer acceptance + approve window C | accept SIGNER, RETIRE, host tree, FORGET-copy check, Privacy READY, no-write acceptance, probe | accepted read-only |
| D (optional) | approve one provider request | one `lilith_os` recall turn | P3 DEV ACCEPTED |

Three owner messages (four with the recall turn) replace about a dozen separate gos. An automatic return is not added:
the accepted process makes every return an adjudicated go, and an unattended selector change while a unit state is
unknown is the riskiest action in the ladder.
