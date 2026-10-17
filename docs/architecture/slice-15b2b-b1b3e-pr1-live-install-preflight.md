# Slice 15B2b-B1b-3e — PR-1 Live Install / Acceptance Preflight

Status:

- **LIVE INSTALL DESIGN / PREFLIGHT**
- **NO LIVE MUTATION PERFORMED**
- **PR-1 NOT AUTHORIZED**
- **B1b-3e LIVE REHEARSAL NOT AUTHORIZED**
- **WHOLE-HOST ROLLBACK UNRESOLVED**
- **REAL AUTHORITY ABSENT**
- **OWNER DECISIONS ACCEPTED:** RR-33 … RR-40 (§34), in the owner-decision
  closure after `c908a95`. **No PENDING_OWNER_DECISION remains before PR-1S**
- **NEXT SLICE: PR-1S** (source/test only), not PR-1A

Base: protected main `954255665e23e0421017a1a0822c3fd6e00a506b` (includes the
merged Source Prep B, `5f5a715` + `5e65c0c`). First draft `c908a95`; this
revision is the owner-decision closure pass. Where the first draft's
recommendation differs from the accepted decision (RR-34 path, RR-36 path,
RR-38 package digest, RR-39 scope, the PR-2 position), the accepted decision
is written in place.

"PR-1" is the prerequisite of the
[live-rehearsal gate](slice-15b2b-b1b3e-live-rehearsal-gate.md) §14: *B1b-3d
L3a–L4 designed for V2, implemented, live, and accepted*. It is not a GitHub
pull-request number.

This record decides what PR-1 owns, how it must be split, which parts must
wait for PR-2 (snapshot inventory) and PR-3 (the owner's off-host register),
and what evidence the owner must see before accepting the DEV_SYNTHETIC
custody baseline. It is a design and a preflight only. It contains no
commands, no runbook, and no authorization. It does not change any source,
test, workflow, or earlier record.

Nothing was contacted or changed: no DEV, PROD, gcloud, SSH, IAP, sudo,
systemctl, or systemd-creds; no installer run; no key, credential, registry,
witness, hold, ledger, epoch, broker ledger, L04, IAM, WIF, or sudoers
touched; no Stage III; no First Memory. Every live fact below comes from an
accepted record, never from observation.

```text
PR-1 acceptance               != positive evidence issuance acceptance
source release prepared       != installed release
installed release             != activation
installation                  != authority
credential loaded             != current authority
hold release                  != authority
witness freshness             != authority
installer success             != owner acceptance
directory existence           != custody readiness
complete observation          != authority
broker preservation proof     != authority proof
routine deployer proof        != owner authority
authority signer installed    != memory activation
```

Labels used for every live-baseline claim (§4):

| Label | Meaning |
| --- | --- |
| **KNOWN** | KNOWN FROM ACCEPTED EVIDENCE: stated by an accepted, merged record |
| **EXPECTED** | EXPECTED FROM SOURCE: what current source or documented systemd behaviour implies. Not a live fact |
| **UNKNOWN** | UNKNOWN UNTIL LIVE PREFLIGHT: not in any merged record; must be observed read-only before any mutation |

## 1. Controlling records and source

Current source governs current behaviour. Where a record and the source
differ, this record says so (§2).

| Area | Record / source |
| --- | --- |
| B1b-3d custody design, ladder §23, paths §15, witness §10, ledger §12 | [slice-15b2b-b1b3d-dev-synthetic-custody-design.md](slice-15b2b-b1b3d-dev-synthetic-custody-design.md) |
| L2 runbook, installer contract, N-45 | [slice-15b2b-b1b3d-l2-custody-preparation.md](slice-15b2b-b1b3d-l2-custody-preparation.md) |
| live baseline at closure | [slice-15b2b-b1b3d-live-closure.md](slice-15b2b-b1b3d-live-closure.md) |
| DR-5 routine deployer proof | [slice-15b2b-b1b3d-deployer-authority-boundary.md](slice-15b2b-b1b3d-deployer-authority-boundary.md), `scripts/deployer_authority_boundary_proof.sh` |
| broker preservation | `scripts/verify_broker_dev_current_incarnation.py` (`preservation`) |
| B1b-3e design and state owners | [slice-15b2b-b1b3e-rotation-revocation-recovery.md](slice-15b2b-b1b3e-rotation-revocation-recovery.md) §4 |
| B1b-3e source contracts | [slice-15b2b-b1b3e-source-contracts.md](slice-15b2b-b1b3e-source-contracts.md) |
| gate: RR-6/7/9/11/17–21, PR-1..3, entry matrix | [slice-15b2b-b1b3e-live-rehearsal-gate.md](slice-15b2b-b1b3e-live-rehearsal-gate.md) |
| Source Prep A: V2 genesis, pin, inventory, durable TEST writer | [slice-15b2b-b1b3e-source-prep-a-witness-readiness.md](slice-15b2b-b1b3e-source-prep-a-witness-readiness.md) |
| Source Prep B design: RR-22..30 | [slice-15b2b-b1b3e-source-prep-b-design.md](slice-15b2b-b1b3e-source-prep-b-design.md) |
| Source Prep B source: custody, holds, C-4 gate, RR-31/32 | [slice-15b2b-b1b3e-source-prep-b-successor-custody.md](slice-15b2b-b1b3e-source-prep-b-successor-custody.md) |
| authority-dev runtime | `services/authority-dev/lilith_authority_dev/{profile,credential,core,server}.py` |
| release payload contract | `services/authority-dev/release_file_set.py` |
| installer / builder / keygen | `services/authority-dev/ceremony/{install_authority_dev,build_authority_dev_release,lilith_authority_keygen_dev}.py` |
| unit assets | `services/authority-dev/deploy/lilith-authority-dev.{service,socket,tmpfiles.conf}` |
| pure contracts | `services/owner-memory-control/lilith_owner_memory/{rotation_contracts,witness_readiness,successor_custody,successor_readiness}.py` |
| TEST-only models | `services/owner-memory-control/lilith_authority_signer/{synthetic_witness_v2,synthetic_witness_store,synthetic_recovery_ledger}.py` |

### 1.1 Source facts that control this design

| # | Source fact | Location |
| --- | --- | --- |
| PF-1 | The signer core has no registry, witness, ledger, or hold input. `readiness_reasons` always appends `REGISTRY_MISSING`, `WITNESS_MISSING`, `AUTHORITY_STATE_MISSING`; readiness is always `NOT_READY`; `ISSUE_OWNER_EVIDENCE` is always refused | `lilith_authority_dev/core.py` |
| PF-2 | The credential module reads only `$CREDENTIALS_DIRECTORY/owner-actor-signing-key`, keeps only the public fingerprint, and drops the private-key object | `lilith_authority_dev/credential.py` |
| PF-3 | The server exits `CREDENTIAL_ABSENT`/`CREDENTIAL_INVALID` before serving; there is no credential-less mode | `lilith_authority_dev/server.py` |
| PF-4 | Runtime modules and shared contracts are **byte-identical** between the installed `9ac7de2` and current main. Only two release members differ: `assets/lilith-authority-dev.service` (adds `/etc/lilith-authority-custody` to `InaccessiblePaths`) and `cli/lilith-authority-keygen-dev` (adds `successor <N>`) | `git diff 9ac7de2 HEAD -- services/authority-dev`; Source Prep B §15 |
| PF-5 | Every mutating installer stage is **fresh-install only**: `release` requires the exact L1a POST (no `/opt/lilith-authority-dev`); `select` refuses an existing `current`; `units` and `cli` create with `O_EXCL`; `accounts` refuses an existing name. There is no upgrade stage | `install_authority_dev.py:548-630` |
| PF-6 | `status` requires `releases/` to hold exactly `[<RELEASE_SHA>]` (`RELEASE_SET`), `current -> releases/<RELEASE_SHA>`, unit and CLI bytes equal to that release, both units inactive and not enabled, and every `DEFERRED_PATHS` entry absent (including `/var/lib/lilith-authority-dev`, `/etc/lilith-authority-dev`, the witness paths, and the K-WIT blob) | `install_authority_dev.py:99-103`, `:410-497` |
| PF-7 | `status` **observes** `credentialBlobSha256` but never compares it with a pinned value; it checks only that the blob is a `root:root 0600` file. It pins no account uid/gid | `install_authority_dev.py:324-354`, `:488` |
| PF-8 | The `custody` stage (installer ladder name `L2c`) requires the exact `L2b.2` POST **for the successor-capable RELEASE_SHA**, creates `/etc/lilith-authority-custody`, `prepared/`, `retired/` `root:root 0700`, fsyncs the root and `/etc`, and checks names, emptiness, and one `st_dev` with the credstore | `install_authority_dev.py:500-517`, `:653-668` |
| PF-9 | The keygen refuses `witness` (`WITNESS_NOT_IN_SCOPE`). `actor` refuses a non-empty credstore; `successor <N>` refuses a credstore that is not exactly the CURRENT slot (`CREDSTORE_NOT_EXACTLY_CURRENT`) | `lilith_authority_keygen_dev.py:261-262`, `:321`, `:367` |
| PF-10 | The Prep A inventory treats **any** credstore name other than the CURRENT slot as `UNEXPECTED_CREDENTIAL_BLOB` | `witness_readiness.py` (SW-6); Prep A §6 |
| PF-11 | `plan_witness_v2_genesis` requires `ledger_sequence ≥ 1`; the genesis binds `(ledgerSequence, ledgerHead)` of the authority recovery ledger. The ledger model's sequence 0 head is `LEDGER_HEAD_GENESIS = "0"*64`; its `GENESIS` journal op is sequence 1 and holds only `{environment, recoveryEpoch, policyVersion, registryVersion, signingKeyIds}` (no timestamp) | `rotation_contracts.py:1100-1135`; `authority_contracts._int`; `synthetic_recovery_ledger.py:150`, `:193-199`, `:270-271`, `:302-305`; `recovery_contracts.py:55` |
| PF-12 | `witness_v2_digest` is SHA-256 over the **signed fields**, which exclude `signature` and include `witnessKeyId` and `updatedAt`. The genesis digest is therefore computable before K-WIT signs | `rotation_contracts.py:613-615` |
| PF-13 | The only V2 witness writer, the durable store, and the recovery ledger are TEST-only models in `lilith_authority_signer`. `release_file_set.FORBIDDEN_RUNTIME_MARKERS` refuses `lilith_authority_signer` in any runtime payload | `synthetic_witness_v2.py`, `synthetic_witness_store.py`, `synthetic_recovery_ledger.py`; `release_file_set.py:82` |
| PF-14 | No source exists for: a recovery-witness service, unit, socket, account contract, or DEV_SYNTHETIC V2 writer profile; a K-WIT keygen; a K-ROOT generator or registry signer for DEV_SYNTHETIC; a durable authority ledger; a ledger provisioning CLI; a hold writer or hold-store observer; an independent root verifier CLI. (`git ls-files` finds no `lilith-recovery-witness` runtime or unit) | repository search |
| PF-15 | `evaluate_recovery_gate` takes **one** caller-supplied `hold` record, not the complete hold store, and its `ledger_observation` argument is **optional** (`ADOPTION_ALREADY_JOURNALLED` is checked only when it is given). `evaluate_successor_readiness` does judge the complete store | `successor_readiness.py:814-870`, `:588-600` |
| PF-16 | The signer unit has `ReadOnlyPaths=/opt/lilith-authority-dev /etc/lilith-authority-dev /var/lib/lilith-recovery-witness`, `InaccessiblePaths=/etc/credstore.encrypted /etc/lilith-authority-custody …` (the latter in the prepared release), and `StateDirectory=lilith-authority-dev`, none prefixed with `-` | `deploy/lilith-authority-dev.service` |
| PF-17 | The DR-5 proof's ladder ends at `L1c.3`; `/etc/lilith-authority-custody` is not in its ladder or its later-state list; its later-state list checks `/etc/*` paths for `-w` only; it probes only the authority-dev units; it refuses any `releases/` entry that is not 40-hex (a `.<sha>.staging` directory fails it) | `scripts/deployer_authority_boundary_proof.sh` |
| PF-18 | The broker `preservation` operation reports `CUSTODY_PATHS` without judging them. `/etc/lilith-authority-custody` is not in the list. Custody observations are **not** part of the pinned `baselineCandidate` hash | `scripts/verify_broker_dev_current_incarnation.py:179-190`, `:396-446`, `:495-536` |
| PF-19 | The needrestart control already carries `override_rc = 0` for `lilith-recovery-witness.service` | `services/memory-broker/deploy/needrestart-lilith-authority-sensitive.conf` |

## 2. Conflicts and naming hazards found

| # | Conflict | Consequence for PR-1 |
| --- | --- | --- |
| PC-1 | B1b-3d §15 puts the K-WIT blob at `/etc/credstore.encrypted/lilith-recovery-witness.witness.cred`. Prep A (PF-10) and the successor keygen (PF-9) require the credstore to hold **exactly** the CURRENT K-ACT slot | a K-WIT blob there would make every readiness evaluation fail `UNEXPECTED_CREDENTIAL_BLOB` and block every successor keygen. **Resolved by RR-36 (OWNER-ACCEPTED):** K-WIT lives under `/etc/lilith-recovery-witness/credentials/`; the B1b-3d §15 credstore path is superseded (not edited) and must stay absent |
| PC-2 | B1b-3d §10/§23 L3b bootstraps the witness at `ledgerSequence = 0` **before** the ledger (L3c). The accepted V2 genesis (RR-18, PF-11) needs `ledgerSequence ≥ 1`, which only a provisioned ledger provides | the V2 order is ledger first, then genesis (§14). The B1b-3d §23 L3b/L3c order is superseded for V2 (the design record is not edited) |
| PC-3 | The installer ladder name `L2c` means "custody directories" (Source Prep B). B1b-3d §23 `L2c` means "K-WIT keygen" | two different mutations share a name. PR-1 phases use the `P1A-*` / `P1B-*` names below and call the installer stage by its name, `custody` |
| PC-4 | B1b-3d §13 step 1 puts the ceremony hold at `/etc/lilith-authority-dev/hold`. Source Prep B makes the hold a store of records named `<sha256(ceremonyId)>.json` whose location PR-1 fixes | **Resolved by RR-34 (OWNER-ACCEPTED):** `/var/lib/lilith-authority-custody/holds/`; the single-file hold is superseded (not edited) |
| PC-5 | The gate's PR-1 evidence is "the B1b-3d acceptance record". B1b-3d §22 acceptance includes positive signing (P2–P4, §22 item 3) and R1–R5 (L7). The gate's PR-1 text names only L3a–L4 and a `RESTORE_READY` signer | **Resolved by RR-39 (OWNER-ACCEPTED):** PR-1 does not wire or prove positive issuance. Its acceptance record names a narrower claim (§5.1) and never claims full legacy B1b-3d §22 acceptance |
| PC-6 | B1b-3d §7 keys the DR-5 existence rule on an `INSTALLED` marker written at L4. The accepted deployer boundary derives maturity from root-owned ladder objects instead, and introduces no marker | PR-1 writes **no** `INSTALLED` marker. The ladder derivation is extended instead (§9). The broker verifier's `…/INSTALLED` entry stays `NOT_YET_PRESENT` |
| PC-7 | The signer runs as `lilith-authority-dev` with `InaccessiblePaths=/etc/credstore.encrypted`. It therefore cannot observe the credential inventory (B6) that `FULL_READINESS` requires | `FULL_READINESS` can be reproduced only by a root observer, never by the signer about itself. The signer reports a partial self-view (§19, §33) |

> **Erratum (2026-10-07, M-B6 remediation D-5; the table above is unchanged).** A naming hazard missing from this
> list: the ledger-journal `GENESIS` op (M-B6, a journal row at sequence 1) ≠ the witness genesis candidate
> (M-B7, unsigned bytes) ≠ `OwnerGenesisPinV1` (M-B8, the owner's pin of the candidate digest) ≠ the committed
> witness genesis (M-B9b, `chain/1.json`). See the [M-B6 remediation record](slice-15b2b-b1b3e-mb6-ledger-remediation.md) §11.

## 3. Invariants

Inherited without change: every invariant of the gate §3, Source Prep A §15,
and Source Prep B's status block. Pinned in addition by this record:

```text
PR-1A success             != custody readiness
upgrade completed         != authority change
old release removed       != authority rollback impossible  (release rollback != authority rollback)
K-WIT credential exists   != witness exists
ledger provisioned        != authority state accepted
genesis candidate digest  != genesis
genesis committed         != genesis accepted
owner pin                 != authority
INITIAL_CUSTODY HELD      != custody accepted
eligibility PASS          != owner acceptance
owner acceptance          != activation
RELEASED                  != issuance permission
FULL_READINESS READY      != issuance wired
FULL_READINESS READY      != memory activation
```

## 4. Current DEV baseline

No DEV contact was made. Every row is classified. Nothing in the **EXPECTED**
or **UNKNOWN** columns is a live fact.

| # | Item | Classification | Value / basis |
| --- | --- | --- | --- |
| B-1 | installed authority-dev release | **KNOWN** | `RELEASE_SHA=9ac7de22bf977385ceb954624677e33f0bae062b` (live closure §3). Its members `cli/…keygen-dev` `f1e7020b…d81232`, `assets/….service` `249f2ec9…b62b1bc` (Source Prep B §15) |
| B-2 | releases directory holds only `9ac7de2`, `current -> releases/9ac7de2` | **KNOWN** at closure; **UNKNOWN** since | the L2b.2 POST at closure checks `RELEASE_SET` and `CURRENT_TARGET` |
| B-3 | control generation of the last DR-5 proof | **KNOWN** | `CONTROL_SHA=293a4c3f3c225dd57113d207133eacb8ffa236cb` |
| B-4 | CURRENT credential path | **KNOWN** | `/etc/credstore.encrypted/lilith-authority-dev.owner-actor.cred`, `root:root 0600`; credstore `root:root 0700` |
| B-5 | CURRENT blob SHA-256 | **KNOWN** | `6a61c350e848a833868f4573982fca9c75e2af79ccc9bd3716ae0303c26973f3` (equal to the publication `blobSha256`) |
| B-6 | runtime credential name | **KNOWN** | `owner-actor-signing-key` (unit, keygen, publication) |
| B-7 | K-ACT key ID | **KNOWN** | `test-only.dev-synthetic.actor.b1b3d.1`, Ed25519, `OWNER_ACTOR`, `OWNER_MEMORY_OPERATION` |
| B-8 | K-ACT public key and `publicKeySha256` | **UNKNOWN** to the repository | the values are in the owner-retained publication (`/root/b1b3d-l2b-publication.json` at the ceremony, L2 runbook L2b.2). No merged record carries them. Where the owner copy now lives is not recorded |
| B-9 | HEALTH fingerprint (B4) | **UNKNOWN**; **EXPECTED** unobserved | the signer has **never started** (closure §6: no state dir, no `/run/credentials/…`). L2 U5 ("blob decrypts to the published key") is still open |
| B-10 | host key | **KNOWN** | `/var/lib/systemd/credential.secret` `root:root 0400`, PRESENT_SECURE; never printed or copied |
| B-11 | signer account | **KNOWN** (contract); **UNKNOWN** (numbers) | exists with the L1a contract (system, `< 1000`, primary group only, nologin, `/nonexistent`, locked, no sudo). The numeric uid/gid are recorded only in the owner's L1a POST transcript (U1), not in the repository |
| B-12 | service state | **KNOWN** at closure; **UNKNOWN** since | both units loaded, inactive, `static`, not enabled; never started |
| B-13 | deployer-observed maturity | **KNOWN** | `AUTHORITY_BOUNDARY_PROOF=PASS maturity=L1c.3` (closure §7). Later routine deployments may have run the proof again; their results are **UNKNOWN** here |
| B-14 | root-observed maturity | **KNOWN** | installer `status --expect L2b.2 9ac7de2` PASS at closure and after the routine deployment (closure §8) |
| B-15 | broker preservation | **KNOWN** | `BROKER_PRESERVATION=PASS`, incarnation `42af2691b8d24ee5a92a286197c5444c`, candidate SHA-256 `3549585487ad46ead96a0cb1af30a15be0c4ac17575663816e8e11dc80a7eee5` |
| B-16 | activation | **KNOWN** | `ACTIVATION=NOT_ACCEPTED reason=GRANT_ABSENT` |
| B-17 | authority recovery ledger | **KNOWN** absent; **EXPECTED** absent | `/var/lib/lilith-authority-dev` absent at closure; no durable ledger source exists (PF-13) |
| B-18 | registry, trust anchors, `/etc/lilith-authority-dev` | **KNOWN** absent | closure §6; gate §1 |
| B-19 | `RecoveryWitnessV2` live | **KNOWN** absent; **EXPECTED** impossible today | no live writer or service source (PF-13, PF-14) |
| B-20 | witness service / account `lilith-recovery-witness` | **KNOWN** absent | closure §6; L2 D-W deferred the account |
| B-21 | K-WIT custody | **KNOWN** absent | closure §6: "K-WIT is absent" |
| B-22 | live hold storage | **KNOWN** absent | accepted location `/var/lib/lilith-authority-custody/holds/` (RR-34) |
| B-23 | custody root, `prepared/`, `retired/` | **KNOWN** absent at closure; **EXPECTED** absent | the `custody` stage did not exist at closure and is source-only (Source Prep B §14) |
| B-24 | owner off-host register / genesis pin | **KNOWN** absent | Source Prep A §7.1: no real off-host storage is built; no genesis exists to pin |
| B-25 | snapshot inventory | **KNOWN** absent; snapshots **UNKNOWN** | PR-2 not performed. Whether any disk or machine-image snapshot of `lilith-dev-01` exists is unknown |
| B-26 | K-ROOT | **KNOWN** absent from DEV; **UNKNOWN** off-host | absent from DEV, GitHub, and the repository by design; no record says whether the owner has generated one |
| B-27 | DR-3 (`ubuntu` root-equivalent), whole-host rollback | **KNOWN** OPEN | closure §11 |
| B-28 | Stage III artefacts, broker release `817a83e…` | **KNOWN** untouched at closure | every PR-1 phase re-hashes them (B1b-3d §23 preservation set) |

## 5. PR-1 decomposition

Source inspection shows PR-1 cannot be one live ceremony. Most of the
machinery it must install does not exist (PF-13, PF-14, §31). PR-1 is split
into three gates with different failure domains:

```text
PR-1S  source/runtime wiring (no DEV contact)
  -> PR-1A  inert live installation (release upgrade + empty structure; no credential, no authority state)
  -> PR-1B  bootstrap and owner acceptance (K-WIT, registry, ledger, V2 genesis, INITIAL_CUSTODY)
```

PR-2 and PR-3 interleave as §20 shows. The label "PR-1" is kept for the
gate's single prerequisite row; its three parts are accepted separately.
**RR-33 (OWNER-ACCEPTED)** fixes this split and the single-upgrade rule
(§6.1): PR-1S produces the **one** reviewed release PR-1A installs, holding
all source/runtime machinery known to be required for the accepted PR-1
baseline. PR-1S performs no live mutation; PR-1A installs inert machinery
only; PR-1B establishes V2/bootstrap/readiness state only after its PR-2 and
PR-3 dependencies are satisfied.

| | PR-1S | PR-1A | PR-1B |
| --- | --- | --- | --- |
| may mutate | repository only | `/opt/lilith-authority-dev` release set and selector; installed unit/socket/tmpfiles files; `/usr/local/sbin/lilith-authority-*-dev`; `systemctl daemon-reload`; empty custody root and slots; the `lilith-recovery-witness` account; empty root-owned skeleton directories (`/etc/lilith-authority-dev/{trust,registry}`, `/etc/lilith-recovery-witness/credentials/`, `/var/lib/lilith-authority-custody/holds/`) | K-WIT blob; trust anchors; registry v1; the authority recovery ledger; the on-host pin copy; witness state dir + V2 genesis; hold store records; signer and witness runtime (started, never enabled) |
| must stay unchanged | every host | CURRENT blob bytes and identity; credstore listing; host key; signer account; K-ACT; units inactive and not enabled; activation; broker; Stage III; IAM/WIF/sudoers | CURRENT blob bytes and identity; host key; K-ACT; activation `GRANT_ABSENT`; broker; Stage III; IAM/WIF/sudoers; the routine deployer rule |
| evidence | CI, tests, release manifest, reproducible build | pre/post installer `status` per stage; CURRENT preservation (§24); installed-release evidence (§23); DR-5 + broker preservation on a real routine deployment | per-phase POST (§27); the owner acceptance package (§19) |
| blocks continuation | any §31 blocker open | any baseline mismatch (§7); any preservation diff | PR-2 or PR-3 missing where §20 requires them; any RR-7 class 1–4; any readiness reason other than the hold |
| rollback boundary | revert | release rollback to a reviewed prior archive, before any authority PONR | per phase (§29); forward-only from V2 genesis commit |
| authority state changes | no | **no** | **yes, and only by K-ROOT**: registry v1 becomes the genesis head through the witness. Nothing is granted by the host |
| custody state changes | no | **no** (empty directories only) | yes: K-WIT created; hold store written |
| owner acceptance | review + merge | PR-1A acceptance record (inert install; no custody claim) | the explicit INITIAL_CUSTODY release decision over the digest-bound package (RR-38), then the PR-1 acceptance record (§5.1) |

### 5.1 The PR-1 claim (RR-39, OWNER-ACCEPTED)

PR-1 scope is exactly:

- B1b-3d L3a–L4-style live custody and bootstrap establishment, re-derived
  for V2 (registry v1, anchors, K-WIT custody, authority recovery ledger, V2
  genesis);
- the accepted OS, routine-deployer, and broker denial proofs (B1b-3d §17
  N1–N9, D1–D12, B1–B4, plus the custody, witness-credential, and hold-store
  paths);
- loaded-key / HEALTH fingerprint verification: the independently
  reproduced custody/publication/blob binding (B1 = B3 = B2, with B5/B6)
  plus the runtime-derived HEALTH fingerprint (B4). This is the current
  accepted loaded-key evidence; RR-14a proof-of-possession stays deferred per
  the B1b-3e design;
- the V2 / INITIAL_CUSTODY hold / readiness bootstrap through
  `FULL_READINESS`.

PR-1 does **not** enable or prove positive OwnerEvidence issuance. Issuance
stays unwired (`ISSUE_OWNER_EVIDENCE` is refused even at `FULL_READINESS`
READY). No real OwnerEvidence signing is performed to satisfy the older
B1b-3d §22 acceptance shape (P2–P4 and R1–R5, §22 items 3 and 13–16).

The PR-1 acceptance record therefore names this narrower claim:

```text
B1b-3d L3a–L4 (V2) DEV_SYNTHETIC custody bootstrap ACCEPTED
  issuance: UNWIRED; positive evidence issuance: NOT ACCEPTED, NOT PROVEN
  legacy B1b-3d §22 "DEV_SYNTHETIC CUSTODY PROVEN": NOT CLAIMED
```

The gate's PR-1 row ("B1b-3d L3a–L4 designed for V2, implemented, live, and
accepted … `RESTORE_READY` signer"; evidence "the B1b-3d acceptance record")
is satisfied by that record, read with this narrower claim:
`RESTORE_READY` means `FULL_READINESS` READY reproduced by the independent
root verifier and the owner (RR-38), not issuance. No real authority gate is
weakened: every readiness, binding, inventory, hold, and denial condition
still applies; only the claim is narrower.

```text
PR-1 acceptance != positive evidence issuance acceptance
```

## 6. Installed release upgrade

### 6.1 Which release is installed

Source Prep B prepared a successor-capable **source** release (PF-4). It
differs from `9ac7de2` only in the unit's `InaccessiblePaths` and the keygen's
`successor <N>` form. It still has no witness, ledger, registry reader, hold
reader, C-4 wiring, or readiness (PF-1). Installing it alone would satisfy
RR-25 only until PR-1S produces the release PR-1B needs, and then a **second**
upgrade of the custody host would follow.

**Accepted (RR-33):** do not install the Source Prep B release on its
own. PR-1A installs exactly one release: the reviewed PR-1S release, which
contains the Source Prep B changes plus the §31 runtime work. One upgrade,
one release-set transition, one set of provenance evidence.

```text
source release prepared != installed release
installed release       != authority activation
```

### 6.2 What the upgrade must preserve

Fail closed if any of these differ before or after any upgrade stage (§24):

- the CURRENT blob: path, type, `root:root 0600`, size, `st_dev`/`st_ino`,
  SHA-256 `6a61c350…`, and its `mtime`/`ctime`;
- the credstore listing: exactly one name, the CURRENT slot;
- the runtime credential name `owner-actor-signing-key` and the single
  `LoadCredentialEncrypted=` directive naming CURRENT;
- the host key's identity (`st_dev`, `st_ino`, size, mode, owner, `mtime`,
  `ctime`). It is **never read or hashed**, matching L2a ("stat only");
- the signer account: name, uid, gid, and every L1a contract fact;
- the K-ACT identity (unchanged key ID; no keygen run);
- `ACTIVATION=NOT_ACCEPTED reason=GRANT_ABSENT`;
- no PREPARED or RETIRED blob, and no successor credential of any kind;
- no registry, witness, ledger, hold, or state directory created by the
  upgrade itself.

### 6.3 Upgrade analysis

| Topic | Design |
| --- | --- |
| source tree replacement | the new tree is staged as `releases/.<NEW>.staging`, verified against the attested archive, venv-built offline with `--require-hashes`, import-checked as the service identity, then renamed to `releases/<NEW>`. The old tree is not touched. Transiently `releases/` holds `{OLD, NEW}`. This state is new: today's `status` calls it `RELEASE_SET` FAIL (PF-6), so the upgrade needs its own expected-state stages (§7) |
| immutable release verification | the archive attestation and manifest (installer `verify_archive`) plus a **full** post-install tree check (every manifest file's bytes, no extra files outside `venv/`, venv file-set digest recorded). Today's `status` compares only unit and CLI bytes with the release copy, not the release tree with its manifest. SOURCE CHANGE REQUIRED (§23) |
| selector switch | `current` is re-pointed by `symlink(tmp) → rename(tmp, current)`, a same-directory atomic replace. The service is stopped, so nothing loads through it until PR-1B |
| unit-file replacement | the installed unit, socket, and tmpfiles files are **replaced** (tmp + fsync + rename + directory fsync), not created: `O_EXCL` refuses today (PF-5). Byte equality with `releases/<NEW>/assets/*` afterwards |
| daemon-reload | a separate stage after unit replacement: `NeedDaemonReload=no`, both units `loaded`, `inactive`, `static`. Until it runs, systemd holds the old unit definition (`NeedDaemonReload=yes`). Harmless while stopped, but PR-1B must never start a unit whose `NeedDaemonReload` is not `no` |
| service restart | **not required and not performed.** The signer has never started (B-9); it stays stopped throughout PR-1A (§25) |
| can the service stay stopped | yes. Nothing in PR-1A needs a running signer. HEALTH is first needed in PR-1B for B4 |
| CLI replacement | `/usr/local/sbin/lilith-authority-keygen-dev` is replaced (not created) by the new release copy. New fixed CLIs (§31) are created. `CLI_BYTES` equality for each |
| old release retirement (RR-25) | `releases/<OLD>` is removed only after selector, units, reload, and CLIs all name NEW. Afterwards `status --expect L2b.2 <NEW>` must PASS **exactly as written today**: that contract is already the correct upgraded end state |
| prior-release provenance | `9ac7de2` stays preserved by repository history, its reviewed archive + attestation hashes (owner-retained), and the closure record. The upgrade record binds `OLD=9ac7de2`, `NEW=<PR-1S RELEASE_SHA>`, the CONTROL_SHA of the installer used, and both manifests |
| rollback before an authority PONR | allowed as a separately reviewed operational recovery (RR-25): re-stage the reviewed `9ac7de2` archive and run the same upgrade stages in reverse direction. It never touches CURRENT. Before `releases/<OLD>` is removed, rollback is a selector/unit/CLI flip back |
| release rollback after an authority PONR | allowed only as code rollback; it never rolls authority back. After V2 genesis the witnessed head, the ledger, and the holds stay authoritative for their own facts. An old release that cannot read them simply fails closed (`NOT_READY`) |

## 7. Upgrade must not look like fresh install

### 7.1 Fresh-install assumptions in current source

| # | Assumption | Where | Unsafe on the custody host because |
| --- | --- | --- | --- |
| FI-1 | `release` requires the L1a POST: no `/opt/lilith-authority-dev` | `stage_release` → `status(L1a)` | refuses the upgrade; a "fix" by deleting `/opt/…` first would destroy the only executable release |
| FI-2 | `select` refuses an existing `current` | `stage_select` | an upgrade must replace it atomically |
| FI-3 | `units` and `cli` write with `O_EXCL` | `_write_new` | an upgrade must replace existing files; removing them first leaves a window with no unit definition |
| FI-4 | `status` requires exactly `[<RELEASE_SHA>]` in `releases/` at every stage from L1b.1 | `status` `RELEASE_SET` | the transient `{OLD, NEW}` state has no contract |
| FI-5 | `status` expects every later path absent (`DEFERRED_PATHS`) | `expected_paths` | correct for PR-1A, wrong from PR-1B on; PR-1B needs its own stage contracts (§31 S-12) |
| FI-6 | `status` never compares the blob hash or account uid/gid with accepted values | PF-7 | an upgrade could pass `status` with a replaced blob or a re-created account |
| FI-7 | `accounts` creates the one signer account from nothing | `stage_accounts` | the signer account already exists and must be adopted unchanged; the witness account is new and needs its own contract (distinct uid/gid, not in `lilith-authority-dev`'s group except as §10 designs) |
| FI-8 | `actor` keygen assumes an empty credstore | keygen `CREDSTORE_NOT_EMPTY` | never run again on this host. The upgrade must not offer it as a step |
| FI-9 | units are assumed never started | `status` `UNIT_ACTIVE` | true today (B-9) and must stay true through PR-1A; PR-1B stages must allow active, never-enabled units |
| FI-10 | ownership normalization walks the staged tree only | `_normalize_tree` | correct; must never be pointed at `releases/<OLD>` or `current` |

### 7.2 `UPGRADE_EXISTING_DEV_SYNTHETIC` (design decision only; not implemented)

A new, closed installer mode. Design only; PR-1S implements it (S-2).

- **Entry:** only from `status --expect L2b.2 9ac7de2` PASS **plus** an
  accepted-baseline pin passed as fixed arguments that the tooling compares
  exactly: OLD release SHA; CURRENT blob SHA-256 `6a61c350…`; CURRENT
  `(st_dev, st_ino, size)`; host key identity tuple; signer uid/gid as
  recorded in the owner's L1a POST; NEW release SHA with its attestation.
- **Refuses** if any accepted-baseline fact differs, if any `DEFERRED_PATHS`
  entry exists, if either unit is active or enabled, if `NeedDaemonReload` is
  not `no`, if a staging or temporary name exists, if the credstore holds
  anything but CURRENT, or if the custody root exists.
- **Stages** (one logical transition each, each with its own POST):
  `upgrade-stage` (NEW tree beside OLD), `upgrade-select`, `upgrade-units`,
  daemon-reload (an owner command, as L1c.2 today), `upgrade-cli`,
  `upgrade-retire-old`. Each stage's POST re-proves every §6.2 fact.
- **End state:** `status --expect L2b.2 <NEW>` PASS, unchanged contract.
- **Never:** runs any keygen, `systemd-creds`, `useradd` for the signer,
  `systemctl start|enable`, creates a PR-1B path, or reads the host key.
- There is no `--force`, no path argument, and no "repair" of a mismatch.
  A mismatch is a STOP for the owner.

## 8. Custody root install

The custody structure is created by the existing `custody` stage (PF-8),
run once PR-1A has reached `status --expect L2b.2 <NEW>` PASS.

| Object | Contract | Explicit state? |
| --- | --- | --- |
| `/etc/lilith-authority-custody` | `root:root 0700`, directory, not a symlink, exactly two entries `prepared`, `retired` | **yes**: the custody root is explicit state. Its entry set is checked (`CUSTODY_ROOT_UNEXPECTED_ENTRY`); an extra entry would be an unexpected slot |
| `…/prepared`, `…/retired` | `root:root 0700`, directories, not symlinks, **empty** | yes |
| `/etc` | the parent; root-owned `0755`; fsynced after creation | inherited |

Live evidence the custody POST must carry (read-only, root):

| Property | Evidence |
| --- | --- |
| directory identity | `lstat` of all three: type, `st_dev`, `st_ino`; `O_DIRECTORY\|O_NOFOLLOW` open succeeds; re-`fstat` on the descriptor equals the path `lstat` |
| ownership / mode | `uid 0`, `gid 0`, `0700` for each |
| emptiness | `getdents` of each slot through the descriptor: zero entries |
| `st_dev` relation | `st_dev(credstore) == st_dev(prepared) == st_dev(retired)` (installer `custody_failures`; keygen preflight) |
| authority service denial | config level: the installed unit bytes equal the NEW release asset and `systemctl show -p InaccessiblePaths` lists `/etc/lilith-authority-custody`. Runtime level (PR-1B, signer running): a probe inside the signer's mount namespace as the signer uid observes the path inaccessible. SOURCE CHANGE REQUIRED for the probe (§31 S-15) |
| routine deployer denial | DR-5: `-r`, `-w`, `-x` denied on `/etc/lilith-authority-custody` with the path existing (stat is possible: `/etc` is traversable). `prepared/` and `retired/` are `UNOBSERVABLE_BY_DESIGN` to the deployer, like the K-ACT blob. SOURCE CHANGE REQUIRED (§9) |
| broker denial | root-run probe as `lilith-memory-broker`: `-r`, `-w`, `-x` denied on the custody root. SOURCE CHANGE REQUIRED (§31 S-15) |
| no credential | the keygen was not run; `prepared/` and `retired/` stay empty; CURRENT unchanged (§24) |

`directory existence != custody readiness`. The custody POST proves only
that empty, correctly owned slots exist on the right filesystem. It proves
nothing about any key, and it does not engage the successor keygen.

## 9. Broker preservation and routine deployer proof

**Broker preservation today** (PF-18) checks the accepted broker release,
config, state, identity, socket, Stage III artefacts, deployer policy text,
and the accepted incarnation and candidate hash. It **reports**
`CUSTODY_PATHS` presence and never judges it (`authorityCustodyJudgment:
NOT_PERFORMED`).

Why the custody root (and every other PR-1 path) must be added: the
preservation transcript is the owner's record that each routine deployment
left the broker unchanged **while** the authority paths existed. A path not
in the list is silently absent from that record. Adding
`/etc/lilith-authority-custody`, `/etc/lilith-recovery-witness/credentials/`
(RR-36), `/var/lib/lilith-authority-custody/holds/` (RR-34),
`/etc/lilith-authority-dev/{trust,registry}`, and
`/var/lib/lilith-authority-dev/authority_ledger.db` makes the transcript
complete. Because custody observations are outside the pinned
`baselineCandidate` (PF-18), adding paths does **not** change the accepted
candidate SHA-256 `3549585…` and needs no new broker baseline.

Exact property: *broker continuity holds, and every listed authority path's
presence is reported; no authority fact is judged.*

**DR-5 today** (PF-17) ends at `L1c.3` and does not know the custody root,
the witness identity, witness units, the hold store, or the transient upgrade
names. Required extension:

- ladder objects for the custody root (`directory|700`, denials `-r -w -x`),
  the witness account (`sudo -u lilith-recovery-witness` denied), witness
  units (every unit verb denied), new CLIs (`sudo -n -l` denied), the
  `/etc/lilith-authority-dev` skeleton (`-w` denied), and the two new
  root-only roots `/etc/lilith-recovery-witness` and
  `/var/lib/lilith-authority-custody` (`-r -w -x` denied on the first
  root-only directory the deployer can stat; everything beneath it is
  `UNOBSERVABLE_BY_DESIGN`, like the K-ACT blob);
- the maturity rule unchanged in kind: derived only from root-owned objects
  the ceremony steps create; no marker (PC-6);
- a decision on the transient upgrade names: the proof refuses
  `.<sha>.staging` in `releases/` (PF-17). That is fail-closed availability
  loss for a routine deployment that runs mid-upgrade. **Rule (SOURCE DETAIL):** keep
  the refusal, and require that no routine deployment runs between
  `upgrade-stage` and `upgrade-retire-old` (owner freeze on merges to `main`).

Classification: both are **PR-1 SOURCE BLOCKERS** (§31 S-13, S-14). They are
control-only changes (`scripts/`), never release payload, and need no
reinstall of the authority release (N-45 provenance rule).

```text
broker preservation proof != authority proof
routine deployer proof    != owner authority
```

## 10. Live RecoveryWitnessV2 — what exists

| Question | Answer | Basis |
| --- | --- | --- |
| live recovery-witness service source | **absent** | PF-14 |
| service account | **absent** live; no installer contract | B-20; installer `DISTINCT_PRINCIPALS` omits it |
| K-WIT private credential source (keygen form) | **absent**; `witness` is refused | PF-9 |
| append-only chain storage (live) | **absent**; only the TEST `DurableWitnessV2WriterV1` over a storage port and a temp-directory adapter | PF-13; Prep A §1 |
| live `witness.json` | **absent** | B-19 |
| installer | **absent** | PF-14 |
| schema capability | V2 contracts exist (pure); the TEST writer is `environment=test` only; the B1b-3d §10 service design is **V1** (`RAISE_REGISTRY_FLOOR`, V1 `ADVANCE_EPOCH`) and is superseded by RR-18 | Prep A U-9; gate GC-4 |
| real K-WIT ever generated | **no** | closure §6 |

**Consequence.** PR-1B cannot start until PR-1S delivers a DEV_SYNTHETIC V2
witness service (§31 S-5 … S-8). This is why PR-1 is split (§5).

Witness design points that are already fixed and carry over unchanged:
identity `lilith-recovery-witness` (T-1 analogue, B1b-3d §6); K-WIT keyId
`test-only.witness.dev-synthetic.b1b3d.1` (B1b-3d §4; exact spelling checked
against the B1a validator in PR-1S); credential name
`recovery-witness-signing-key`; state `/var/lib/lilith-recovery-witness/`
(`lilith-recovery-witness:lilith-authority-dev 0750`, chain `chain/<v>.json`,
pointer `witness.json`, retained authorizations `authorizations/`); signer
socket (`RECORD_LEDGER_ADVANCE`, `READ_WITNESS`; peer uid =
`lilith-authority-dev`) and root owner socket; RR-9 commit order and recovery
scan exactly as Prep A implements them; single instance and `flock`.

Owner ops for V2: `BOOTSTRAP` (V2 genesis only, from `UNINITIALIZED`). The
V2 head-advance and epoch-advance execution ops are needed by the B1b-3e
rehearsal, not by PR-1B. **RR-37 (OWNER-ACCEPTED, with inertness):** PR-1S
ships them, TEST-proven, so the accepted host needs no further source-release
upgrade merely to begin the B1b-3e rehearsal. `installed code != enabled
mutation`:

- PR-1 never executes a registry-head or RecoveryEpoch transition;
- both ops stay fail closed at runtime: they require a K-ROOT-verified
  `RegistryHeadAdvanceAuthorizationV1` / `EpochAdvanceAuthorizationV1` bound
  to the current head, a registered retained copy (RR-20a), the owner pin, a
  CONSISTENT chain, the governing hold of the matching ceremony kind, the
  root owner socket, and `environment=dev`;
- no transition authorization exists or is manufactured by installation;
  PR-3's authorization register stays empty through PR-1;
- PR-1 uses only `BOOTSTRAP` (V2 genesis), `READ_WITNESS`, and
  `RECORD_LEDGER_ADVANCE`;
- PR-1 evidence for the transition ops is the TEST proof and their presence
  in the reviewed manifest. PR-1 does not invoke them live.

## 11. K-WIT custody

Fixed by accepted records (B1b-3d §4, §6, §9, §10, §17 B4):

- a distinct Unix identity `lilith-recovery-witness`, nologin, no home, no
  sudo, never sharing a uid or gid with `lilith`, `lilith-memory-broker`,
  `lilith-memory-relay`, or `lilith-authority-dev`;
- a distinct Ed25519 private key, generated on-host by the fixed keygen,
  encrypted `--with-key=host` under the name `recovery-witness-signing-key`,
  and loaded only by `lilith-recovery-witness.service` through
  `LoadCredentialEncrypted=`. The embedded name prevents it from loading in
  the signer's `owner-actor-signing-key` slot;
- it signs **only** `RecoveryWitnessV2` (`LILITH_RECOVERY_WITNESS_V2\0`); no
  generic signing interface; no registry, OwnerEvidence, Privacy, or
  authorization signing; `WITNESS_KEY_IS_AUTHORITY_KEY` if it appears as an
  authority key;
- root-controlled installation; the signer, the broker, `lilith`, and the
  routine deployer are denied the blob and the runtime credential (B4, N1,
  N3, D1–D9);
- no key sharing with K-ACT or K-ROOT; no backup (B1b-3d §16).

Not fixed by any accepted record, and conflicting with Prep A:

- **the K-WIT blob location** (PC-1). **RR-36 (OWNER-ACCEPTED):** K-WIT
  custody is separate from K-ACT custody. The blob **must not** be placed in
  `/etc/credstore.encrypted`, which stays constrained to the single K-ACT
  CURRENT blob. It lives in a dedicated root-only RecoveryWitness credential
  source boundary, `/etc/lilith-recovery-witness/credentials/`:
  - directory `root:root 0700` (its parent `/etc/lilith-recovery-witness`
    root-owned; parent mode SOURCE DETAIL); no symlinks;
  - exactly one expected blob, a `root:root 0600` regular file, encrypted
    `--with-key=host` under the already-accepted runtime credential name
    `recovery-witness-signing-key` for the already-accepted keyId. The
    filename is SOURCE DETAIL (the B1b-3d §15 basename
    `lilith-recovery-witness.witness.cred` is the natural choice); the
    credential name gets no second meaning;
  - referenced only by the witness unit's single
    `LoadCredentialEncrypted=recovery-witness-signing-key:<that path>`; the
    K-WIT service obtains plaintext only through that systemd credential;
  - denied to the routine deployer, the broker, and the K-ACT signer (the
    signer unit adds the directory to `InaccessiblePaths`; SOURCE CHANGE
    REQUIRED);
  - protected by the existing systemd host credential mechanism (T-2). The
    whole-host snapshot limitation is unchanged: a disk snapshot holds both
    the blob and `credential.secret`.

  The Prep A "credstore = exactly CURRENT" invariant is untouched. The old
  credstore K-WIT path stays a must-be-absent path in the installer and
  broker observations.
- **the keygen form** for K-WIT: a closed `witness` form writing only that
  location, refusing if it is non-empty, printing only its public
  publication. SOURCE CHANGE REQUIRED (S-6).

K-WIT is distinct from K-ACT, K-ROOT, the B1c activation key, and the owner
WebAuthn credential, and signs only `RecoveryWitnessV2`.

Distinctness evidence (owner package §19): K-WIT public fingerprint ≠ K-ACT
fingerprint; K-WIT keyId ∉ registry v1; K-WIT blob SHA-256 ≠ K-ACT blob
SHA-256; the witness anchor names K-WIT and nothing else.

## 12. Live V2 genesis bootstrap

The genesis is the output of the witness owner op `BOOTSTRAP`, from
`UNINITIALIZED` only, signed by K-WIT. It binds (Prep A §4):

| Field | Value source | Owner-derivable offline? |
| --- | --- | --- |
| `environment` | `dev` | yes |
| `registryVersion`, `registryDigest` | registry v1, signed offline by K-ROOT | yes (the owner signed it) |
| `currentRecoveryEpoch` | E0 as named in registry v1 | yes |
| `policyVersion` | registry v1 | yes |
| `ledgerSequence`, `ledgerHead` | the authority recovery ledger after its `GENESIS` op: `1`, `sha256(LILITH_AUTHORITY_LEDGER_HEAD_V1\0 ‖ 0^32 ‖ JCS(genesis op))` | **yes**, if the live ledger reproduces the model's head function and genesis op exactly (PF-11; S-9) |
| `witnessVersion` | `1` | yes |
| `previousWitnessDigest` | `null` | yes |
| `consumedAuthorizationId` | `null` (no authorization is invented or consumed) | yes |
| `witnessKeyId` | the fixed K-WIT keyId | yes |
| `updatedAt` | chosen once, by the owner, for the candidate | yes |

Preconditions before the genesis may be committed:

1. registry v1 verifies under the installed `TrustedRegistryRootV1` at its
   own epoch, `test-only.` root key ID, `environment=dev`;
2. registry v1 satisfies the single-current-key rule, with K-ACT the only
   current OWNER_ACTOR key, and its record equals the K-ACT publication
   (`publicKey`, keyId, domain, evidence type);
3. the loaded-key binding is **reproducible** for K-ACT: B1 (registry) = B3
   (publication) = B2 (CURRENT blob hash), with B5/B6 (unit directive,
   inventory). B4 (HEALTH) cannot exist yet (the signer has not started); it
   is required later, at eligibility (§18);
4. the credential inventory verifies in phase `STEADY` (credstore = CURRENT
   only; `prepared/`, `retired/` empty);
5. the ledger exists at exactly sequence 1 with the expected head, and its
   schema fingerprint verifies;
6. K-WIT custody verifies (§11) and the installed `TrustedWitnessAnchorV1`
   names the K-WIT public key from its publication;
7. the witness store is `UNINITIALIZED`: no chain, pointer, scratch, or
   retained authorization;
8. the owner pin equals the candidate digest (RR-35 step 4, §13), and after
   the commit the committed digest equals the pin (step 7).

Durability (inherited, Prep A §8): create `chain/1.json` `O_EXCL`, fsync the
file, fsync `chain/` (**commit point**), write and fsync the tmp pointer,
rename to `witness.json`, fsync the state directory, then reply. An
interrupted bootstrap before the commit point stays `UNINITIALIZED`.

## 13. Owner genesis pin dependency (RR-35, OWNER-ACCEPTED)

**Accepted ordering: PIN-BEFORE-COMMIT.** After the exact initial ledger
position, registry head, RecoveryEpoch, `policyVersion`, and every other
deterministic genesis field are established (§12):

1. construct the exact unsigned `RecoveryWitnessV2` genesis candidate;
2. compute its canonical genesis digest (`witness_v2_digest`, which excludes
   the K-WIT signature, PF-12);
3. the owner independently reproduces that digest off-host from owner-held
   inputs and stores it as `OwnerGenesisPinV1` (PR-3);
4. on-host verification proves the owner pin equals the candidate digest;
5. K-WIT signs **that exact candidate** (the witness `BOOTSTRAP` refuses any
   other unsigned body);
6. the signed genesis is committed durably (§12 durability);
7. the committed genesis digest is re-verified equal to the owner pin.

If the committed genesis differs from the pinned candidate: **STOP.** No
second genesis is ever created silently (RR-40). The rejected alternative
(commit, then pin) would copy the pin from the host it anchors and leave a
window with no pin input.

```text
owner pin != K-WIT signature
owner pin != K-ROOT authority
owner pin != external monotonic current-head anchoring
```

| Item | Owner | PR |
| --- | --- | --- |
| candidate construction and digest, host side (read-only) | PR-1B tooling (S-7) | PR-1 |
| digest reproduction, owner side (offline) | owner workstation tooling (S-11) | PR-1 source; PR-3 material |
| off-host storage of the pin | the owner | **PR-3 foundation** (before commit) |
| on-host copy of the pin (root-owned input for witness recovery and the verifier) | host root | PR-1B |
| pin verification before signing (step 4) and after commit (step 7) | witness `BOOTSTRAP`; witness recovery; the root verifier; the owner's off-host reproduction | PR-1 |
| release-eligibility input | the verified pin, checked equal to the owner's off-host record | PR-1 (check), PR-3 (reference value) |

PR-1 never manufactures PR-3 evidence: the on-host copy counts only when its
digest equals the owner's off-host record (Prep A §7.2 rule 4 applied to the
pin).

## 14. Authority ledger live gap

**Confirmed.** The L1 signer has no ledger (PF-1). No durable ledger source
exists (PF-13). The accepted path is
`/var/lib/lilith-authority-dev/authority_ledger.db` (B1b-3d §12; B1b-3e §4).

| Aspect | Design |
| --- | --- |
| path | `/var/lib/lilith-authority-dev/authority_ledger.db` (+ WAL/SHM) |
| owner | `lilith-authority-dev`, sole writer (gate §9); file `0600`, directory `0700` (`StateDirectoryMode=0700`) |
| schema / source | B1b-3d §12 tables (`authority_meta_v1`, `authority_journal_v1`, `authority_epoch_v1`, `authority_challenge_v2`, `authority_evidence_v2`, `authority_evidence_use_v1`), WAL, `synchronous=FULL`, exact schema fingerprint. The journal must be the durable form of `AuthorityLedgerStateV1`: same ops, same head function, same refusals. **SOURCE CHANGE REQUIRED** (S-9); the model lives in the TEST package and cannot ship (PF-13) |
| initialization rules | no auto-initialisation: a missing ledger is `AUTHORITY_STATE_MISSING`. One explicit owner provisioning step, run by a fixed release CLI as the signer uid (`runuser`, as the L1b.1 import check), creates the directory `0700`, the DB, and exactly one `GENESIS` op from registry v1: `{environment: dev, recoveryEpoch: E0, policyVersion, registryVersion: 1, signingKeyIds: [K-ACT]}`; refuses if the file or directory exists |
| permissions | signer read/write; witness none (B4); root read-only for forensics with the service stopped; `lilith`, broker, deployer none |
| is initialization an authority mutation? | **no.** It records a position, and the registry it copies is already K-ROOT's. It is rollback-sensitive only once the genesis binds its head |
| migration from absent | none: absent → sequence 1. There is no sequence-0 file state. `"0"*64` is the pre-genesis head constant only |
| empty/initial head | `ledgerSequence = 1`, `ledgerHead = H(0^32, genesis op)`; deterministic, no timestamp, so the owner can recompute it (§12) |
| genesis before ledger? | **no.** `plan_witness_v2_genesis` needs `ledgerSequence ≥ 1` (PF-11). The ledger is provisioned first (PC-2) |
| first signer start | journals nothing. The genesis op already binds the registry v1 view, so the head stays at the genesis position and both HELD and RELEASED can bind the genesis entry (SOURCE DETAIL; S-10) |
| C-4 use | `ADVANCE_EPOCH`, `VOID_CHALLENGE`, `QUARANTINE_USE` exist in the op set, reachable only through the gated recovery handler (§15). Never exercised live in PR-1 |

> **Erratum (2026-10-07, M-B6 remediation D-3; the table above is unchanged).** The provisioning code does not
> refuse every existing directory: `ledger_tool.prepare_state_directory` adopts an exact, empty, signer-owned
> `0700` `/var/lib/lilith-authority-dev` unchanged (`ADOPTED_NO_MUTATION`) and refuses only an unsafe directory
> (`LEDGER_TOOL_STATE_DIRECTORY_UNSAFE`) or any existing ledger file or `-wal` / `-shm` / `-journal` sidecar
> (`LEDGER_TOOL_ALREADY_PROVISIONED`). See the [M-B6 remediation record](slice-15b2b-b1b3e-mb6-ledger-remediation.md) §11.

## 15. Narrow C-4 gate wiring

PR-1 must wire `evaluate_recovery_gate` into the runtime (Source Prep B §12).
Design only:

| Topic | Design |
| --- | --- |
| dispatch boundary | the signer's closed owner-socket protocol (`protocol.py`) gains exactly three operations: `RECOVERY_ADVANCE_EPOCH`, `RECOVERY_VOID_CHALLENGE`, `RECOVERY_QUARANTINE_USE`. Root peer only (`SO_PEERCRED uid 0`), one frame, as today. No other new operation |
| operations callable | only the three ledger ops of the gate allowlist. `ISSUE`, `PREPARE`, `CONSUME`, `RESERVE`, `CONFIRM`, `ABANDON`, `REGISTRY_VIEW`, every signing request, admin, and unknown values are refused before any state is read |
| normal signing impossible | the recovery handler module imports no minter (test-enforced, like today's "no authority-dev module imports the gate"). The minter is constructed only on the `FULL_READINESS` path, which is unwired in PR-1 if RR-39 is accepted |
| compromised K-ACT loaded for C-4 | the C-4 ops are **ledger journal writes, not signatures**. P stays loaded only because systemd delivers it and the signer refuses to start without it (PF-3). The key object is never retained (PF-2), so no code path in the handler can reach private material |
| operation context | the request carries only the operation name and, for `RECOVERY_ADVANCE_EPOCH`, the exact signed `EpochAdvanceAuthorizationV1` bytes. Everything else, except the root-produced hold-store observation below, the signer reads **itself**, from fixed paths, never from the caller: the witness (chain from genesis, via `ReadOnlyPaths`), head registries, anchors, the on-host pin and register copies, and its own ledger |
| HELD verification | the hold store is `root:root 0700` (RR-34), so the signer **cannot read it** and cannot observe its completeness, exactly as it cannot observe the credential inventory (PC-7). The root owner-socket request therefore carries the **complete** `HoldStoreObservationV1` produced by the fixed root hold observer (§17), with its listing digest. The handler accepts no single hold record; it re-judges the whole set with the same `parse_hold_store` / `governing_hold_reason` rules readiness uses and passes only the governing record to the gate. Completeness remains a root-observation property (story 4), produced by the store's owner, never by an arbitrary caller. Closes PF-15 (single-record input) |
| expected epoch authorization | K-ROOT signature, `KEY_COMPROMISE`, bound to the current witness digest/version/epoch, unconsumed in the chain; and `ledger_observation` is **mandatory** in the runtime path (PF-15: optional in the pure API), so `ADOPTION_ALREADY_JOURNALLED` is always checked |
| refusal of everything else | any gate result other than `RECOVERY_GATE_PERMITTED` returns only the closed reason; a permitted result performs exactly the named ledger op in one transaction, then `RECORD_LEDGER_ADVANCE` (B1b-3d §10 ordering). No other side effect |

Classification: **PR-1 SOURCE BLOCKER** (S-10). The live PR-1 never exercises
C-4 (no compromise exists); acceptance is TEST evidence plus the live
refusal of the three ops outside `KEY_COMPROMISE_RECOVERY` (they must return
`HOLD_NOT_COMPROMISE_RECOVERY` under INITIAL_CUSTODY).

## 16. Live hold-store location (RR-34, OWNER-ACCEPTED)

**Accepted path:** `/var/lib/lilith-authority-custody/holds/`.

Holds are mutable, forward-only local readiness/custody state, not static
configuration, so they live under `/var/lib`, not `/etc`. Persistence is
owned by **host root through the fixed root ceremony tooling** (gate §9:
"ceremony hold — owner host root; may mutate host root"). The authority
signer is a consumer, never the owner. The hold store is not
authority-bearing.

| Requirement | Rule |
| --- | --- |
| parent | `/var/lib/lilith-authority-custody`, root-owned, not a symlink, no other entries than `holds` (mode SOURCE DETAIL; `0700` keeps everything beneath unobservable by non-root) |
| hold directory | `root:root 0700`, not a symlink, no subdirectories |
| records | `root:root 0600` regular files named `<sha256(ceremonyId)>.json`, RFC 8785 bytes |
| writer | the fixed root hold CLI only (S-11) |
| signer | cannot read or rewrite (mode; plus `InaccessiblePaths` in the signer unit as defence in depth, SOURCE DETAIL). It consumes only the root-produced complete observation (§15) |
| broker, routine deployer, `lilith` | denied (mode; proven non-vacuously on the first directory they can stat, §9) |
| unexpected content | any unexpected entry, name, type, or symlink fails the whole store closed |
| completeness | provable by the root observer (§17) |

`/var/lib/lilith-authority-custody` (hold state) and `/etc/lilith-authority-custody`
(credential custody slots, RR-26) are **different roots with similar names**.
Tooling, proofs, and records always use the full path; neither is ever
inferred from the other.

The draft's alternatives (the signer state dir, the credential custody root,
`/etc/lilith-authority-dev/holds/`, another state root) are closed by this
decision.

## 17. Hold-store completeness proof

| Property | Design |
| --- | --- |
| exact directory | `/var/lib/lilith-authority-custody/holds/`; opened `O_DIRECTORY\|O_NOFOLLOW`; every later operation through that descriptor (`openat`, `fstatat` with `AT_SYMLINK_NOFOLLOW`) |
| ownership / mode | directory `root:root 0700`, not a symlink, inside a root-owned parent holding only `holds`; every record `root:root 0600` regular file |
| no nested namespace | zero subdirectories; any non-regular entry fails the whole store closed |
| no ignored filename classes | **every** directory entry is judged: no dot-file, backup, editor, or temp exemption. Only `^[0-9a-f]{64}\.json$` names are admitted; anything else is `HOLD_STORE_ENTRY_INVALID` |
| deterministic naming | `sha256(ceremonyId).json`; the name is re-derived from the parsed record (`HOLD_STORE_NAME_MISMATCH`); duplicates fail (`HOLD_SET_CEREMONY_DUPLICATED`) |
| symlink refusal | `O_NOFOLLOW` on every open; `lstat` type check |
| atomic / read-consistent | the root writer and every observer take `flock` on the **directory descriptor** (no lock file inside the store, which would be an unexpected entry). The observer records the directory's `(st_ino, st_mtime_ns, st_ctime_ns)` before and after the listing and fails on any change. The writer publishes a record by tmp **outside** the store → fsync → `rename` into the store → fsync the store directory |
| digest / listing evidence | `HoldStoreObservationV1` plus a listing digest: SHA-256 of the JCS list of `(name, sha256(bytes))`, sorted by name. Every eligibility and readiness result names that digest |
| forward-only | the writer checks `hold_store_transition_reason(previous, proposed)` before every write: no record disappears, new ceremonies start `HELD`, `RELEASED` never returns to `HELD`. A forged or reverted record by host root is Level 3 (DR-3) |
| observer | the fixed root observer only (inside the root verifier and the root hold CLI). The signer never observes the store; it receives the complete root observation (§15) |

```text
complete observation            != authority
caller-selected subset          != complete hold state
directory listing digest equal  != records valid  (every record is still parsed and bound)
```

## 18. INITIAL_CUSTODY live flow

RR-30 lifecycle, bound live (Source Prep B §8):

```text
missing -> INITIAL_CUSTODY / HELD -> HOLD_RELEASE_ELIGIBILITY -> explicit owner acceptance
        -> INITIAL_CUSTODY / RELEASED -> FULL_READINESS
```

| Field (HELD) | Live value |
| --- | --- |
| `environment` | `dev` |
| `ceremonyId` | `dev.initial-custody.test-only.dev-synthetic.actor.b1b3d.1` (deterministic; Source Prep B §8) |
| `transitionKind` | `INITIAL_CUSTODY` |
| `state`, `reason` | `HELD`, `INITIAL_CUSTODY_BOOTSTRAP` |
| `expectedPredecessorKeyId` | `null` |
| `expectedSuccessorKeyId` | `test-only.dev-synthetic.actor.b1b3d.1` (the existing K-ACT; no new material) |
| `observedWitnessDigest` | the committed V2 genesis digest, equal to the owner pin |

- **No grandfathering.** The B1b-3d credential's existence never becomes a
  release. Missing, malformed, or unknown holds fail closed.
- **HELD placement.** HELD is written after the genesis commit and its pin
  re-verification (RR-35 step 7), and **before** the signer's first start.
- **No re-bootstrap (RR-40, OWNER-ACCEPTED).** Once HELD is durably created:
  it is never deleted or recreated; no other genesis is created; the
  bootstrap ceremony is never silently reset; the deterministic initial
  ceremony ID is never reused for different state. If eligibility fails on
  a recoverable observation/readiness condition (unit mapping, inventory,
  HEALTH, ledger view, a proof), the **same** HELD ceremony is re-evaluated
  after the condition is corrected: that is retry, not re-bootstrap. If the
  accepted genesis, the initial ceremony identity, or the HELD lineage itself
  is wrong after HELD exists: **STOP**; a separate reviewed recovery design is
  required. There is no automatic bootstrap reset.
- **Eligibility** is a read-only evaluation by the root verifier in
  `HOLD_RELEASE_ELIGIBILITY` mode. It needs B4 (HEALTH), so the signer must
  be running (not enabled).
- **RELEASED is never automatic.** It is written only by the fixed root hold
  CLI, and only when the owner supplies the **canonical acceptance-package
  digest they approved** (RR-38, §19). The CLI re-runs the root verifier,
  rebuilds the package, and refuses unless its digest is identical. This
  binds the owner's decision to the exact state reviewed. It is not
  authority.
- **RELEASED** binds `OWNER_RELEASE_AFTER_ELIGIBILITY` and an
  `observedWitnessDigest` with the **genesis registry head** (the genesis
  itself, or a later ledger-only entry).
- **FULL_READINESS** is then re-run. It never implies the release; the
  release never implies readiness.

The owner acceptance is separate from, and never inferred from: installer
success, service health, genesis creation, eligibility PASS, or test
success.

## 19. Owner acceptance evidence package

Presented before the owner may authorize `HELD → RELEASED`. Each item names
the PR that owns it. **Every item is required.**

| # | Evidence | PR |
| --- | --- | --- |
| E-1 | installed release: RELEASE_SHA, archive + attestation SHA-256, manifest SHA-256, full tree check, venv file-set digest, CONTROL_SHA of the tooling (§23) | PR-1 |
| E-2 | K-ACT keyId, public key, `publicKeySha256` (from the owner-retained publication, B3) | PR-1 (B3 bytes); PR-3 (owner copy) |
| E-3 | HEALTH `publicKeySha256` (B4) equal to E-2 | PR-1 |
| E-4 | CURRENT blob SHA-256 `6a61c350…` and identity tuple unchanged since closure (§24) | PR-1 |
| E-5 | credential inventory `STEADY` (credstore = CURRENT only; PREPARED/RETIRED empty); listing digest | PR-1 |
| E-6 | unit credential mapping (B5): exactly one `LoadCredentialEncrypted=owner-actor-signing-key:<CURRENT>`; unit bytes = release asset; `NeedDaemonReload=no` | PR-1 |
| E-7 | authority service denial of PREPARED/RETIRED: unit property + mount-namespace probe | PR-1 |
| E-8 | routine deployer denial: DR-5 PASS on a real routine deployment with every PR-1 path existing (non-vacuous) | PR-1 |
| E-9 | broker denial (root probes as `lilith-memory-broker`) and `BROKER_PRESERVATION=PASS` with the accepted incarnation and candidate | PR-1 |
| E-10 | K-WIT keyId, public fingerprint, blob SHA-256; distinctness from K-ACT and K-ROOT; anchor equality | PR-1; PR-3 records the fingerprint |
| E-11 | V2 genesis digest; chain = `[1.json]` (or genesis + ledger-only entries); pointer = head; recovery `CONSISTENT` | PR-1 |
| E-12 | owner genesis pin equals E-11; on-host copy digest equals the off-host record | PR-3 (pin); PR-1 (comparison) |
| E-13 | K-ROOT registry v1: version, digest, root key ID, epoch E0, policy version; equal to the register's head entry | PR-1 (installed bytes); PR-3 (register) |
| E-14 | RecoveryEpoch E0 (counter, random, digest) | PR-1 |
| E-15 | authority ledger: sequence, head, schema fingerprint; equal to the genesis binding | PR-1 |
| E-16 | complete hold-store observation: listing digest; exactly one record, INITIAL_CUSTODY HELD bound to E-11 | PR-1 |
| E-17 | `HOLD_RELEASE_ELIGIBILITY` = READY by the on-host root verifier: every check PASS, with `CEREMONY_HOLD` passing as a bound INITIAL_CUSTODY HELD record; the readiness digest | PR-1 |
| E-18 | the owner's off-host reproduction (RR-38 B) of the relevant digests, registry, genesis pin, identities, and package content, from off-host material; equal to E-17 | PR-1 tooling; PR-3 inputs |
| E-19 | `ACTIVATION=NOT_ACCEPTED reason=GRANT_ABSENT`; B1c helper, library, verifier, sudoers unchanged | PR-1 |
| E-20 | snapshot inventory: accepted record; every K-ACT, K-WIT, and host-key artefact `SAFE_RETAINED_CIPHERTEXT` or bounded, documented `KNOWN_CUSTODY_DEBT`; named debts | **PR-2** |
| E-21 | off-host register status: exists; holds the K-ROOT public fingerprint, registry v1 head, genesis pin, K-WIT fingerprint, release provenance, the (empty) authorization-ID list, and the (empty) burned-ordinal register | **PR-3** |
| E-22 | secret hygiene: journal, transcript, and publication scans clean for every PR-1B credential ceremony | PR-1 |
| E-23 | preservation set (B1b-3d §23) unchanged: Stage III, broker, API unit | PR-1 |
| E-24 | explicit nonclaims (§36), including `wholeHostRollbackProtected: false` | PR-1 |

**PR-2 and PR-3 are both required before release** (E-20, E-21, E-12).

**Two reproductions (RR-38, OWNER-ACCEPTED).**

- **A. On-host root verifier.** Produces the complete canonical evidence
  package (E-1 … E-24 as structured data, RFC 8785) and the
  `HOLD_RELEASE_ELIGIBILITY` result. The package has one canonical digest:
  SHA-256 over its JCS bytes, domain-separated (exact separator SOURCE
  DETAIL).
- **B. Owner off-host verification.** The owner independently verifies and
  reproduces, from off-host material (the register, the pin, the K-ACT
  publication, registry v1 bytes, K-ROOT and K-WIT public keys, release
  provenance), the digests, the registry, the genesis pin, the identities,
  and the package content, and recomputes the package digest.
- The owner may release INITIAL_CUSTODY only when the exact package digest
  being approved equals the digest of a **current re-run** (§18). No
  screenshot and no unstructured human comparison counts.

```text
on-host PASS != owner acceptance
```

## 20. PR-2 / PR-3 dependency order (OWNER-ACCEPTED)

```text
PR-1S
 -> PR-1A inert install
 -> PR-2 snapshot inventory
 -> PR-3 foundation
 -> authority-ledger bootstrap
 -> exact V2 genesis candidate
 -> owner candidate-digest pin
 -> K-WIT signed genesis commit
 -> INITIAL_CUSTODY / HELD
 -> HOLD_RELEASE_ELIGIBILITY
 -> PR-3 full acceptance / register material
 -> explicit owner acceptance
 -> RELEASED
 -> FULL_READINESS
```

The steps this order implies but does not name are placed where their
inputs require them (§28): K-ROOT generation, K-WIT keygen, registry v1
signing, and the anchor and registry installs come after PR-2 and PR-3
foundation and before the ledger bootstrap (the ledger's genesis op copies
registry v1, PF-11); the witness start precedes the genesis commit; the
signer's first start (for B4) follows HELD and precedes eligibility.

| Question | Answer | Why |
| --- | --- | --- |
| may PR-2 follow PR-1A? | **yes, with an explicit nonclaim** (PR-1A makes no custody claim) | PR-1A creates no credential |
| what must PR-2 precede? | **real K-WIT credential generation**, and the **initial authority registry publication/signing** for this bootstrap | K-ACT is `NOT_IN_HEAD` today. If PR-2 finds it exposed, RR-7 says it "must never be published", and RR-20b requires fresh custody material. A K-WIT created under a possibly exposed host key would be contaminated |
| must PR-2 precede RELEASED? | **yes** (E-20) | the gate's entry rule applied to initial custody |
| what must PR-3 foundation precede? | the **V2 genesis commit** (the pin is stored before commit, RR-35) | |
| what must PR-3 full material precede? | **INITIAL_CUSTODY RELEASED** (E-12, E-21) | |
| the first live K-ROOT authorization? | PR-1 issues **none**: genesis consumes none (gate §14 is satisfied vacuously within PR-1) | |

**PR-1B cannot complete until PR-2 and PR-3 are satisfied.**

## 21. Snapshot inventory interaction

PR-2 is not performed here. Its findings map to RR-7 (gate §5.2, §5.6) and
to PR-1 continuation:

| Finding | RR-7 class | PR-1A | PR-1B / release |
| --- | --- | --- | --- |
| no snapshots, machine images, or snapshot schedules (complete provider listing) | none | proceed | proceed |
| snapshot with the encrypted blob only | `SAFE_RETAINED_CIPHERTEXT` if the class-6 conditions hold, else `UNKNOWN_PROVENANCE` | proceed | SAFE: proceed. UNKNOWN: **DO NOT PROCEED** |
| snapshot with `credential.secret` only (for example taken between L2a and L2b.2) | not a K-ACT artefact by itself, but it **reclassifies every ciphertext under that host key**, including a future K-WIT blob (class-6 condition) | proceed | only if inside an accepted, inventoried environment (bounded debt); otherwise treat the host key as exposed: **DO NOT PROCEED** (RR-20b) |
| snapshot with blob + `credential.secret` inside an accepted, inventoried environment | at least `KNOWN_CUSTODY_DEBT` | proceed | **ALLOWED WITH EXPLICIT NONCLAIM**: debt named in the acceptance record |
| the same outside the accepted boundary | `EXPOSED_PRIVATE_MATERIAL` | proceed (no custody claim) | **DO NOT PROCEED**; K-ACT never published; re-custody with fresh material (RR-20b) before registry v1 |
| unknown access history | `UNKNOWN_PROVENANCE` (treated as exposure) | proceed | **DO NOT PROCEED** unless an owner record proves a lower class |
| snapshot outside the accepted project/account | with both halves `EXPOSED_PRIVATE_MATERIAL`; ciphertext only `UNKNOWN_PROVENANCE` | proceed | **DO NOT PROCEED** |
| the host itself was restored from a stale snapshot | before PR-1B: detectable only as a baseline mismatch (§7.2) → STOP. After V2 genesis: whole-host rollback, **not detected** | STOP on mismatch | nonclaim; STOP on any detected mismatch |

PR-1A precedes PR-2 in the accepted order and may proceed under bounded
`KNOWN_CUSTODY_DEBT` or with PR-2 incomplete, with an explicit nonclaim,
because it asserts nothing about custody. INITIAL_CUSTODY
release may proceed only when every artefact is `SAFE_RETAINED_CIPHERTEXT`
or bounded, documented `KNOWN_CUSTODY_DEBT`.

## 22. Owner off-host register / material

PR-3 provides to PR-1 (Prep A §7.1, gate §6.8, Source Prep B §4):

| Item | Role |
| --- | --- |
| `OwnerGenesisPinV1` | the reference genesis digest (RR-21); a distinct input, not a register row (Prep A U-5) |
| `OwnerAuthorizationRegisterV1.authorizations` | foundation: empty at PR-1 (genesis consumes nothing); must exist so the first later authorization is registered |
| `OwnerAuthorizationRegisterV1.headRegistries` | `(1, digest(registry v1))` |
| full signed bytes of registry v1 | retained off-host (gate §6.8 item 1) |
| K-ROOT public key fingerprint and root key ID | provenance: which root the owner holds |
| K-WIT public identity / fingerprint | provenance for the anchor the owner accepts |
| K-ACT publication bytes and digest | the B3 reference (E-2) |
| installed release provenance | RELEASE_SHA, archive/attestation/manifest SHA-256 |
| `SuccessorCeremonyRegisterV1` | foundation: empty (no successor exists) |
| the acceptance record digest | what the owner accepted, at which readiness digest |

Separation:

```text
owner record / provenance  != K-ROOT authority
register entry             != authorization
pin                        != K-ROOT, != K-WIT
```

PR-3 holds records and references. It signs nothing, and nothing verifies
under it as a root. K-ROOT generation and registry signing are PR-1B
owner-workstation steps; PR-3 only records their public results. PR-3 must
never become a second authority root.

## 23. Installed release evidence

Independent evidence that the installed release is the reviewed PR-1S
release. None of it is "git HEAD" or "installer succeeded".

| Evidence | Who observes | Proves |
| --- | --- | --- |
| reproducible archive: two independent owner-workstation builds from clean `<RELEASE_SHA>` give the same `archiveSha256` | owner | the archive is a function of the reviewed commit |
| attestation and manifest verify (`verify_archive`) | installer, root | the staged bytes are the archive |
| full tree check: every manifest file's bytes equal; no extra file outside `venv/`; ownership and modes | root verifier (S-2/S-12) | the installed tree is the manifest |
| venv file-set digest recorded at install and re-verified at every later phase | root verifier | drift detection only (the venv is built on-host) |
| unit, socket, tmpfiles, CLI bytes equal to the release copies (`UNIT_BYTES`, `CLI_BYTES`) | installer `status` | host-installed copies are the release's |
| `release_file_set.runtime_manifest` digest equal to the reviewed value | owner, from source | the runtime payload is the reviewed source |
| `current -> releases/<RELEASE_SHA>`; `releases/` = exactly that entry | installer `status` | the selected release (RR-25) |
| running processes (PR-1B): `/proc/<pid>/cwd` → `releases/<RELEASE_SHA>`; `exe` in its venv; `InvocationID` and `ExecMainStartTimestamp` after the last `daemon-reload`; `NeedDaemonReload=no` | root verifier | the process runs the installed release under the current unit definition |

## 24. CURRENT credential preservation

Pre and post **every** PR-1A stage and every PR-1B phase:

| Fact | Expected |
| --- | --- |
| path | `/etc/credstore.encrypted/lilith-authority-dev.owner-actor.cred` |
| type | regular file, not a symlink (`lstat`) |
| owner / mode | `root:root 0600` |
| identity | `st_dev`, `st_ino`, `st_size` equal to the first PR-1 preflight's values, which the owner records |
| times | `st_mtime_ns` and `st_ctime_ns` unchanged (a chmod, chown, or rewrite changes `ctime`) |
| content | SHA-256 = `6a61c350e848a833868f4573982fca9c75e2af79ccc9bd3716ae0303c26973f3`, read as ciphertext by root. **Never decrypted** |
| credstore | exactly one entry, this name |
| publication relation | `blobSha256` of the owner-retained publication = the observed SHA-256 (B2 = B3) |
| HEALTH relation | from PR-1B P1B-10 on: HEALTH `publicKeySha256` = publication `publicKeySha256` (B4 = B3); closes L2 U5 |

Any difference is a STOP. PR-1A fails if the blob changes.

## 25. Authority-dev service state

| | A. stopped through PR-1A | B. restart after inert install for HEALTH | C. start only in PR-1B, after genesis and HELD |
| --- | --- | --- | --- |
| signer availability | none (as today) | brief | from P1B-10 |
| key loading | never | K-ACT decrypted into `/run/credentials/…` for the first time | first time, under HELD |
| issuance surface | none | none (L1 refuses everything) | none if RR-39 (issuance unwired) |
| activation | dark | dark | dark |
| HEALTH fingerprint | not available | available, but with no registry to compare | available when every other binding input exists |
| side effects | none | `StateDirectory=` creates `/var/lib/lilith-authority-dev` → installer `status` fails `UNEXPECTED_PRESENT` (PF-6). With the new unit, systemd is **expected** to refuse the start while `/etc/lilith-authority-dev`, `/var/lib/lilith-recovery-witness`, or `/etc/lilith-authority-custody` is absent (PF-16: no `-` prefix; documented systemd behaviour, not live-proven) | none unexpected |
| exposes Source Prep B paths | no | no | no (`InaccessiblePaths`) |
| rollback before an authority PONR | trivial | needs removal of the state dir | stop the units |

**Recommendation: A through PR-1A, then C.** The signer is started for the
first time in PR-1B, after the ledger, the V2 genesis, and the
INITIAL_CUSTODY HELD record exist. No owner decision is needed beyond the
existing T-5 (never enabled). The first K-ACT load is itself evidence (B4)
and belongs where it can be bound.

## 26. Activation must remain dark

Throughout PR-1: `ACTIVATION=NOT_ACCEPTED reason=GRANT_ABSENT`. PR-1 creates
no activation grant, touches no B1c helper, library, verifier, or sudoers, and
never turns signer readiness into memory acceptance. `FULL_READINESS READY`
is local issuance readiness only, and under RR-39 even issuance stays
unwired.

```text
authority signer installed != memory activation
FULL_READINESS READY       != activation grant
```

## 27. PR-1 mutation ledger

One logical transition per row. PRE always includes: the preservation set
(B1b-3d §23) re-hashed; CURRENT preservation (§24); the previous row's POST.
"Forward" means forward-only.

| ID | State owner | Responsibility | One mutation | POST | Rollback / forward | Authority | Custody | STOP if |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| M-A1 | root | stage NEW release | `releases/<NEW>` beside OLD | tree = manifest; `{OLD, NEW}` | remove NEW | none | none | archive/attestation/import check fails |
| M-A2 | root | selector | `current -> releases/<NEW>` | target | flip back | none | none | any other change |
| M-A3 | root | unit files | replace service/socket/tmpfiles | bytes = NEW assets | replace back | none | none | units active/enabled |
| M-A4 | systemd | reload | `daemon-reload` | loaded, inactive, static, `NeedDaemonReload=no` | reload after M-A3 rollback | none | none | any unit active |
| M-A5 | root | CLIs | replace keygen; create the new fixed CLIs | `CLI_BYTES` each | replace back / remove | none | none | collision on a new name |
| M-A6 | root | release set (RR-25) | remove `releases/<OLD>` | `status L2b.2 <NEW>` PASS | re-stage the reviewed OLD archive (pre-PONR) | none | none | any §6.2 fact differs |
| M-A7 | root | custody root | installer `custody` stage | custody POST (§8) | `rmdir` the three (empty) | none | structure only | not empty; `st_dev` mismatch |
| M-A8 | root | witness identity | create `lilith-recovery-witness` | account contract | `userdel` (nothing uses it) | none | none | name exists; uid/gid collision |
| M-A9 | root + systemd | witness units | install witness unit/socket/tmpfiles, then `daemon-reload` (two stages) | loaded, inactive, never enabled | remove + reload | none | none | active |
| M-A10 | root | skeleton | create, all empty: `/etc/lilith-authority-dev/{trust,registry}`; `/etc/lilith-recovery-witness/credentials/` (RR-36); `/var/lib/lilith-authority-custody/holds/` (RR-34) | owner/mode/emptiness | `rmdir` | none | structure only | not empty |
| — | routine CI | proof gate | none (a real routine deployment) | DR-5 PASS non-vacuous; broker preservation PASS | — | none | none | any FAIL |
| M-B1 | owner, off-host | K-ROOT | generate K-ROOT on the workstation | public fingerprint in the register | discard (nothing uses it) | defines the future root | none on host | key material leaves the workstation |
| M-B2 | root | K-WIT custody | keygen `witness` → K-WIT blob | publication; blob hash; scans clean; K-ACT unchanged | destroy the blob (before M-B4) | none | **custody created** | any private pattern; CURRENT changed |
| M-B3 | owner, off-host | registry v1 | build + sign registry v1 at E0, K-ACT current | digest in the register; verifies offline | discard (never installed) | **authority object created off-host** | none | succession/single-current fails; K-ACT record ≠ publication |
| M-B4 | root | trust anchors | install `registry-root.json`, `witness-anchor.json` | bytes equal owner copies | remove | none | none | anchor ≠ publication |
| M-B5 | root | registry bytes | install registry v1 (`authority-registry.v1.json`; no pointer — the witness decides the head at M-B9b) | verifies on-host under the anchor | remove (nothing binds it yet) | none on host (story 4) | none | verification fails |
| M-B6 | signer uid (via root) | ledger | provision `authority_ledger.db` at sequence 1 | sequence 1; head = owner value; fingerprint | remove (before M-B9 only) | none | none | head ≠ owner-computed |
| M-B7 | owner + root | genesis candidate | none on host (read-only construction and digest, both sides) | host digest = owner digest | — | none | none | digests differ |
| M-B8 | owner / root | pin | owner stores the pin off-host (PR-3 foundation); root installs the on-host copy | copy digest = off-host = candidate digest | remove the copy (before M-B9b) | none | none | mismatch |
| M-B9a | systemd | witness start | start the witness socket/service (not enabled) | recovery `UNINITIALIZED`; nothing written but the state dir | stop; remove the empty state dir | none | none | any other classification |
| M-B9b | witness | V2 genesis | `BOOTSTRAP` of the exact pinned candidate | chain `[1]`; pointer = head; `CONSISTENT`; committed digest re-verified = pin | **forward only** | lineage anchored | none | refusal (state unchanged); committed ≠ pin → STOP |
| M-B10 | root | hold | write INITIAL_CUSTODY HELD | store = one HELD record bound to genesis | **forward only**; never deleted or recreated (RR-40) | none | none | store not empty before |
| M-B11 | systemd | signer start | start the signer socket/service (not enabled) | HEALTH B4 = B3; `NOT_READY` with only the hold reason | stop | none | K-ACT loaded (first time) | B4 ≠ B3; any other reason |
| M-B12 | root verifier | eligibility | none (read-only): canonical evidence package + its digest | eligibility READY; package digest | — (retry of the same HELD after a correction) | none | none | not READY |
| M-B13 | owner | acceptance | off-host reproduction (RR-38 B), then the explicit decision naming the package digest, recorded off-host (PR-3 full material in place) | owner digest = package digest | — | none | none | any mismatch; owner declines |
| M-B14 | root | release | write INITIAL_CUSTODY RELEASED (hold CLI with the approved package digest; re-run must match) | RELEASED bound to the genesis head | **forward only** | none | none | re-run digest ≠ approved digest |
| M-B15 | root verifier | full readiness | none (read-only) | FULL_READINESS READY; E-19 activation dark | — | none | none | anything else |

> **Erratum (2026-10-07, G-7 of the M-B4/M-B5 preflight; the rest of this table is unchanged).** The M-B5 row
> previously read "install registry v1 + `current` pointer". No pointer exists: the installer installs only
> `authority-registry.v<N>.json` (its listing check refuses any other name), and the runtime reader states
> "registry storage != accepted registry head (the witness decides the head)". See the
> [M-B4/M-B5 remediation record](slice-15b2b-b1b3e-mb4-mb5-trust-install-remediation.md) §7.

> **Erratum (2026-10-07, M-B6 remediation D-2 and D-4; the table above is unchanged).** D-2: the M-B6 row's
> rollback boundary is **before M-B9b** (as §29, F-5 and sequencing C-7 state), not "before M-B9". D-4: the M-B8
> row names only the pin; the installer stage `install-owner-inputs` (P1B-8) installs **both** the on-host
> genesis-pin copy and the authorization-register copy, and requires `status P1B-6`. See the
> [M-B6 remediation record](slice-15b2b-b1b3e-mb6-ledger-remediation.md) §11.

> **Amendment (2026-10-17, OD-M11-12, owner-accepted; the table above is unchanged).** The M-B12 row's pass
> criterion "eligibility READY; package digest" means: the complete PR-1 package E-01 … E-24 is **READY** under the
> release verifier, over one complete hold observation and the captured HEALTH bound to the observed signer
> InvocationID, with every input established by merged owner records. Its digest is the M-B12 output. E-17
> `HOLD_RELEASE_ELIGIBILITY` READY alone is not M-B12 PASS. A NOT_READY package is recorded as `M-B12 NOT PASSED`,
> and M-B13 does not start. The completed, owner-accepted M-B11 signer start is not reinterpreted. Verifier
> semantics are unchanged. See the
> [M-B12 PR-B1 record](slice-15b2b-b1b3e-mb12-prb1-prerequisite-tooling.md) §18.

## 28. Future phases

Derived from §12–§20. The B1b-3d §23 L3a–L4 order is re-derived for V2 (PC-2).
Every phase starts by re-hashing the preservation set and re-proving §24.
No commands.

| Phase | Gate | Rows |
| --- | --- | --- |
| **PR-1S** | source + tests + review + merge; reproducible build | §31 |
| P1A-0 read-only preflight | PR-1S merged and its release reviewed | reproduce §4 **UNKNOWN** rows; installer `status L2b.2 9ac7de2` PASS; accepted-baseline pins recorded; DR-5 + preservation PASS |
| P1A-1 … P1A-6 inert release upgrade | P1A-0 | M-A1 … M-A6 (with S-1/S-2-style owner-only staging and unstaging around M-A1) |
| P1A-7 custody root | `status L2b.2 <NEW>` | M-A7 |
| P1A-8 witness identity + units | P1A-7 | M-A8, M-A9 |
| P1A-9 config skeleton | P1A-8 | M-A10 |
| P1A-10 routine proof | a real routine deployment | DR-5 non-vacuous for every new path; broker preservation |
| **PR-1A acceptance** | owner | inert install accepted; no custody claim |
| PR-2 | read-only | accepted inventory record (required before P1B-2 and P1B-3) |
| PR-3 foundation | owner | register + pin storage exist (required before P1B-9) |
| P1B-0 preflight | PR-1A, PR-2, PR-3 foundation | re-verify the PR-1A POST; RR-7 classes permit PR-1B |
| P1B-1 K-ROOT (off-host) | P1B-0 | M-B1 |
| P1B-2 K-WIT | P1B-1 | M-B2 |
| P1B-3 registry v1 (off-host) | P1B-2 | M-B3 |
| P1B-4 anchors | P1B-3 | M-B4 |
| P1B-5 registry bytes | P1B-4 | M-B5 |
| P1B-6 ledger | P1B-5 | M-B6 |
| P1B-7 genesis candidate | P1B-6 | M-B7 |
| P1B-8 pin | P1B-7 | M-B8 |
| P1B-9 witness start, then V2 genesis | P1B-8 | M-B9a, M-B9b |
| P1B-10 INITIAL_CUSTODY HELD | P1B-9 | M-B10 |
| P1B-11 signer start | P1B-10 | M-B11 |
| P1B-12 eligibility | P1B-11 | M-B12; denial proofs N1–N9, D1–D12, B1–B4 as evidence |
| PR-3 full material | owner | E-21 complete |
| P1B-13 owner acceptance | P1B-12 + PR-3 full + E-1…E-24 | M-B13 |
| P1B-14 RELEASED | P1B-13 | M-B14 |
| P1B-15 FULL_READINESS | P1B-14 | M-B15; a routine deployment re-proves DR-5 and preservation |
| **PR-1 acceptance record** | owner | the §5.1 narrower claim; no positive-issuance claim (RR-39) |

## 29. Points of no return

| Event | PONR? | Nature |
| --- | --- | --- |
| source install (M-A1 … M-A6) | **no authority PONR** | operational; reviewed release rollback remains possible |
| custody directory creation (M-A7) | no | empty directories; removable while empty |
| K-WIT credential creation (M-B2) | **custody PONR** | private material existed (zeroization not proven). Destroying the blob before M-B4 is allowed, but the key is burned: a replacement needs a new key |
| registry v1 signing (M-B3) | off-host authority object | harmless until a witness makes it head; the register records it |
| authority-ledger initialization (M-B6) | no, until M-B9b | deterministic; re-provisioning gives the same head. After the genesis binds it: rollback-sensitive, forward-only |
| V2 genesis commit (M-B9b) | **lineage PONR** | forward only; a second genesis is `GENESIS_MISMATCH` against the pin |
| owner genesis pin (M-B8) | record PONR | never silently replaced; a new pin is an owner re-bootstrap decision |
| INITIAL_CUSTODY HELD (M-B10) | **hold-store PONR** | never deleted, recreated, or re-bound; retry of the same ceremony only (RR-40) |
| INITIAL_CUSTODY RELEASED (M-B14) | **readiness PONR** | never returns to HELD; later changes are new ceremonies |
| FULL_READINESS | none | derived; a re-run, not a mutation |

## 30. Failure / crash matrix

| # | State | Automatic recovery | Fail closed | Owner intervention | Rollback allowed |
| --- | --- | --- | --- | --- | --- |
| F-1 | upgrade stopped before unit replacement | none | `status` has no matching stage: STOP | re-run the next stage or roll back | yes (flip selector; remove NEW) |
| F-2 | units replaced, no `daemon-reload` | none | `NeedDaemonReload=yes`; PR-1B refuses to start any unit | run the reload stage | yes |
| F-3 | custody dirs partially created | none | custody POST FAIL (`MISSING`/`CUSTODY_ROOT_UNEXPECTED_ENTRY`) | remove the empty partial set, re-run the stage | yes (empty only) |
| F-4 | K-WIT created, witness service absent | none | no witness → signer `WITNESS_MISSING` | continue forward, or destroy the unused blob and record it burned | destroy only before M-B4 |
| F-5 | ledger initialized, genesis absent | none | `WITNESS_MISSING` | continue to M-B7 | yes (remove DB before M-B9b) |
| F-6 | genesis written, `chain/` fsync missing | witness recovery at start (Prep A §9): after a crash, `UNINITIALIZED` → the owner re-runs `BOOTSTRAP` (same candidate, same digest); without a crash, the visible head is made durable, then published | never serves an uncommitted genesis | re-run `BOOTSTRAP` if `UNINITIALIZED` | no rollback of a committed genesis |
| F-7 | genesis committed, pin absent | none: impossible under RR-35 (the pin precedes signing). If ever observed, `RECOVERY_INPUT_INVALID` | yes | STOP | no |
| F-7a | committed genesis digest ≠ pinned candidate | none | yes | **STOP**; no second genesis (RR-35, RR-40) | no |
| F-8 | pin exists, HELD absent | none | `missing hold != released`: full readiness fails | write HELD | — |
| F-9 | HELD exists, eligibility fails | none | NOT_READY with the reasons | recoverable observation/readiness condition: correct it and re-evaluate the **same** HELD ceremony (retry). Genesis, initial ceremony identity, or HELD lineage wrong: **STOP**, separate reviewed recovery design (RR-40) | never delete or recreate HELD |
| F-10 | eligibility passed, owner does not release | none | stays HELD: no issuance | the owner decides; nothing expires into a release | — |
| F-11 | RELEASED written, full readiness fails | none | NOT_READY | diagnose. A later head change needs its own REGISTRY_MAINTENANCE cycle | RELEASED never returns to HELD |
| F-12 | service restart after RELEASED | signer and witness re-verify at start | readiness recomputed from inputs; no state lost | none if READY | — |
| F-13 | whole-host snapshot restore | none | **not detected** after genesis (chain, pointer, ledger, holds restored together read `CONSISTENT`) | only owner-side knowledge can notice | nonclaim |
| F-14 | routine deployment mid-upgrade | none | DR-5 `UNEXPECTED_RELEASE_ENTRY` FAIL; deploy aborts | finish the upgrade; re-run the deployment | — |
| F-15 | signer started with a stale unit definition | none | refused by the PR-1B stage contract (`NeedDaemonReload`) | reload | — |

## 31. Source blocker table

Every item must be implemented, TEST-proven, reviewed, and merged before
**any** live PR-1 mutation, unless its class says otherwise. **The next
engineering slice is PR-1S** (source/test only), which must close every
SOURCE CHANGE REQUIRED row; not PR-1A.

| # | Blocker | Classification | Notes |
| --- | --- | --- | --- |
| S-1 | successor-capable keygen, custody stage, unit `InaccessiblePaths`, RR-25 wording | **ALREADY IMPLEMENTED** (Source Prep B) | not installed; carried in the PR-1S release (RR-33) |
| S-2 | installer `UPGRADE_EXISTING_DEV_SYNTHETIC` mode with accepted-baseline pins and full tree check | **SOURCE CHANGE REQUIRED** | §7.2, §23 |
| S-3 | release file set / archive layout for the new runtime modules and shared contracts (`SHARED_HASHES`, `RUNTIME_PATHS`, forbidden markers kept) | **SOURCE CHANGE REQUIRED** | the runtime must import pure contracts it does not ship today (PF-13) |
| S-4 | witness account contract in the installer | **SOURCE CHANGE REQUIRED** | FI-7 |
| S-5 | live DEV_SYNTHETIC `RecoveryWitnessV2` service: profile, sockets, closed op set, start-up recovery | **SOURCE CHANGE REQUIRED** | §10; RR-37 |
| S-6 | K-WIT custody: keygen `witness` form, blob location | **SOURCE CHANGE REQUIRED** | RR-36 |
| S-7 | live durable witness store adapter (real filesystem, RR-9 order, `flock`, retention dir) + genesis candidate computation | **SOURCE CHANGE REQUIRED** | the TEST adapter shows the shape |
| S-8 | witness unit, socket, tmpfiles assets | **SOURCE CHANGE REQUIRED** | `systemd-analyze verify` in CI |
| S-9 | durable authority recovery ledger (SQLite, schema fingerprint, head function identical to the model) + provisioning CLI | **SOURCE CHANGE REQUIRED** | §14 |
| S-10 | signer runtime: registry/anchor/pin/register readers, witness client, readiness self-view, narrow C-4 wiring (complete root hold-store observation, never a single record; mandatory ledger observation); unit `InaccessiblePaths` for the K-WIT credential root and the hold root; issuance stays unwired | **SOURCE CHANGE REQUIRED** | §15; PF-15; RR-34/36/39 |
| S-11 | root tooling: hold writer and complete hold-store observer (HELD / RELEASED with the approved package digest), independent verifier CLI producing the canonical evidence package and its digest, owner off-host reproduction tooling, owner-workstation K-ROOT generator, registry v1 builder/signer, genesis-candidate recomputation | **SOURCE CHANGE REQUIRED** | PF-14; RR-38 |
| S-12 | installer `status` contracts for every P1A/P1B phase (active never-enabled units; new paths; ledger; witness state) | **SOURCE CHANGE REQUIRED** | FI-5, FI-9 |
| S-13 | DR-5 proof extension | **SOURCE CHANGE REQUIRED** (control-only) | §9 |
| S-14 | broker preservation `CUSTODY_PATHS` extension | **SOURCE CHANGE REQUIRED** (control-only; candidate hash unchanged) | §9 |
| S-15 | root denial-proof tool (N1–N9, B1–B4, broker probes, mount-namespace probe of the signer) | **SOURCE CHANGE REQUIRED** (control-only) | §8, §19 |
| S-16 | hold-store location | decided (RR-34): a fixed constant in S-10/S-11; created empty by PR-1A | |
| S-17 | snapshot inventory | **PR-2** | read-only |
| S-18 | owner register, pin storage, burned-ordinal register | **PR-3** | Prep A §7.1 / Prep B §4 models exist |
| S-19 | issuance (ISSUE path) wiring | **NOT NEEDED** (RR-39: issuance stays unwired) | |
| S-20 | V2 head-advance / epoch-advance witness execution ops | **SOURCE CHANGE REQUIRED** in PR-1S, TEST-proven, fail closed, never invoked in PR-1 (RR-37) | |
| S-21 | needrestart coverage of the witness unit | **ALREADY IMPLEMENTED** (PF-19) | |

## 32. PR-1 is not one slice

The split is required, not stylistic:

- **PR-1S** is large (S-2 … S-15). It is the failure domain of code review.
- **PR-1A** is reversible host plumbing. Its failure domain is availability.
- **PR-1B** creates custody, lineage, and hold state that is forward-only.
  Its failure domain is authority and custody.

Collapsing them would put an irreversible genesis in the same step as a
reversible file copy. The label "PR-1" survives only as the gate's row.
Infrastructure depth stays proportional: PR-1 builds exactly what the gate's
row names, and nothing for issuance, First Memory, or PROD.

## 33. Hidden assumption

**"What assumption could make PR-1 appear successfully installed while the
authority/custody baseline is still wrong?"**

The assumption: **that the installer's `status` PASS and a healthy signer
together describe the custody baseline.** They do not. `status` checks shape,
not identity (PF-7), and HEALTH is a self-claim about one instant. Each case:

| Case | Why it can look fine | What catches it |
| --- | --- | --- |
| release installed, CURRENT blob changed | `status` checks only type/owner/mode | §24 hash + identity pins (S-2) |
| unit updated, old process still running | unit bytes match | `NeedDaemonReload=no`, `InvocationID`/start time after the reload, `/proc/<pid>/cwd` (§23) |
| HEALTH good, wrong key loaded | HEALTH shows *a* fingerprint | B4 = B3 = B2 = B1 (binding), not HEALTH alone |
| V2 genesis over a stale registry | genesis verifies | the owner-reproduced candidate digest pinned before signing (RR-35); register head entry |
| owner pins a digest from another genesis | a pin exists | pin = the owner's own offline recomputation, not a copy |
| hold-store listing incomplete | the listed records parse | complete directory observation under `flock`; no ignored names (§17) |
| RELEASED exists but a newer HELD exists | the RELEASED record is valid | the complete store: any HELD blocks `FULL_READINESS` (Source Prep B §21.2) |
| K-WIT and K-ACT identical | both are valid Ed25519 keys | distinctness evidence E-10; `WITNESS_KEY_IS_AUTHORITY_KEY` |
| ledger head does not match genesis | both exist | `GENESIS_LEDGER_POSITION_MISMATCH`; ledger check E-15 |
| broker/deployer can read new paths | no path is listed | DR-5 + broker probes for every new path, non-vacuous (S-13 … S-15) |
| snapshot holds blob + `credential.secret` | the live host is clean | PR-2 before PR-1B (§21) |
| installer success mistaken for acceptance | every stage printed PASS | acceptance is a separate owner act over E-1 … E-24 (§19) |
| the signer's own readiness mistaken for independent readiness | the signer reports READY-ish | the signer cannot observe the inventory (PC-7); only the root verifier and the owner's off-host re-evaluation count |
| a C-4 handler given a caller-chosen hold | the gate accepts a single record (PF-15) | S-10 accepts only the complete root observation and re-judges the whole set |
| an older owner approval reused for a changed state | the owner did approve *a* package | RELEASED requires the approved package digest to equal a current re-run (RR-38) |

## 34. Owner decisions (RR-33 … RR-40)

All **OWNER-ACCEPTED** in this closure pass. **No PENDING_OWNER_DECISION
remains before PR-1S.**

| # | Question | Accepted outcome | Classification |
| --- | --- | --- | --- |
| RR-33 | How is PR-1 decomposed, and which release does PR-1A install? | PR-1S (source/runtime wiring) → PR-1A (inert live install) → PR-1B (V2 bootstrap / owner acceptance). PR-1S produces the **single** reviewed release PR-1A installs, holding all machinery known to be required for the accepted PR-1 baseline. The Source Prep B release is not installed on its own; no second authority-host upgrade (§5, §6.1) | **OWNER-ACCEPTED** |
| RR-34 | Where does the live hold store live? | `/var/lib/lilith-authority-custody/holds/`: holds are mutable forward-only local state, not configuration. Root-owned parent; directory `root:root 0700`; records `root:root 0600`, `<sha256(ceremonyId)>.json`; no symlinks; no ignored classes; unexpected entries fail closed; completeness provable; fixed root tooling the only writer; signer a consumer that cannot rewrite; broker and deployer denied; never authority-bearing (§16, §17) | **OWNER-ACCEPTED (different path from the draft recommendation)** |
| RR-35 | Genesis pin order | PIN-BEFORE-COMMIT: candidate → digest → owner off-host reproduction and pin → on-host pin = candidate → K-WIT signs that candidate → durable commit → committed digest re-verified = pin. Mismatch → STOP; no silent second genesis (§13) | **OWNER-ACCEPTED** |
| RR-36 | K-WIT blob location | separate K-WIT custody under `/etc/lilith-recovery-witness/credentials/` (`root:root 0700`, one `root:root 0600` blob, no symlinks); never in `/etc/credstore.encrypted`; accepted credential name and keyId unchanged; deployer, broker, and K-ACT signer denied; plaintext only through the witness unit's systemd credential; host-key mechanism unchanged; filename SOURCE DETAIL (§11) | **OWNER-ACCEPTED** |
| RR-37 | Witness op set in PR-1S | ship the TEST-proven V2 registry-head and RecoveryEpoch execution machinery, inert: never executed in PR-1, fail closed behind the authorization / witness / hold / environment gates; no authorization manufactured. PR-1 uses only bootstrap/genesis (plus read and ledger-advance). `installed code != enabled mutation` (§10) | **OWNER-ACCEPTED (with inertness requirement)** |
| RR-38 | How is acceptance reproduced? | two reproductions: A on-host root verifier (canonical evidence package with a canonical digest + eligibility result); B the owner's off-host verification from off-host material. Release only when the approved package digest equals a current re-run. `on-host PASS != owner acceptance` (§19) | **OWNER-ACCEPTED** |
| RR-39 | PR-1 scope versus B1b-3d §22 | L3a–L4-style custody/bootstrap + OS/deployer/broker denial proofs + loaded-key/HEALTH verification + V2/hold/readiness bootstrap. Issuance unwired; no positive OwnerEvidence signing; RR-14a stays deferred; no full legacy B1b-3d acceptance claimed; the acceptance record names the narrower claim. `PR-1 acceptance != positive evidence issuance acceptance` (§5.1) | **OWNER-ACCEPTED** |
| RR-40 | Re-bootstrap after INITIAL_CUSTODY HELD | never delete/recreate HELD, never create another genesis, never silently reset, never reuse the initial ceremony ID for other state. Recoverable eligibility failures: retry the same HELD ceremony. Wrong genesis / ceremony identity / HELD lineage: STOP; separate reviewed recovery design (§18) | **OWNER-ACCEPTED** |

The dependency order of §20 is also OWNER-ACCEPTED.

**Derived consequence (not a new decision).** Under RR-34 the signer cannot
read the `0700` hold store. Its C-4 handler therefore receives the complete
root-produced hold-store observation instead of reading the store itself
(§15). This follows from the accepted ownership (host root owns the holds;
the signer consumes) and matches the existing treatment of the credential
inventory (PC-7). It changes no authority, state owner, custody boundary, or
failure semantics: C-4 is never exercised in PR-1, and `FULL_READINESS` is
reproduced by the root verifier and the owner in any case.

Source details that do not change authority, state owner, security
boundary, or failure semantics (for PR-1S to fix and review): exact CLI
names and argument forms; the ledger's physical SQL; the evidence-package
schema and digest separator; the K-WIT blob filename; the modes of the
`/etc/lilith-recovery-witness` and `/var/lib/lilith-authority-custody`
parents; whether the witness package ships inside the authority-dev release
tree (recommended: one reviewed release, two units, RR-25 unchanged) or its
own tree; the listing-digest encoding.

## 35. Live entry matrix

**Current verdict: DO NOT PROCEED with any PR-1 live phase.** Live PR-1
mutation is **NOT AUTHORIZED**. The next slice is PR-1S.

| Condition | Verdict |
| --- | --- |
| any §31 SOURCE CHANGE REQUIRED item unresolved | **DO NOT PROCEED** |
| PR-1S not merged, or its release not reviewed | **DO NOT PROCEED** |
| PR-2 incomplete | PR-1A: **ALLOWED WITH EXPLICIT NONCLAIM** (no custody claim). K-WIT generation, registry v1 signing, and everything after: **DO NOT PROCEED** |
| PR-3 foundation absent | PR-1A and the ledger bootstrap: PROCEED TO NEXT PR-1 PHASE. Genesis commit: **DO NOT PROCEED** |
| PR-3 full material absent | owner acceptance and RELEASED: **DO NOT PROCEED** |
| new release not installed | PR-1A phases: PROCEED TO NEXT PR-1 PHASE (the upgrade is the phase). PR-1B: **DO NOT PROCEED** |
| custody dirs absent | P1A-7 may create them; everything after: **DO NOT PROCEED** |
| K-WIT absent | up to P1B-1: PROCEED TO NEXT PR-1 PHASE. Anchors and genesis: **DO NOT PROCEED** |
| authority ledger absent | genesis candidate and commit: **DO NOT PROCEED** (PF-11) |
| V2 genesis absent | HELD, signer start, eligibility: **DO NOT PROCEED** |
| owner genesis pin absent | K-WIT signing and genesis commit (RR-35): **DO NOT PROCEED** |
| committed genesis ≠ pin | **DO NOT PROCEED**; STOP (RR-35, RR-40) |
| HELD absent | signer start and eligibility: **DO NOT PROCEED** |
| eligibility fails | owner acceptance and release: **DO NOT PROCEED**; retry the same HELD after a recoverable correction (RR-40) |
| owner acceptance absent, or its package digest ≠ current re-run | RELEASED: **DO NOT PROCEED** |
| RELEASED absent | FULL_READINESS and PR-1 acceptance: **DO NOT PROCEED** |
| FULL_READINESS fails | PR-1 acceptance: **DO NOT PROCEED** |
| positive issuance unwired / unproven | **ALLOWED WITH EXPLICIT NONCLAIM** (required: RR-39) |
| registry-head / epoch execution code installed | **ALLOWED WITH EXPLICIT NONCLAIM** (inert; never invoked in PR-1, RR-37) |
| activation grant absent | **ALLOWED WITH EXPLICIT NONCLAIM** (required: PR-1 never creates one) |
| whole-host rollback unresolved | **ALLOWED WITH EXPLICIT NONCLAIM** (`wholeHostRollbackProtected: false`) |
| any preservation-set or §24 difference | **DO NOT PROCEED** |

B1b-3e live rehearsal is **not** authorized by any row. It stays gated by the
[live-rehearsal gate](slice-15b2b-b1b3e-live-rehearsal-gate.md) §10, which
needs PR-1, PR-2, and PR-3 accepted and a separate authorization.

## 36. Nonclaims

This record does not claim, create, or authorize:

- PROD authority, or closure of the cross-environment debt;
- real-owner-grade custody, or real-owner-grade memory authority;
- First Memory;
- Privacy custody (B1b-3f);
- a Stage III retry;
- a live rotation, revocation, epoch advance, or restore;
- a live successor credential;
- a whole-host rollback solution;
- media zeroization or remanence elimination;
- an activation grant;
- positive OwnerEvidence issuance, or full legacy B1b-3d §22 acceptance;
- any executed registry-head or RecoveryEpoch transition;
- that installer success, service health, genesis creation, or eligibility
  equals authority acceptance;
- that source tests passing authorizes any live phase;
- any live command, runbook, or ceremony.

## Explicitly not done

- No DEV or PROD contact; no gcloud, SSH, IAP, sudo, systemctl, or
  systemd-creds; no installer run against any host.
- No live `/etc` or `/var/lib` inspected.
- No credential, K-WIT, K-ROOT, genesis, hold, register, or pin created.
- No authority ledger, registry, witness, epoch, credential slot, broker
  ledger, or L04 touched; no service started or stopped.
- No IAM, WIF, or sudoers change.
- No source, test, vector, workflow, or earlier record changed.
- No PR opened.
