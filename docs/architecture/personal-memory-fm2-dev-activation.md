# Personal memory FM-2: DEV activation of one owner-provided relationship-origin memory (PROPOSED)

**Status:** source and offline proof only, 2026-10-26. Nothing in this record is authorized by the repository. Every
DEV mutation below is its own owner go. No PROD, no provider call, no key generation, no memory written.

The goal is ONE meaningful canonical memory on DEV: the owner's own relationship-origin statement (at most 600
characters, the owner's words, never proposed or paraphrased here), admitted once with governed signer evidence and
explicit owner-device consent, creation disabled again, and recalled from an independent new session. Hermes is not
on this path: the root CLI bridge is the host, as for the accepted First Memory.

## 1. Observed DEV state (read-only, 2026-10-26, boot `cb0d71da`)

Evidence: `C:\Users\edufo\lilith-pm-activation-d82f7da\` (`pa_driver.py survey`, `A1-survey.*`, rc 0).

| Item | Observed |
| --- | --- |
| Host | `lilith-dev-01`, boot `cb0d71da-32a7-402b-b85e-5748da012bff` (unchanged since Privacy activation) |
| Core API | `lilith-os-api-dev` 304463 running from `releases/d82f7dac…` (deploy 40354335433) |
| Authority release | only `e2324a5f89200aa5f374c4a43a13cb76b36376f9`, manifest `a2f32664…`, `protocol.py` `e5ac085e…`, `cli.py` `f65d1f48…`; no process on the retired 57bff671 |
| Signer / witness | the FM-1 accepted replacements, NRestarts 0, both from `releases/e2324a5…` (§2) |
| Ledger / hold / witness | seq 6 head `e7d4cc0f…` consistent; hold `bb7576f4…` RELEASED; witness CONSISTENT |
| Credentials | K-WIT ino 262585 `f8759370…`, K-PAN ino 262565 `c4563726…`, owner-actor `6a61c350…`; pins `kpan` `49c05db2…`, `kpck` `1b7b8cfa…` |
| Privacy | gate READY, durability READY for THIS boot; anchor v1 `c3c0dc33…`, checkpoint seq 1 `abc549e1…`; Privacy DB `429ae756…` (= the R3-dev baseline, byte-identical), stale path ABSENT |
| F9c2 FORGET | receipt `aaa06e1e…`, tombstone `ad97f246…`, provider ledger `68b4057e…` unchanged; intent directory EMPTY, no in-progress |
| L04 | integrity ok, WAL 0 bytes; exactly 1 admission `madm.ccb20162be02446fa1d60737c37e56fe`, 1 item (the codename); owner ledgers at schema **v2** (the F9c2 drill provisioned FM-02) |
| Creation | `/etc/lilith-first-memory-dev/canonical-config.json` `4fa82ae6…` = DISABLED, no capability |
| Host tree | `/opt/lilith-first-memory-dev/current`: 92 files, root-owned, none writable = the FM-1 tar `5ea19196…` exactly |
| Root executor | Hermes `f293e72-f9c2`, `hermes_forget_executor.py` `4992f932…` (First Interaction intent only); frozen Core API copy differs from d82f7da in `canonical_authority.py` (`631eee9e…` -> `1d05aeaf…`) and `memory_action_v2.py` (`f64ec3ce…` -> `2132ac99…`); the other three equal |
| Hermes context socket | not installed (optional, §6) |

## 2. FM-2: the successor signer release and its one transition

**Release.** Built from the exact merge `d82f7dac669f37c494beebf9bbb99dffdb6c23f5` with the accepted V3 builder and
wheels; evidence `C:\Users\edufo\lilith-pm-build-d82f7dac669f37c494beebf9bbb99dffdb6c23f5\` (`EVIDENCE-SHA256SUMS`
`fcf23a7721e9312281aa46f8cfe5060db8d6913bc6ddcd93f127d2de2289d4fa`).

| | Value |
| --- | --- |
| Archive | `9588c85b2ed424da8c10dcac17d49202b2436304fac830faeda7a172895889f4`, 5387827 bytes (Windows A = WSL B) |
| Manifest | `81a047657698c1903d1fd5cc30e725fdbbf3ea84ccf5b587f597ecba1be22d56` |
| Builder stamp | `c7fe0bb339776ea3e05c155516fd18abc1b352f71b15365c264a6d27f4543853` |
| Identity | `eea6e0b593887e154e1a3e099e41c0589249d410b5ee7cadff36c68068de622f` |
| Attestation | REPRODUCED `c5bf54b628fb454b802fe81a6c6f93a4f6ad3fe15f2c63a4bd975940ff38f5c5`; `check` PASS on both archives |
| Recipe / digests | recipe `1e61c2bad664c34cfded59d7d5b6400ab6da659716fd7890836891e200e74b7b`; authority `76568cee2c878aba0e5ee5743f28e049e90d726d9acd49d497b25588a0c54b56`; witness `c911b7334d97dfe3b9246832d5301a830771e3f41c3b2d6d86867519de16c2be` (= e2324a5) |
| Delta vs installed e2324a5 | exactly `lilith_authority_dev/protocol.py` (`e5ac085e…` -> `8a082a12…`) and `lilith_authority_root/cli.py` (`f65d1f48…` -> `46f21565…`) + the manifest; 70 members each, none added or removed; every witness member, unit, CLI, lock and wheel identical |

Keys, credentials, custody, registry, provenance, the E-23 / FM-1 pins and evidence are unchanged.

**Transition contract.** `fm2_signer_upgrade` (`UPGRADE_FM2_RELATIONSHIP_ORIGIN_SIGNER_DEV_SYNTHETIC`): OLD e2324a5
(the FM-1 contract's NEW), NEW d82f7da, the two-member delta, no added member (`LAYOUT_ADDED` keeps FM-1's two in
layout v3). `fm2_release_stages` and `fm2_operator` are the accepted FM-1 tools moved to that contract: the FM-1 files
are byte-unchanged and `tests/fm2_transform.py` is the complete, test-proven difference (renames, the ending
incarnations, the layout binding, the bundle and pins, no adjudicated step).

The ending incarnations are the FM-1 owner-accepted replacements: signer `5e439b2dfd434367a14ac5870b9a6316` / 298274
(the fourth K-ACT load, acceptance `13b1c742…`) and witness `efa7040c6ad94de69bfeadd496ba1ac3` / 294978 (K-WIT +
K-PAN, acceptance `4d745297…`).

Reused controls, unchanged: the exact signed release and archive pins; one current-selector change while BOTH units
are stopped (the witness follows `current` with `Restart=on-failure`); a unit on OLD after the select is a STOP;
root-owned interpreter and hash-pinned BOOT bundles; one marker per mutation; a fresh read-only gate before and a
status after every mutation; retirement only while no process uses OLD. The known local plink exit crash
(`0xC0000005`) on a post-status read takes the accepted single clean independent re-read (FM-1 record §5); there is
no new transport.

Ladder (each step its own go, rendered by `fm2_operator render`): TRANSFER, STAGE (F1), SIGNER_STOP (F2),
WITNESS_STOP (F3), SELECT (F4), WITNESS_START (F5; one K-WIT + one K-PAN load) -> verify + owner acceptance,
SIGNER_START (F6; the fifth K-ACT load) -> verify + owner acceptance, RETIRE (F7). After F7, re-derive the DR-5 target.

## 3. Origin FORGET usability (before the first OWNER_PERSONAL admission)

Without both parts below, an origin memory could not be forgotten: a recorded `relationship-origin.intent` would stop
the Hermes gateway and keep the Privacy gate at `FORGET_INTENT_PENDING` forever (every canonical recall refused).

**a. The trigger (this source).** `tools/relationship_origin_forget_dev.py` (`status`, `forget --owner-approval REF`,
`resume`; run as `lilith` from the host tree). The only installed trigger, `f9c_dev_drill.py`, is First-Interaction
only and builds its runner without the Track B barrier, which the runner now refuses. The tool composes only merged
parts: `RELATIONSHIP_ORIGIN_FORGET` (owners L04 + L18_V2; no Hermes adapter, so a floor naming Hermes is refused before
anything is held), the hold-first `relationship-origin.intent`, `DurabilityBarrier` over the authoritative Privacy DB,
and one single-use DEV_SYNTHETIC actor evidence keyed to the owner's approval reference (as F9c2). It refuses unless
Privacy is READY for this boot, no other intent is pending, the identity is not already suppressed and an origin
memory exists (never suppress an identity nobody admitted). Flow: `forget` -> INCOMPLETE_HOLD_ACTIVE
(`DURABILITY_BARRIER:ANCHOR_BEHIND`) -> the existing Privacy steps `advance` (witness K-PAN) and owner `checkpoint`
(WSL K-PCK) -> `resume` -> COMPLETE (L04, L18_V2) -> root reconcile releases the intent.

**b. The root executor (Hermes package, off-repo).** The staged patch
`C:\Users\edufo\lilith-hermes-staging\personal-memory-hermes-20261026` changes only `bin/hermes_forget_executor.py`
(`4992f932…` -> `2dafbfec8b88b36f9e1b92bea3b38ec5ab244a01a9182648b3058d7085c4072d`; diff `origin-forget-executor.patch`
`31ea9dc2…`). Every other staged `bin/` file equals the installed f9c2 release manifest. It adds a closed second intent
(`relationship-origin.intent` -> label RELATIONSHIP_ORIGIN, released only on Privacy's proof of the origin FORGET
COMPLETED with L18_V2); First Interaction semantics, the erasure scope and the Hermes owner scope are unchanged.

The patched executor reads `MA.RELATIONSHIP_ORIGIN_IDENTITY` from its frozen Core API copy, so the copy must be
re-pinned to the deployed d82f7da modules. The exact installed difference is the two files in §1; their import closure
stays inside the five pinned modules. Install plan (one go, root, no FORGET):

1. read-only gate: intent directory empty, no in-progress, Privacy READY, executor `4992f932…`, `executor.json`
   `a6428514…`, the five copy hashes of §1;
2. re-pin first (the unpatched executor works with the new copy): the installed `install_f9c.sh --repin` with
   `F9C_CORE_API_DIR` = the deployed d82f7da `lilith_memory`; expect exactly the two copy files to change;
3. the patched executor as a versioned, root-owned overlay
   `/opt/lilith-hermes-forget-executor/2dafbfec…/hermes_forget_executor.py` (the Hermes release stays byte-exact) and
   one drop-in `60-origin-executor.conf` per executor unit (`hermes-forget-executor`, `-hold`, `-reconcile`) that
   replaces only `ExecStart` with the same interpreter and mode; one `daemon-reload` under the C-3 preconditions;
4. read-only proof: as root, the overlay's `load_privacy` against the re-pinned copy reports the historical First
   Interaction FORGET completed with Hermes and the origin identity not completed.

Rollback: remove the three drop-ins and reload (the copy re-pin is compatible with both executors).

## 4. L04 schema v3 and the host tree

Proven offline against the exact DEV schema (the read-only dump rebuilt locally, no DEV row copied): `schema_state` 2,
`relationship_origin_l04_migration apply` -> `SCHEMA_V3_APPLIED` from v2, idempotent re-apply, integrity ok. The
merged DEV-vertical test proves the same on the First Memory shape with an admitted codename (rows byte-identical,
recall unchanged, creation per capability).

Host tree: the accepted rule (every `.py` of the six packages plus named tools) at the merge commit of this source,
with the tools `first_memory_dev_host.py`, `first_memory_l04_migration.py`, `relationship_origin_l04_migration.py`
and `relationship_origin_forget_dev.py`. Setup (one go, creation stays DISABLED): stage the tree beside `current`,
verify every hash and the trusted-tree rule, swap with the old tree kept until verified; then, as `lilith`, the
migration `apply` with a verified backup in `f9-drill/backups`; then read-only proof: schema v3, every preserved table
digest equal to §1's survey, the codename recalled through the bridge, config unchanged.

## 5. The one origin memory

After §2, §3 and §4: Privacy and FORGET readiness re-read; the owner supplies the statement; the exact normalized
statement is shown; one go names its digest and enables ONLY `canonical_memory.relationship_origin.create`, runs one
`remember our origin: …` with the owner-device credential, and disables creation again; the admitted revision, the
signer ledger, the witness and Privacy are re-read; a new host session recalls it (`what is our origin?`).

## 6. Hermes (optional, later)

The read-only context route (`first-memory-context`, socket units in `tools/hermes_context/`) ships in the FM-2
release but is not installed by this activation. Owner-personal content stays unavailable to Hermes until a Privacy
floor provisions Hermes for the origin scope and the owner grants one `lilith_os` session; no tool provisions that
floor. The codename can reach new Hermes sessions once the socket units and the adapter patch are installed under
their own go.
