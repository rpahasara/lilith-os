# Slice 15B2b-B1b-3e — PR-1S: Source / Runtime Wiring

Status:

- **SOURCE IMPLEMENTED / TEST PROVEN** (preflight §31 S-2 … S-15 and S-20;
  pure contracts, temp-directory hosts, TEST-only or local pipeline keys only)
- **NEW AUTHORITY-DEV SOURCE RELEASE PREPARED** (one release carrying the
  signer, the recovery witness, and the root tooling; not built on any host,
  not installed, not active)
- **LIVE INSTALL ABSENT**
- **PR-1A NOT AUTHORIZED**
- **B1b-3e LIVE REHEARSAL NOT AUTHORIZED**
- **WHOLE-HOST ROLLBACK UNRESOLVED**
- **REAL AUTHORITY ABSENT**; positive OwnerEvidence issuance stays unwired
  (RR-39)

Base: protected main `8826c2c7ff72d4ed5bded269005abe45d437403d`.

This slice is the source half of gate row PR-1, as decomposed by the
[PR-1 live install / acceptance preflight](slice-15b2b-b1b3e-pr1-live-install-preflight.md)
("the preflight"). The preflight's §31 blocker table is the scope. It builds
on [Source Prep A](slice-15b2b-b1b3e-source-prep-a-witness-readiness.md),
[Source Prep B](slice-15b2b-b1b3e-source-prep-b-successor-custody.md), the
[B1b-3e source contracts](slice-15b2b-b1b3e-source-contracts.md), the
[live-rehearsal gate](slice-15b2b-b1b3e-live-rehearsal-gate.md), and the
B1b-3d [custody design](slice-15b2b-b1b3d-dev-synthetic-custody-design.md) and
[deployer boundary](slice-15b2b-b1b3d-deployer-authority-boundary.md).

Nothing was contacted or changed. No DEV, PROD, gcloud, SSH, IAP, sudo,
systemctl, systemd-creds, or installer run against any host. No K-WIT,
K-ROOT, successor, or actor credential was generated. No authority ledger,
RecoveryWitnessV2 genesis, CeremonyHoldV1, owner register, or owner pin was
created on any host. No registry, witness, RecoveryEpoch, broker ledger,
L04, IAM, WIF, sudoers, or workflow was touched. `services/core-api/**` and
the memory-broker runtime are unchanged. Every runtime behaviour in this
record ran in a temporary directory or on synthetic stores.

```text
source release prepared != installed release
installation            != activation
ledger provisioned      != authority state accepted
genesis committed       != authority
hold release            != authority;  hold release != S_CURRENT
eligibility READY       != owner acceptance
FULL_READINESS          != issuance;   issuance stays unwired (RR-39)
root verifier PASS      != authority
```

## 1. Location and delivery impact

| Path | Role |
| --- | --- |
| `services/owner-memory-control/lilith_owner_memory/authority_ledger_journal.py` | **new, pure.** The authority-ledger journal (ops, head function, replay, refusals, epoch adoption) moved verbatim in behaviour out of the TEST model so the runtime never imports TEST code |
| `services/owner-memory-control/lilith_owner_memory/pr1_bootstrap.py` | **new, pure.** K-WIT profile and publication, witness anchor, genesis candidate and its digest, pin check |
| `services/owner-memory-control/lilith_owner_memory/pr1_acceptance.py` | **new, pure.** Complete hold-store snapshot, CURRENT preservation, installed-release verification, E01–E24 package, package digest, release decision |
| `services/owner-memory-control/lilith_authority_signer/synthetic_recovery_ledger.py` | **changed, TEST.** Re-exports the moved journal; behaviour unchanged |
| `services/authority-dev/lilith_authority_dev/{ledger,recovery,state,witness_client}.py` | **new, signer runtime.** Durable ledger; narrow C-4 handler; signer self-view; witness signer-socket client |
| `services/authority-dev/lilith_authority_dev/{core,protocol,server,profile}.py` | **changed.** Three recovery operations; frame limit 64 KiB; lazy wiring; ledger path |
| `services/authority-dev/lilith_authority_host/` | **new.** Fixed host paths, strict public-input readers, store observer (shared by signer, witness, root tooling) |
| `services/authority-dev/lilith_authority_root/` | **new, root tooling.** Hold store, observers, verifier, genesis tool, ledger tool, socket clients, closed CLI dispatcher |
| `services/authority-dev/bin/` | **new.** Five fixed CLI wrappers (release members `cli/<name>`) |
| `services/authority-dev/ceremony/install_authority_dev.py` | **changed.** `UPGRADE_EXISTING_DEV_SYNTHETIC`; PR-1A / PR-1B stages and status contracts |
| `services/authority-dev/ceremony/lilith_authority_keygen_dev.py` | **changed.** Closed `witness` form (K-WIT) |
| `services/authority-dev/ceremony/lilith_authority_owner_dev.py` | **new, owner workstation.** K-ROOT keygen, registry v1, witness anchor, off-host reproduction, package digest. Never release payload |
| `services/authority-dev/ceremony/build_authority_dev_release.py`, `release_file_set.py` | **changed.** Release set v2 (runtime, host, root tooling, witness payload, CLIs, pinned shared contracts) |
| `services/authority-dev/deploy/lilith-authority-dev.service` | **changed.** `InaccessiblePaths` adds the hold root (RR-34) and the K-WIT root (RR-36); the witness state stays group-readable by the signer (`2750`), never writable |
| `services/recovery-witness/` | **new service tree.** `lilith_recovery_witness` package, units, file set, README, 39 tests |
| `scripts/deployer_authority_boundary_proof.sh` | **changed (control-only).** DR-5 PR-1 ladder on its own report line |
| `scripts/verify_broker_dev_current_incarnation.py` | **changed (control-only).** `CUSTODY_PATHS` extended; `baselineCandidate` hash unchanged |
| `scripts/authority_custody_denial_proof.py` | **new (control-only).** Fixed-row root denial proof |

No workflow, IAM, WIF, sudoers, core-api, or memory-broker runtime change was
needed.

## 2. Controlling records and owner decisions

- The preflight §§5–31 and owner decisions **RR-33 … RR-40** (all accepted):
  RR-33 one reviewed release; RR-34 hold store
  `/var/lib/lilith-authority-custody/holds/`; RR-35 owner pin before any
  genesis commit; RR-36 K-WIT custody under
  `/etc/lilith-recovery-witness/credentials/`; RR-37 head/epoch execution
  code shipped inert; RR-38 owner acceptance package and digest; RR-39
  issuance unwired; RR-40 the initial HELD record is never recreated.
- Source Prep B: RR-22 … RR-32, hold-store dominance, compromise-epoch rule,
  the narrow C-4 gate (`successor_readiness.evaluate_recovery_gate`).
- The live-rehearsal gate: RR-6/7/9/11/17–21, including the RR-9 witness
  commit order reused by the live store.

No source in this slice conflicts with an accepted owner decision.

## 3. Release identity (SOURCE PREPARED / NOT INSTALLED)

`python services/authority-dev/release_file_set.py` on this tree:

| Field | Value |
| --- | --- |
| role | `lilith-authority-dev-synthetic-release-source-v2` |
| status | `SOURCE_PREPARED_NOT_INSTALLED` |
| runtime payload files | 53 (plus 6 `cli/` members) |
| `runtimeDigests.authority` | `08d6a99c7eb02cb659253ad37137651706931f2e7bf160224288f80343dd5521` |
| `runtimeDigests.witness` | `5137ddb03c3c1b17fceb400cee70a5e0b057c02f1c9138722f1260db1564d3c3` |
| `runtimeDigests.rootTooling` | `28e9d6cbdb0d2642074d10c4d8dc9e83c9c7b19f90c6676248b920cd6c47b903` |
| `witnessManifestSha256` | `5137ddb03c3c1b17fceb400cee70a5e0b057c02f1c9138722f1260db1564d3c3` (12 witness files, role `lilith-recovery-witness-dev-synthetic-source-v1`) |

These are source identities only. The installed-release identity is the
merged commit SHA the owner later builds, attests, and stages (M-A1); no such
build exists. The recovery witness ships inside the same archive (option A of
the preflight §10) with its own manifest digest, so there is one release and
one reviewed candidate (RR-33). The accepted OLD release stays
`9ac7de22bf977385ceb954624677e33f0bae062b` and the accepted CURRENT SHA-256
stays `6a61c350e848a833868f4573982fca9c75e2af79ccc9bd3716ae0303c26973f3`.

`SHARED_HASHES` pins nine additional pure modules (authority verifier,
recovery / rotation contracts, witness readiness, successor custody and
readiness, the journal, PR-1 bootstrap and acceptance). The forbidden runtime
markers are unchanged; `lilith_authority_signer` and every TEST seed marker
stay out of the payload.

## 4. S-2 — `UPGRADE_EXISTING_DEV_SYNTHETIC`

The installer gains a closed upgrade mode for the installed `9ac7de2`
release; it never looks like a fresh install.

| Command | Phase | Effect |
| --- | --- | --- |
| `upgrade-baseline <OLD>` | P1A-0 | none: prints the observed baseline for the owner to record off-host |
| `upgrade-status <OLD> <NEW> <baseline>` | any | none: classification and preservation |
| `upgrade-stage` | M-A1 | `releases/<NEW>` beside `<OLD>` (staging dir, full tree check, rename) |
| `upgrade-select` | M-A2 | `current -> releases/<NEW>` (atomic replace) |
| `upgrade-units` | M-A3 | replace the signer unit, socket, tmpfiles (owner reloads) |
| `upgrade-cli` | M-A5 | replace the keygen; create each new fixed CLI (collision refused) |
| `upgrade-retire-old` | M-A6 | remove `releases/<OLD>` only after NEW verifies |

The classification is closed: `FRESH_ABSENT`,
`EXISTING_ACCEPTED_OLD_RELEASE`, `STAGED_NEW_RELEASE`,
`SELECTED_NEW_RELEASE`, `UNITS_UPDATED`, `UNITS_RELOADED`, `CLI_UPDATED`,
`COMPLETE_NEW_RELEASE`, `INCONSISTENT`. Every stage re-checks the baseline:
the CURRENT blob (device, inode, size, owner, mode, mtime and ctime in
nanoseconds, SHA-256), the signer account identity, the credstore listing
(exactly CURRENT), the host key by `stat` only, and the absence of every
PR-1 object that must not yet exist. Any difference is
`PRESERVATION_FAILED` and stops before mutation. Each stage is idempotent
(`ALREADY_COMPLETE`) or refused; none creates an account, runs
`systemd-creds`, reloads, enables, or starts a unit. The upgrade ends at the
unchanged B1b-3d `L2b.2` status contract for NEW.

## 5. S-3 — release file set

`release_file_set.py` enumerates the exact source tree (authority-dev and the
recovery-witness tree through `witness_release_file_set.py`), maps every
payload member, pins the shared contracts, and rejects symlinks, unlisted
files, and forbidden markers. `RUNTIME_PATHS` in the installer equals the map
values. `cli_payloads` adds the five fixed CLI wrappers; the owner-workstation
tool is source-only.

## 6. S-4 — witness account

`witness-account` (P1A-8a) creates the system user and group
`lilith-recovery-witness` with no home and a `nologin` shell, distinct from
the signer's uid and gid. The account is never in the signer group
(`WITNESS_IN_SIGNER_GROUP` fails the status); an existing account is never
corrected.

## 7. S-5, S-7, S-20 — live DEV_SYNTHETIC RecoveryWitnessV2

`lilith_recovery_witness` is a socket-activated service with two inherited
listeners (`LISTEN_FDNAMES` `owner`, `signer`):

| Socket | Path | Owner | Mode | Operations |
| --- | --- | --- | --- | --- |
| owner | `/run/lilith-recovery-witness/owner.sock` | `root:root` | `0600` | `HEALTH`, `READ_WITNESS`, `BOOTSTRAP`, `EXECUTE_REGISTRY_HEAD_ADVANCE`, `EXECUTE_EPOCH_ADVANCE` |
| signer | `/run/lilith-recovery-witness/signer.sock` | `lilith-recovery-witness:lilith-authority-dev` | `0660` | `READ_WITNESS`, `RECORD_LEDGER_ADVANCE` |

Peers are checked by `SO_PEERCRED` (root on the owner socket, the signer
uid on the signer socket). The credential object exposes only
`sign_recovery_witness_v2`. The filesystem store
(`/var/lib/lilith-recovery-witness`, files `0640`, directories `0750`)
follows the RR-9 order: `flock`, write the next record `O_EXCL`, fsync,
fsync the directory, replace the pointer from scratch, fsync again. Start-up
recovery classifies and repairs only a torn pointer; it never bootstraps and
never rolls back. `BOOTSTRAP` is pin-before-commit: it recomputes the
genesis candidate, requires the on-host owner pin to equal its digest
(RR-35), signs, commits, and reports `GenesisCommitMismatch` as a STOP (no
retry, RR-40). `RECORD_LEDGER_ADVANCE` binds the previous witness digest.
The head-advance and epoch-advance executions (S-20) are shipped, TEST-proven,
and fail closed (transition hold check; `KEY_COMPROMISE` only for the epoch
op); PR-1 never invokes them (RR-37).

## 8. S-6 — K-WIT custody

`lilith-authority-keygen-dev witness` is closed (no arguments). Preconditions:
root, isolated interpreter, the DEV hostname; the credstore holds exactly
CURRENT; `/etc/lilith-recovery-witness` and its `credentials/` child are
`root:root 0700`, the parent lists only `credentials`, the child is empty,
and neither is a symlink. It writes one blob,
`/etc/lilith-recovery-witness/credentials/lilith-recovery-witness.witness.cred`,
`O_EXCL` through a directory fd, encrypted with
`systemd-creds encrypt --with-key=host --name=recovery-witness-signing-key`,
and proves CURRENT byte- and identity-unchanged before and after. It prints
only the public `LILITH_WITNESS_KEY_PUBLICATION` (key id
`test-only.witness.dev-synthetic.b1b3d.1`). The K-WIT profile refuses the
K-ACT key id, a non-test-only id, another credential name, a path under the
credstore, or PROD.

## 9. S-8 — witness unit, sockets, tmpfiles

`services/recovery-witness/deploy/`: the service (no `[Install]`, the two
socket units as `Sockets=`, `LoadCredentialEncrypted=` for the K-WIT blob,
`InaccessiblePaths` for the credstore, custody roots, signer state, and broker
state; the K-WIT blob reaches the process only through systemd), the two
sockets, and a tmpfiles file for the runtime directory only
(`/run/lilith-recovery-witness` `0710 root:lilith-authority-dev`).
The state directory is created once by the installer stage `witness-state`
(P1B-9a) as `lilith-recovery-witness:lilith-authority-dev 2750`; the unit has
no `StateDirectory=`. `systemd-analyze verify` (with `ExecStart` stubbed, as
CI does for the signer) is clean for all five units locally; CI verifies only
the authority-dev units (§22).

## 10. S-9 — durable authority recovery ledger

`/var/lib/lilith-authority-dev/authority_ledger.db`, signer-owned, `0600`,
SQLite WAL, `synchronous=FULL`, an exact schema fingerprint, append-only and
contiguous journal triggers, and terminal-row triggers. Every write replays
the full journal through `authority_ledger_journal` (the same ops and head
function as the accepted model) and materializes exactly the replayed rows.
`open_existing` never creates a file (`AUTHORITY_STATE_MISSING`).
`provision` is the one explicit action: signer-owned `0700` directory, no
existing file or sidecar, one `GENESIS` op (sequence 1). The public writer
accepts only `ADVANCE_EPOCH`, `VOID_CHALLENGE`, `QUARANTINE_USE` at an exact
expected position. Root reads a private `0600` copy of the database and WAL
(`observe_copy`); the live file is never opened in place by root.

`lilith-authority-ledger-dev provision <version>` is two halves: as root it
prepares the empty state directory and runs the signer half through
`runuser`; the signer half verifies the installed registry and anchors and
provisions. A second run is `LEDGER_TOOL_ALREADY_PROVISIONED`.

## 11. S-10 — signer runtime and narrow C-4 wiring

The signer reads the installed public inputs (registry-root anchor, witness
anchor, registries, pin copy, register copy) through strict readers, reads
the witness through its signer socket, and exposes three recovery operations
through `recovery.py`, which is the only signer module that imports
`successor_readiness` and imports no minter:

1. parse the **complete** hold-store snapshot (never a single record): exact
   directory, sorted unique bounded names, per-entry bytes, and a listing
   digest that must match;
2. require exactly one HELD record governing the operation;
3. open the ledger (a missing ledger is `AUTHORITY_STATE_MISSING`) and take a
   mandatory observation;
4. `evaluate_recovery_gate`;
5. `ADVANCE_EPOCH`: the ledger must equal the witness position (a
   `BROKER_REGISTRY_VIEW_STALE` lag from the in-epoch compromise marking is
   tolerated: the adoption itself moves the view to the target, as in the
   Prep B model), then `epoch_adoption_op`; the witness binds the adoption by
   its own later `EXECUTE_EPOCH_ADVANCE`, so no `RECORD_LEDGER_ADVANCE` is
   sent;
6. `VOID_CHALLENGE` / `QUARANTINE_USE`: exact position, stale ids only
   (`NO_PRE_RECOVERY_WORK` otherwise), append, then `RECORD_LEDGER_ADVANCE`;
   a witness failure after commit is reported `LEDGER_AHEAD_OF_WITNESS`.

Every reply carries `authorityGranted: false` and `signingPermitted: false`.
`ISSUE_OWNER_EVIDENCE` is still refused. The signer self-view is always
`NOT_READY` (`CREDENTIAL_INVENTORY_UNOBSERVABLE_BY_SIGNER`,
`HOLD_STORE_UNOBSERVABLE_BY_SIGNER`, `ISSUANCE_UNWIRED`): readiness belongs
to the root verifier.

## 12. S-11 — root tooling and the owner acceptance package

`lilith_authority_root` (release members; invoked only through the fixed
CLIs as root):

- **Hold store (RR-34).** `/var/lib/lilith-authority-custody/holds/`, parent
  `0700` listing only `holds`, directory `0700`, records `0600` under their
  deterministic names. The observer takes `flock`, lists every entry, and
  refuses dot files, temporaries, subdirectories, symlinks, wrong modes or
  owners, misnamed records, and a directory that changed during the read.
  Writes are forward-only: `create-initial-held` (RR-40, never recreated),
  `release-initial <approvedPackageDigest>` (only when a fresh re-run of the
  verifier yields the same package digest and is READY), successor,
  maintenance, and custody-debt HELD records, and readiness-gated release.
- **Verifier (RR-38).** A closed owner input document
  (`LILITH_PR1_VERIFIER_INPUTS`) plus live observations: installed release
  tree byte-for-byte against the attested manifest, fixed CLIs, unit states,
  CURRENT preservation against the first preflight observation, credential
  inventory, unit credentials, witness store, ledger copy, hold store, signer
  health, external proofs, activation line, PR-2 snapshot inventory, and PR-3
  off-host material. It produces checks E01–E24, the canonical package, and
  `packageDigest = sha256("LILITH_PR1_OWNER_ACCEPTANCE_PACKAGE_V1\0" ||
  JCS(package))`. PR-2 or PR-3 absent is `NOT_READY`
  (`SNAPSHOT_INVENTORY_ABSENT_PR2`, `OFFHOST_REGISTER_ABSENT_PR3`), never a
  default pass. The package states `authorityGranted`, `activationGranted`,
  `issuanceWired`, and `wholeHostRollbackProtected` as `false`. Device,
  inode, and nanosecond times are decimal strings (they exceed the JCS
  safe-integer domain).
- **Genesis tool.** Recomputes the candidate from the installed inputs and a
  private ledger copy; `bootstrap` sends `BOOTSTRAP` only when the pin copy
  equals the candidate digest.
- **Owner workstation tool** (`ceremony/lilith_authority_owner_dev.py`,
  never payload): K-ROOT generation (passphrase-encrypted PKCS#8 DER, `0600`,
  `O_EXCL`), registry v1 signing, witness anchor, off-host reproduction of
  the ledger genesis, candidate, pin, and empty register, and the package
  digest.

The five fixed CLIs (`lilith-authority-ledger-dev`,
`lilith-authority-hold-dev`, `lilith-authority-verify-dev`,
`lilith-authority-recovery-dev`, `lilith-recovery-witness-owner-dev`) run
`/opt/lilith-authority-dev/current/venv/bin/python -IB`, import only the
selected release, refuse a non-root caller, and accept closed argument forms
only.

## 13. S-12 — installer status contracts

`STAGES` gains the PR-1 phase contracts `P1A-8a`, `P1A-8b`, `P1A-8c`,
`P1A-9`, `P1B-2`, `P1B-4`, `P1B-5`, `P1B-6`, `P1B-8`, `P1B-9a`, `P1B-9b`,
`P1B-10`, `P1B-11`. Status checks shape only (paths, owners, modes, exact
listings, unit load and active states, CLI bytes); content is the root
verifier's. Units must never be enabled; the witness may be active from
P1B-9a and the signer from P1B-11. `/run/*` directories are optional
(runtime), never required. PR-1B write stages (`install-anchors`,
`install-registry`, `install-owner-inputs`, `witness-state`) are write-once
and take strict canonical JSON (no floats, no duplicates).

The fresh B1b-3d ladder is unchanged except that `L1c.3` installs every fixed
CLI the release ships, not only the keygen.

## 14. S-13 — DR-5 extension (control-only)

The routine-deployer proof gains a second, cumulative PR-1 ladder
(`PR1_ABSENT`, `P1A-5`, `P1A-7`, `P1A-8a`, `P1A-8b`, `P1A-9`), derived only
from root-owned objects, valid only on top of `L1c.3`
(`PR1_OBJECT_BEFORE_L1C3`). It is reported on its own line,
`PR1_AUTHORITY_BOUNDARY maturity=<step>`, just before the final line. The
final line and its B1b-3d `maturity=` vocabulary are unchanged, so the
`deploy-dev.yml` gate regex needs no change; any PR-1 failure still makes the
final line FAIL. The witness account's `sudo -u` is queried; every witness
unit verb is queried, never run; leaves beneath root-only directories are
`UNOBSERVABLE_BY_DESIGN`, never "denied". `/var/lib` joins the governed
parents. A `releases/.<sha>.staging` entry still fails (no routine deploy
mid-upgrade).

## 15. S-14 — broker preservation paths (control-only)

`CUSTODY_PATHS` in `verify_broker_dev_current_incarnation.py` now also names
every PR-1 path, reported (not judged) so the broker preservation transcript
shows their presence while the broker is proven unchanged. The pinned
`baselineCandidate` SHA-256 is unchanged. The PR-1 paths:

| Path |
| --- |
| `/etc/lilith-authority-custody` |
| `/etc/lilith-authority-custody/prepared` |
| `/etc/lilith-authority-custody/retired` |
| `/var/lib/lilith-authority-custody` |
| `/var/lib/lilith-authority-custody/holds` |
| `/etc/lilith-recovery-witness` |
| `/etc/lilith-recovery-witness/credentials` |
| `/etc/lilith-recovery-witness/credentials/lilith-recovery-witness.witness.cred` |
| `/etc/lilith-authority-dev/trust` |
| `/etc/lilith-authority-dev/registry` |
| `/etc/lilith-authority-dev/owner` |
| `/var/lib/lilith-authority-dev/authority_ledger.db` |
| `/etc/systemd/system/lilith-authority-dev.socket` |
| `/etc/systemd/system/lilith-recovery-witness-owner.socket` |
| `/etc/systemd/system/lilith-recovery-witness-signer.socket` |
| `/etc/tmpfiles.d/lilith-authority-dev.conf` |
| `/etc/tmpfiles.d/lilith-recovery-witness.conf` |
| `/usr/local/sbin/lilith-authority-keygen-dev` |
| `/usr/local/sbin/lilith-authority-ledger-dev` |
| `/usr/local/sbin/lilith-authority-hold-dev` |
| `/usr/local/sbin/lilith-authority-verify-dev` |
| `/usr/local/sbin/lilith-authority-recovery-dev` |
| `/usr/local/sbin/lilith-recovery-witness-owner-dev` |

## 16. S-15 — root denial proof (control-only)

`scripts/authority_custody_denial_proof.py <P1A-10|P1B-12>` runs as root,
takes no other argument, and executes only fixed rows: `runuser -u <account>
-- /usr/bin/test <op> <path>` for the deployer, `lilith`, the broker, the
signer, and the witness against the credstore, custody roots, hold root,
K-WIT root, signer state, witness state, and broker state; and, at P1B-12,
`nsenter` into the running signer's mount namespace with its numeric ids.
An absent path is `DENIAL_VACUOUS_PATH_ABSENT` (never a denial); any allowed
access fails; the last line is `AUTHORITY_CUSTODY_DENIAL_PROOF=PASS|FAIL`.

## 17. Crash and failure behaviour (tests)

| Case | Result |
| --- | --- |
| upgrade interrupted at any stage | re-run is `ALREADY_COMPLETE` or the next stage; `INCONSISTENT` stops |
| CURRENT re-written with identical bytes | `PRESERVATION_FAILED` (inode / ctime) |
| witness torn pointer | start-up recovery repairs forward; never rolls back |
| genesis committed ≠ pin | STOP (`GenesisCommitMismatch`), no retry |
| ledger committed, witness record failed | `LEDGER_AHEAD_OF_WITNESS` |
| hold listing is a subset, stale, or has two HELD | refused before any ledger write |
| hold store changes during observation | `HOLD_STORE_BUSY` / refused |
| release with a stale or malformed package digest | `HOLD_RELEASE_NOT_PERMITTED` |
| verifier run | read-only (no mtime or inode change anywhere) |

## 18. Refactors

- The journal and replay moved from the TEST ledger model into the pure
  `authority_ledger_journal` so the runtime ledger shares the exact head
  function without importing `lilith_authority_signer`; the TEST model
  re-exports it.
- The witness tree's file-set module is `witness_release_file_set.py` (the
  authority-dev builder imports both; one name would collide).
- The installer account check is generalized for the second account.

## 19. Compatibility

Existing structural tests that asserted the Prep A / Prep B contracts are
unreachable from runtime now scope that claim: core-api, the memory broker,
and scripts still never import them; the authority-dev release may; the TEST
writers stay unreachable everywhere; and within the signer only `recovery.py`
reaches `successor_readiness`. The B1b-3d ladder, the keygen `actor` form
(and its historical `USAGE_ONLY_ACTOR` refusal), and the DR-5 final line are
unchanged.

## 20. Tests

| Suite | Result |
| --- | --- |
| `services/authority-dev/tests` (incl. the witness loader) | 214 OK |
| `services/owner-memory-control/tests` | 489 OK |
| `services/recovery-witness/tests` | 39 OK |
| DR-5, broker preservation, needrestart, classifier, PR-CI separation | 35 + 38 + 24 + 19 + 9 OK |

New: `test_pr1s_runtime_wiring.py` (28), `test_pr1s_installer_upgrade.py`
(14), `test_pr1s_root_tooling.py` (24), `test_recovery_witness.py` (39), and
four DR-5 PR-1 ladder tests.

## 21. Remaining before any PR-1 live phase

- PR-1S review and merge (this record does not merge it).
- A separate owner authorization for PR-1A; PR-1A itself (preflight §27).
- **PR-2** (snapshot inventory, S-17) and **PR-3** (owner register, pin
  storage, burned-ordinal register, S-18); until both exist the verifier is
  `NOT_READY` by construction.
- The live entry matrix (preflight §35) still reads **DO NOT PROCEED**.

## 22. Remaining SOURCE DETAIL

- CI runs `systemd-analyze verify` for the authority-dev units only; the
  witness units were verified locally. Adding them to CI is a workflow change
  and is left for a later review.
- The witness suite runs in CI through
  `services/authority-dev/tests/test_recovery_witness_suite.py` (CI discovers
  only the authority-dev and owner-memory-control test directories).

## 23. Nonclaims

This record does not claim, create, or authorize:

- any PR-1A or PR-1B live phase, or any live command, runbook, or ceremony;
- an installed release, a K-WIT, a K-ROOT, an authority ledger, a V2 genesis,
  a hold record, an owner pin, or an owner register on any host;
- PROD authority, or closure of the cross-environment debt;
- positive OwnerEvidence issuance, an activation grant, or First Memory;
- any executed registry-head or RecoveryEpoch transition;
- a whole-host rollback solution;
- that tests passing, installer success, service health, genesis creation,
  eligibility, or a verifier PASS equals authority acceptance;
- the B1b-3e live rehearsal.

## Explicitly not done

- No DEV or PROD contact; no gcloud, SSH, IAP, sudo, systemctl, or
  systemd-creds against any host; no installer run against any host.
- No real credential, registry, witness, ledger, hold, pin, or register
  created; no service started or stopped.
- No workflow, IAM, WIF, sudoers, core-api, or memory-broker runtime change.
- No PR opened; nothing merged.
